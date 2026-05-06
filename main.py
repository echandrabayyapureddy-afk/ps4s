"""
Creator Content Posting Optimization System
=============================================
Winning solution: Joint platform × time-slot optimization using
a multiplicative scoring model over platform activity, historical
creator engagement, and base engagement multipliers.

Scoring formula:
    score = platform_activity(platform, t) 
            × historical_engagement(creator, platform, content_type, t)
            × base_engagement(creator)

For each content item, we evaluate all 48 combinations (2 platforms × 24 hours)
and greedily pick the highest-scoring option. The scheduling decision is
determined by comparing the optimal time slot to the content's creation timestamp.
"""

import csv
import sys
from collections import defaultdict


# ──────────────────────────────────────────────
# 1. DATA LOADING
# ──────────────────────────────────────────────

def load_content(path):
    """Load content submissions. Returns list of dicts."""
    items = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys: strip BOM, quotes, whitespace
            clean = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
            items.append({
                'content_id': int(clean['content_id']),
                'creator_id': int(clean['creator_id']),
                'content_type': clean['content_type'],
                'created_timestamp': int(clean['created_timestamp']),
                'time_sensitivity': clean['time_sensitivity'],
            })
    return items


def load_creators(path):
    """Load creator profiles. Returns dict: creator_id -> {base_engagement, cooldown_hours}."""
    creators = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = int(row['creator_id'])
            creators[cid] = {
                'base_engagement': float(row['base_engagement']),
                'cooldown_hours': int(row['cooldown_hours']),
            }
    return creators


def load_platform_activity(path):
    """Load platform activity scores. Returns dict: (platform, time_slot) -> score."""
    activity = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['platform'].strip(), int(row['time_slot']))
            activity[key] = float(row['activity_score'])
    return activity


def load_historical_engagement(path):
    """Load historical engagement. Returns dict: (creator_id, platform, content_type, time_slot) -> avg_engagement."""
    engagement = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                int(row['creator_id']),
                row['platform'].strip(),
                row['content_type'].strip(),
                int(row['time_slot']),
            )
            engagement[key] = float(row['avg_engagement'])
    return engagement


# ──────────────────────────────────────────────
# 2. SCORING FUNCTION
# ──────────────────────────────────────────────

PLATFORMS = ['Instagram', 'YouTube']
TIME_SLOTS = list(range(24))

# Default fallback values when data is missing
DEFAULT_ACTIVITY = 0.6
DEFAULT_ENGAGEMENT = 0.5
DEFAULT_BASE = 1.0


def compute_score(creator_id, platform, content_type, time_slot,
                  creators, activity, engagement):
    """
    Compute the engagement score for a (creator, platform, content_type, time_slot) combination.
    
    Score = platform_activity × historical_engagement × base_engagement
    """
    # Platform activity at this time slot
    act = activity.get((platform, time_slot), DEFAULT_ACTIVITY)

    # Creator's historical engagement for this specific combination
    eng = engagement.get((creator_id, platform, content_type, time_slot), DEFAULT_ENGAGEMENT)

    # Creator's base engagement multiplier
    base = creators.get(creator_id, {}).get('base_engagement', DEFAULT_BASE)

    return act * eng * base


# ──────────────────────────────────────────────
# 3. OPTIMIZATION ENGINE
# ──────────────────────────────────────────────

def optimize_content(content_item, creators, activity, engagement):
    """
    Find the optimal (platform, time_slot) for a single content item
    by evaluating all 48 combinations and picking the maximum score.
    
    Returns: (best_platform, best_time_slot, best_score, decision)
    """
    creator_id = content_item['creator_id']
    content_type = content_item['content_type']
    created_ts = content_item['created_timestamp']
    time_sensitivity = content_item['time_sensitivity']

    best_score = -1.0
    best_platform = None
    best_time_slot = None

    for platform in PLATFORMS:
        for ts in TIME_SLOTS:
            score = compute_score(
                creator_id, platform, content_type, ts,
                creators, activity, engagement
            )
            
            # Deterministic tie-breaking: prefer lower time_slot, then Instagram
            if score > best_score:
                best_score = score
                best_platform = platform
                best_time_slot = ts
            elif score == best_score:
                # Tie-breaking: prefer the option closer to created_timestamp,
                # then prefer Instagram, then prefer lower time_slot
                if ts == created_ts and best_time_slot != created_ts:
                    best_score = score
                    best_platform = platform
                    best_time_slot = ts

    # Scheduling decision
    if best_time_slot == created_ts:
        decision = 'post_now'
    else:
        decision = 'schedule'

    return best_platform, best_time_slot, best_score, decision


def run_optimization(data_dir):
    """
    Main optimization pipeline:
    1. Load all data
    2. For each content item, find optimal platform + time slot
    3. Generate recommendations sorted by content_id
    """
    import os

    # Load data
    print("Loading data...")
    content = load_content(os.path.join(data_dir, 'content.csv'))
    creators = load_creators(os.path.join(data_dir, 'creators.csv'))
    activity = load_platform_activity(os.path.join(data_dir, 'platform_activity.csv'))
    engagement = load_historical_engagement(os.path.join(data_dir, 'historical_engagement.csv'))

    print(f"  Content items: {len(content)}")
    print(f"  Creators: {len(creators)}")
    print(f"  Platform-time combos: {len(activity)}")
    print(f"  Historical engagement records: {len(engagement)}")

    # Optimize each content item
    print("\nOptimizing recommendations...")
    recommendations = []
    total_score = 0.0

    for item in content:
        platform, time_slot, score, decision = optimize_content(
            item, creators, activity, engagement
        )
        recommendations.append({
            'content_id': item['content_id'],
            'platform': platform,
            'time_slot': time_slot,
            'decision': decision,
            'score': score,
            # Metadata for analysis
            'creator_id': item['creator_id'],
            'content_type': item['content_type'],
            'created_timestamp': item['created_timestamp'],
            'time_sensitivity': item['time_sensitivity'],
        })
        total_score += score

    # Sort by content_id for deterministic output
    recommendations.sort(key=lambda x: x['content_id'])

    return recommendations, total_score


# ──────────────────────────────────────────────
# 4. OUTPUT GENERATION
# ──────────────────────────────────────────────

def write_recommendations(recommendations, output_path):
    """Write recommendations CSV in the required format."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['content_id', 'platform', 'time_slot', 'decision'])
        for rec in recommendations:
            writer.writerow([
                rec['content_id'],
                rec['platform'],
                rec['time_slot'],
                rec['decision'],
            ])
    print(f"\nRecommendations written to: {output_path}")


def print_summary(recommendations, total_score):
    """Print detailed summary statistics."""
    print("\n" + "=" * 60)
    print("  OPTIMIZATION RESULTS SUMMARY")
    print("=" * 60)

    # Platform distribution
    ig_count = sum(1 for r in recommendations if r['platform'] == 'Instagram')
    yt_count = sum(1 for r in recommendations if r['platform'] == 'YouTube')
    print(f"\n  Platform Selection:")
    print(f"    Instagram: {ig_count} ({ig_count}%)")
    print(f"    YouTube:   {yt_count} ({yt_count}%)")

    # Decision distribution
    post_now = sum(1 for r in recommendations if r['decision'] == 'post_now')
    schedule = sum(1 for r in recommendations if r['decision'] == 'schedule')
    print(f"\n  Scheduling Decisions:")
    print(f"    Post Now:  {post_now} ({post_now}%)")
    print(f"    Schedule:  {schedule} ({schedule}%)")

    # Content type × platform breakdown
    short_ig = sum(1 for r in recommendations if r['content_type'] == 'SHORT' and r['platform'] == 'Instagram')
    short_yt = sum(1 for r in recommendations if r['content_type'] == 'SHORT' and r['platform'] == 'YouTube')
    long_ig = sum(1 for r in recommendations if r['content_type'] == 'LONG' and r['platform'] == 'Instagram')
    long_yt = sum(1 for r in recommendations if r['content_type'] == 'LONG' and r['platform'] == 'YouTube')
    print(f"\n  Content Type x Platform:")
    print(f"    SHORT -> Instagram: {short_ig}")
    print(f"    SHORT -> YouTube:   {short_yt}")
    print(f"    LONG  -> Instagram: {long_ig}")
    print(f"    LONG  -> YouTube:   {long_yt}")

    # Time slot distribution (peak vs off-peak)
    ig_peak = sum(1 for r in recommendations if r['platform'] == 'Instagram' and 18 <= r['time_slot'] <= 22)
    yt_peak = sum(1 for r in recommendations if r['platform'] == 'YouTube' and 20 <= r['time_slot'] <= 23)
    print(f"\n  Peak Hour Recommendations:")
    print(f"    Instagram peak (18-22): {ig_peak}")
    print(f"    YouTube peak (20-23):   {yt_peak}")

    # Score statistics
    scores = [r['score'] for r in recommendations]
    avg_score = total_score / len(recommendations)
    print(f"\n  Engagement Scores:")
    print(f"    Total:   {total_score:.4f}")
    print(f"    Average: {avg_score:.4f}")
    print(f"    Max:     {max(scores):.4f}")
    print(f"    Min:     {min(scores):.4f}")

    # Top 5 recommendations
    top5 = sorted(recommendations, key=lambda x: x['score'], reverse=True)[:5]
    print(f"\n  Top 5 Highest-Scoring Recommendations:")
    print(f"    {'ID':>4} {'Platform':>10} {'Slot':>4} {'Type':>5} {'Creator':>7} {'Score':>8} {'Decision':>10}")
    print(f"    {'-'*4} {'-'*10} {'-'*4} {'-'*5} {'-'*7} {'-'*8} {'-'*10}")
    for r in top5:
        print(f"    {r['content_id']:>4} {r['platform']:>10} {r['time_slot']:>4} "
              f"{r['content_type']:>5} {r['creator_id']:>7} {r['score']:>8.4f} {r['decision']:>10}")

    print("\n" + "=" * 60)


# ──────────────────────────────────────────────
# 5. VALIDATION
# ──────────────────────────────────────────────

def validate_recommendations(recommendations):
    """Validate that all recommendations conform to expected constraints."""
    errors = []
    valid_platforms = {'Instagram', 'YouTube'}
    valid_decisions = {'post_now', 'schedule'}

    seen_ids = set()
    for rec in recommendations:
        cid = rec['content_id']

        # Check for duplicates
        if cid in seen_ids:
            errors.append(f"Duplicate content_id: {cid}")
        seen_ids.add(cid)

        # Check platform
        if rec['platform'] not in valid_platforms:
            errors.append(f"Content {cid}: invalid platform '{rec['platform']}'")

        # Check time slot range
        if not (0 <= rec['time_slot'] <= 23):
            errors.append(f"Content {cid}: invalid time_slot {rec['time_slot']}")

        # Check decision
        if rec['decision'] not in valid_decisions:
            errors.append(f"Content {cid}: invalid decision '{rec['decision']}'")

    # Check completeness (should have content_ids 1-100)
    expected_ids = set(range(1, 101))
    missing = expected_ids - seen_ids
    if missing:
        errors.append(f"Missing content_ids: {sorted(missing)}")

    if errors:
        print("\n[!] VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("\n[OK] All recommendations passed validation!")
        return True


# ──────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import os

    # Data directory
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'raw')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recommendations.csv')

    # Run optimization
    recommendations, total_score = run_optimization(data_dir)

    # Validate
    validate_recommendations(recommendations)

    # Print summary
    print_summary(recommendations, total_score)

    # Write output
    write_recommendations(recommendations, output_path)

    print(f"\n[DONE] Optimization complete! Total engagement score: {total_score:.4f}")

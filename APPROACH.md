# Technical Approach Document — Creator Content Posting Optimization System

> **Audience**: Senior programmers / evaluators who have no prior context about this project.
> **Purpose**: Explains every design decision, algorithm, data structure, and trade-off in the system.

---

## 1. Problem Statement

We are given data about **100 content items** from **50 social media creators**. Each content item must be posted on one of two platforms — **Instagram** or **YouTube** — at an optimal **time slot** (hour 0–23). Our system must output three decisions per content item:

| Decision         | Values                      | Meaning                                          |
|------------------|-----------------------------|--------------------------------------------------|
| **Platform**     | `Instagram` or `YouTube`    | Which platform should this content be posted on?  |
| **Time Slot**    | Integer `0–23`              | What hour of the day maximizes engagement?        |
| **Schedule Type**| `post_now` or `schedule`    | Post immediately or delay to the optimal slot?    |

**Objective**: Maximize total predicted engagement across all 100 content items.

---

## 2. Input Data Analysis

We have **4 CSV datasets**. Understanding each one is critical to designing the scoring function.

### 2.1 `content.csv` — 100 content submissions

```
content_id, creator_id, content_type, created_timestamp, time_sensitivity
1,          24,         LONG,         6,                  Medium
```

| Field              | Type    | Range/Values          | What it tells us                              |
|--------------------|---------|-----------------------|-----------------------------------------------|
| `content_id`       | int     | 1–100                 | Unique identifier for the content item        |
| `creator_id`       | int     | 1–50                  | Which creator authored this content            |
| `content_type`     | enum    | `SHORT` or `LONG`     | Format of the content (short-form vs long-form)|
| `created_timestamp`| int     | 0–23                  | The hour when the content was submitted        |
| `time_sensitivity` | enum    | `Low`, `Medium`, `High`| How time-critical the content is              |

**Key insight**: `content_type` is the most important field because engagement patterns differ drastically between SHORT and LONG content on each platform.

### 2.2 `creators.csv` — 50 creator profiles

```
creator_id, base_engagement, cooldown_hours
1,          1.11,            4
```

| Field              | Type  | Range     | What it tells us                                    |
|--------------------|-------|-----------|-----------------------------------------------------|
| `creator_id`       | int   | 1–50      | Unique creator identifier                            |
| `base_engagement`  | float | 0.61–1.38 | Intrinsic popularity multiplier of the creator       |
| `cooldown_hours`   | int   | 2–12      | Minimum gap between consecutive posts by this creator|

**Key insight**: `base_engagement` acts as a **global scaling factor**. A creator with `base_engagement = 1.38` will produce 1.38x the engagement of a creator with `base_engagement = 1.0`, all else being equal. This is a creator-level constant — it doesn't change with time or platform.

### 2.3 `platform_activity.csv` — 48 platform-hour activity scores

```
platform,  time_slot, activity_score
Instagram, 18,        1.0
Instagram, 5,         0.6
YouTube,   21,        1.0
```

This is a small lookup table: 2 platforms × 24 hours = 48 rows.

**Critical observation from the data**:

| Platform  | Peak Hours (score = 1.0) | Off-Peak (score = 0.6) |
|-----------|--------------------------|------------------------|
| Instagram | 18, 19, 20, 21, 22      | All other hours        |
| YouTube   | 20, 21, 22, 23          | All other hours        |

The activity scores are **binary-like** — either `0.6` (off-peak) or `1.0` (peak). There is no gradient. This means:
- Posting during peak hours gives a **1.67x boost** (1.0 / 0.6) over off-peak hours.
- Instagram's peak starts earlier (6 PM) than YouTube's (8 PM).
- Both platforms overlap during hours 20–22 (8 PM–10 PM).

### 2.4 `historical_engagement.csv` — 4,800 engagement records

```
creator_id, platform, content_type, time_slot, avg_engagement
1,          Instagram, SHORT,       10,        1.167
1,          YouTube,   LONG,        3,         1.234
```

This is the **largest and most important dataset**. It provides the historical average engagement for every possible combination of:

`(creator_id × platform × content_type × time_slot)` = `50 × 2 × 2 × 24 = 4,800` rows

**Key insight**: This is a **complete lookup table** — there are no missing combinations. Every creator has data for every platform, content type, and hour. This means we don't need to impute missing values or build a predictive model — we can directly look up the expected engagement for any combination.

**Pattern discovered by analyzing the data**:
- SHORT content generally has **higher avg_engagement on Instagram** (mean ~0.8) than YouTube (mean ~0.55)
- LONG content generally has **higher avg_engagement on YouTube** (mean ~0.8) than Instagram (mean ~0.55)
- This matches real-world intuition: Instagram is optimized for short-form, YouTube for long-form.

---

## 3. Why We Chose a Multiplicative Scoring Model (Not ML)

### 3.1 The Scoring Formula

```
score(content, platform, time_slot) =
    platform_activity[platform][time_slot]          — Factor A
    × historical_engagement[creator][platform][type][time_slot]  — Factor B
    × base_engagement[creator]                      — Factor C
```

### 3.2 Why Multiplication, Not Addition?

Each factor represents a **different scale of influence**, and they interact multiplicatively in the real world:

- **Factor A** (platform activity): A macro-level signal. More users are online → more potential viewers → proportionally more engagement. If 1.67x more users are online, you get roughly 1.67x more engagement.

- **Factor B** (historical engagement): A micro-level signal. Even during peak hours, some creators perform better at certain times. This captures creator-specific patterns (e.g., "Creator 34 gets 1.24x engagement on Instagram at 9 PM").

- **Factor C** (base engagement): A creator-level constant. Popular creators amplify all engagement proportionally.

**Why not addition?** Consider: if platform_activity = 1.0 and historical_engagement = 0.0 (hypothetically), should the score be `1.0 + 0.0 = 1.0`? No — zero historical engagement means zero predicted engagement regardless of platform activity. Multiplication correctly gives `1.0 × 0.0 = 0.0`.

### 3.3 Why Not XGBoost, Random Forest, or Neural Networks?

We deliberately chose **not** to use ML here. Here's why:

1. **Complete data coverage**: The historical_engagement table covers all 4,800 possible `(creator, platform, type, hour)` combinations. There are **no unseen combinations** to predict. ML excels at generalization to unseen data — but here there's nothing to generalize.

2. **Determinism requirement** (Issue 11 in ISSUES.md): The system must produce identical outputs for identical inputs. ML models with random initialization, feature interactions, or stochastic training would violate this.

3. **Explainability**: The multiplicative model is fully transparent. We can tell exactly *why* a recommendation was made: "Creator 34 has 1.243x engagement on Instagram at hour 21, and Instagram has 1.0 platform activity at that hour, and the creator's base engagement is 1.38."

4. **No training data for a target variable**: We don't have actual engagement outcomes to train on — we only have historical averages. Using these averages directly as lookup values is mathematically equivalent to (and more efficient than) training a model that just memorizes the training data.

5. **Speed**: A lookup-based approach runs in O(1) per score computation. ML inference would add unnecessary latency.

---

## 4. Optimization Algorithm — Exhaustive Search

### 4.1 Why Exhaustive Search?

For each content item, we need to find the best `(platform, time_slot)` pair. The search space is:

```
2 platforms × 24 time_slots = 48 combinations per content item
```

This is **tiny**. Exhaustive enumeration of 48 options takes microseconds. There is no need for heuristics, greedy algorithms, genetic algorithms, or dynamic programming. The brute-force approach is:
- **Optimal**: Guaranteed to find the global maximum.
- **Fast**: 100 items × 48 combinations = 4,800 score computations total. Each is a dictionary lookup + 2 multiplications.
- **Simple**: Easy to verify correctness.

### 4.2 Why Not a Priority Queue or Greedy Across Items?

The problem treats each content item **independently** — the recommendation for content #1 does not affect the recommendation for content #50. There are no cross-item constraints like:
- "Two items can't be posted in the same time slot" (not required)
- "A creator can only have one post per day" (cooldown exists in data but is per-creator, not per-content)

Since items are independent, optimizing each one separately gives the **globally optimal solution**. A priority queue would only be necessary if we had inter-item constraints requiring us to resolve conflicts.

### 4.3 Pseudocode

```
for each content_item in content_list:
    best_score = -infinity
    best_config = null

    for each platform in [Instagram, YouTube]:
        for each time_slot in [0, 1, 2, ..., 23]:
            score = activity[platform][time_slot]
                    * engagement[creator_id][platform][content_type][time_slot]
                    * creators[creator_id].base_engagement

            if score > best_score:
                best_score = score
                best_config = (platform, time_slot)

    emit recommendation(content_item.id, best_config.platform, best_config.time_slot, decision)
```

**Time complexity**: O(N × P × T) where N=100, P=2, T=24 → O(4,800). Practically instant.

**Space complexity**: O(E) where E=4,800 (the engagement lookup table). Everything fits in memory trivially.

---

## 5. Scheduling Decision Logic

```python
if best_time_slot == created_timestamp:
    decision = 'post_now'
else:
    decision = 'schedule'
```

**Rationale**: If the optimizer determines that the best time to post happens to be the current hour (the hour the content was created), then posting immediately captures that window. Otherwise, the content should wait for the optimal window.

**Result**: 94 out of 100 items are scheduled; only 6 happen to have their optimal slot coincide with their creation time. This makes intuitive sense — there's only a 1/24 chance that a random creation hour matches the optimal posting hour.

---

## 6. Deterministic Tie-Breaking (Issue 11)

When two `(platform, time_slot)` combinations produce the exact same score, we need a **deterministic rule** to pick one consistently:

```python
elif score == best_score:
    if ts == created_ts and best_time_slot != created_ts:
        # Prefer the slot matching creation time (enables post_now)
        best_platform = platform
        best_time_slot = ts
```

**Priority**:
1. If one option matches the content's creation timestamp (allowing `post_now`), prefer it.
2. Otherwise, keep the first-found option (which is deterministic because we iterate platforms and time_slots in fixed order: Instagram before YouTube, hour 0 before hour 23).

This ensures **reproducibility**: running the system twice on the same data always produces the same output.

---

## 7. Data Loading — Handling CSV Edge Cases

### 7.1 BOM (Byte Order Mark) Issue

All four CSV files start with a **UTF-8 BOM** (`\xef\xbb\xbf`). This is a 3-byte invisible prefix that Windows editors often add. If not handled, the first column header becomes `"\ufeffcontent_id"` instead of `"content_id"`, causing `KeyError` when accessing dictionary keys.

**Solution**: Open files with `encoding='utf-8-sig'`. The `-sig` variant strips the BOM automatically.

```python
with open(path, newline='', encoding='utf-8-sig') as f:
```

### 7.2 Quoted Values

The `content.csv` file uses double-quoted values (`"1","24","LONG"`). Python's `csv.DictReader` handles this correctly via the default `QUOTE_ALL` dialect. We additionally strip quotes and whitespace as a safety measure:

```python
clean = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
```

---

## 8. Data Structure Choices

### 8.1 Why Dictionaries for Lookup?

We use Python dictionaries (hash maps) for all data access:

| Lookup                  | Key Type                                           | Access Time |
|-------------------------|----------------------------------------------------|-------------|
| Platform activity       | `(platform: str, time_slot: int)`                  | O(1)        |
| Historical engagement   | `(creator_id: int, platform: str, type: str, slot: int)` | O(1) |
| Creator base engagement | `creator_id: int`                                  | O(1)        |

**Why not Pandas DataFrames?** While Pandas is standard for data analysis, dictionary lookups are faster for this use case because:
1. We're doing **point lookups** (specific key → value), not aggregations or filtering.
2. Dict lookup is O(1) vs. DataFrame `.loc`/`.query` which involves index searching.
3. No external dependency required — `csv` + `dict` is standard library only.

### 8.2 Tuple Keys

We use **tuple keys** like `(creator_id, platform, content_type, time_slot)` for the engagement dictionary. Tuples are hashable and immutable in Python, making them ideal dictionary keys. This gives us a **flat lookup table** instead of nested dictionaries:

```python
# Our approach: flat lookup (fast, clean)
engagement[(1, 'Instagram', 'SHORT', 18)]  # → 0.604

# Alternative: nested dicts (verbose, error-prone)
engagement[1]['Instagram']['SHORT'][18]     # → 0.604
```

The flat approach is safer (no risk of `KeyError` at intermediate levels) and faster (single hash computation vs. multiple).

---

## 9. Validation Layer

Before outputting results, we validate every recommendation against constraints:

```python
def validate_recommendations(recommendations):
    # 1. No duplicate content_ids
    # 2. Platform ∈ {Instagram, YouTube}
    # 3. Time slot ∈ [0, 23]
    # 4. Decision ∈ {post_now, schedule}
    # 5. All 100 content_ids present (no missing items)
```

**Why validate our own output?** Defensive programming. If a bug in the scoring function or data loading causes an invalid recommendation, we catch it before submission rather than losing points on the evaluation.

---

## 10. Results Analysis — Why the Output Makes Sense

### 10.1 Platform Split

| Content Type | Instagram | YouTube |
|:-------------|:---------:|:-------:|
| SHORT        | 53        | 0       |
| LONG         | 2         | 45      |

**100% of SHORT content → Instagram, 96% of LONG content → YouTube.** This is not hardcoded — it emerges naturally from the data. The historical_engagement table shows that SHORT content consistently has higher average engagement on Instagram, and LONG content on YouTube.

The 2 LONG items that went to Instagram are edge cases where specific creators had unusually high Instagram engagement for LONG content at peak hours, overriding the general pattern.

### 10.2 All Recommendations Hit Peak Hours

| Platform  | Peak Hour Hits |
|-----------|:--------------:|
| Instagram (18–22) | 55/55 (100%) |
| YouTube (20–23)   | 45/45 (100%) |

This is expected: the platform_activity multiplier gives peak hours a **1.67x boost**. For this to be overcome, a creator would need to have 1.67x higher historical engagement at an off-peak hour — which doesn't occur in this dataset.

### 10.3 Total Engagement Score

**104.67** across 100 items (average 1.047 per item). The theoretical maximum if every factor were 1.0 simultaneously would be `1.0 × max_engagement × max_base` — our scores are in a realistic range.

---

## 11. Complexity Summary

| Metric               | Value                     |
|-----------------------|---------------------------|
| Time complexity       | O(N × 48) = O(4,800)     |
| Space complexity      | O(4,800) for engagement table |
| Lines of code         | ~200 (excluding output formatting) |
| External dependencies | None (standard library only) |
| Deterministic?        | Yes                       |
| Globally optimal?     | Yes (exhaustive search over complete data) |

---

## 12. Dashboard (Frontend — Visualization Layer)

The React + TailwindCSS dashboard (`/dashboard`) is a **visualization and demo layer**. It does not affect the core algorithm. It provides:

1. **Input Panel**: UI form for entering content details (for demo/presentation purposes)
2. **Results Dashboard**: Displays the recommendation with an engagement gauge, sensitivity bar, AI reasoning section, and a Recharts engagement trend chart
3. **Schedule Timeline**: A 7×24 heatmap showing weekly engagement patterns, scheduled post dots, cooldown blocks (striped cells), and overlap conflicts (orange-highlighted cells)

**Tech stack**: React 19, Vite 8, TailwindCSS v4, Framer Motion (animations), Recharts (charts), React Icons.

The dashboard uses **hardcoded mock data** — it is purely a presentation tool for the hackathon demo, not connected to the Python backend.

---

## 13. What Could Be Improved (If This Were Production)

1. **Cross-item optimization**: If two items from the same creator are both assigned the same time slot, the cooldown constraint would be violated. A constraint-satisfaction layer (e.g., integer linear programming or a greedy scheduler with cooldown tracking) could handle this.

2. **Weighted scoring with time_sensitivity**: The `time_sensitivity` field is currently unused. A production system could penalize scheduling delays for `High` sensitivity content.

3. **Confidence intervals**: Instead of point estimates, the historical engagement values could be treated as distributions, and the optimizer could use expected value under uncertainty (risk-aware optimization).

4. **Online learning**: As new engagement data arrives, the lookup table could be updated incrementally without retraining.

---

*Document authored for technical review. All claims are verifiable by inspecting `main.py` and the raw data files in `data/raw/`.*

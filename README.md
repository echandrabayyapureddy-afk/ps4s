# Creator Content Posting Optimization System

## Team Information
- **Team Name**: [Team Name]
- **Year**: [Year]
- **All-Female Team**: [Yes/No]

## Architecture Overview

Our system uses a **joint platform-time optimization** approach with a multiplicative scoring model. For each content item, we evaluate all 48 combinations (2 platforms x 24 time slots) and select the maximum-scoring option.

**Scoring formula:** `score = platform_activity(platform, slot) x historical_engagement(creator, platform, content_type, slot) x base_engagement(creator)`

**Optimal posting time:** We exhaustively search all 24 hourly slots per platform, leveraging creator-specific historical engagement patterns to find the slot where each creator's content type performs best, amplified by platform peak-hour activity scores.

**Platform selection:** Platform and time slot are jointly optimized rather than decided independently. This captures cross-effects where a suboptimal platform at peak time may outperform the "natural" platform at off-peak time. The data naturally reveals SHORT content favors Instagram and LONG content favors YouTube.

**Balancing activity and history:** The multiplicative scoring model naturally balances both signals. Platform activity acts as a scaling multiplier on creator-specific engagement, so high historical engagement at off-peak times competes with moderate engagement at peak times.

**Schedule vs post_now:** If the optimal time slot matches the content's creation timestamp, we post immediately. Otherwise, we schedule for the predicted optimal window.

---

*Keep your description concise and focused on your core decision-making logic.*

**Note:** Please do not change the format or spelling of anything in this README. The fields are extracted using a script, so any changes to the structure or formatting may break the extraction process.

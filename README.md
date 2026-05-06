Team Information

* Team Name: mix
* Year: 2026
* All-Female Team: No

Architecture Overview
Our system uses a joint platform-time optimization approach with a multiplicative scoring model. For each content itemhttps://github.com/echandrabayyapureddy-afk/ps4s/blob/main/README.md, we evaluate all 48 combinations (2 platforms x 24 time slots) and select the maximum-scoring option.

Scoring formula: `score = platform_activity(platform, slot) x historical_engagement(creator, platform, content_type, slot) x base_engagement(creator)`

Optimal posting time: We exhaustively search all 24 hourly slots per platform using creator-specific historical engagement patterns to identify the highest-performing slot, amplified by platform peak-hour activity scores.

Platform selection: Platform and time slot are jointly optimized. This captures cross-effects where a suboptimal platform at peak time may outperform the natural platform at off-peak time. SHORT content favors Instagram; LONG content favors YouTube.

Balancing activity and history: The multiplicative model naturally balances both signals. Platform activity scales creator-specific engagement, so strong off-peak historical performance competes directly with moderate peak-hour engagement.

Schedule vs post_now: If the optimal time slot matches the content's creation timestamp, we post immediately. Otherwise, we schedule for the predicted optimal window.

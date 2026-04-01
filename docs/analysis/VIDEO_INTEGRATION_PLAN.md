# Video Insights Integration Plan

**Status:** ❌ **NOT INTEGRATED** - Agent does not use video insights
**Date:** March 31, 2026

---

## Current State Assessment

### What's NOT Connected:
- ✅ **340 video insights** stored in PostgreSQL
- ✅ **38 documented trade setups** with entry/exit criteria
- ✅ **2,918 extracted chart frames** with timestamps
- ❌ **Agent doesn't query database** - no psycopg2 imports
- ❌ **Scoring system is static** - hardcoded in `memories.py`
- ❌ **No setup validation** against documented examples
- ❌ **Psychology insights unused** - 29 mental game principles ignored

### Current Agent Architecture:
```python
# agent.py flow:
1. Pre-flight checks (market hours, killzones)
2. Get HTF bias (Monthly → Weekly → Daily)
3. Scan intraday (15m → 5m → 1m)
4. Score setup → score_setup()
5. If score >= 80 → Execute trade
```

**Scoring System (`memories.py`):**
```python
SCORE_CRITERIA = {
    "liquidity_sweep": 20,
    "market_structure_shift": 20,
    "fvg_present": 15,
    "displacement": 10,
    ...
}
```

**Problem:** Static scoring, no learning from video insights.

---

## Integration Strategy

### Phase 1: Database Connection (Foundation)
**Goal:** Enable agent to query video insights database

**Changes:**
1. Add PostgreSQL connection to agent
2. Create `video_insights_loader.py` module
3. Add caching layer (don't query DB every scan)

**Files to Create:**
- `video_insights_loader.py` - Query interface
- `video_cache.json` - Cached insights (refresh daily)

**Files to Modify:**
- `agent.py` - Import insights loader
- `requirements.txt` - Add `psycopg2-binary`
- `.env` - Already has `DATABASE_URL` ✓

---

### Phase 2: Setup Validation (Match Video Examples)
**Goal:** Validate current setup matches documented trade patterns

**What to Add:**
```python
def validate_against_video_trades(
    symbol: str,
    direction: str,
    setup_type: str,
    entry_price: float,
    weekly_context: dict
) -> dict:
    """
    Query video_trades table for similar setups.
    Return: {
        "matches_found": int,
        "success_rate": float,
        "similar_trades": list[dict],
        "validation_score": int  # 0-10 bonus points
    }
    """
```

**Use Case:**
- Agent detects FVG entry setup
- Query DB: "Show me 12 documented FVG_entry trades"
- Check if current setup matches entry criteria
- Add +5 bonus points if validated against video examples

**SQL Query:**
```sql
SELECT setup_type, entry_criteria, notes, result
FROM video_trades
WHERE setup_type = 'FVG_entry'
AND direction = 'short'
LIMIT 10;
```

---

### Phase 3: Dynamic Confluence Scoring
**Goal:** Add bonus points when setup has learned confluence factors

**New Scoring Component:**
```python
VIDEO_INSIGHT_BONUS = {
    "matches_documented_setup": 10,      # Setup in video_trades
    "has_learned_confluence": 5,         # Multiple video principles apply
    "timeframe_alignment_confirmed": 5,  # HTF→LTF matches video insight
    "entry_timing_validated": 5,         # Matches entry_timing principles
}
```

**Example:**
```
Current setup:
- FVG entry detected ✓
- 4H bearish bias ✓
- 15m entry timing ✓
- Liquidity sweep ✓

Query video_insights:
- Found 12 FVG_entry examples → +10 pts
- Found "HTF bias + LTF entry" principle → +5 pts
- Found "liquidity_sweep + FVG" confluence → +5 pts

Total bonus: +20 pts
Final score: 75 (base) + 20 (HTF) + 20 (video) = 115
```

---

### Phase 4: Pre-Trade Psychology Checks
**Goal:** Display relevant mental game reminders before execution

**What to Add:**
```python
def get_psychology_reminders(score: int, setup_type: str) -> list[str]:
    """
    Query video_insights where category = 'psychology'
    and tags match current situation.

    Return top 3 most relevant reminders.
    """
```

**Use Case:**
Agent about to execute trade → Show:
```
⚠️ Psychology Reminders:
1. "You do not gain intelligence while in a trade.
    Plan the trade BEFORE clicking."
2. "If you can't recall specific trade details after,
    you lack process and discipline."
3. "Avoid chasing trades due to FOMO - this often
    leads to poor outcomes."
```

**SQL Query:**
```sql
SELECT description, evidence, confidence
FROM video_insights
WHERE category = 'psychology'
AND (
    tags @> ARRAY['FOMO']
    OR tags @> ARRAY['discipline']
    OR tags @> ARRAY['trading psychology']
)
ORDER BY confidence DESC
LIMIT 3;
```

---

### Phase 5: Market Structure Rules Enforcement
**Goal:** Validate HTF/LTF usage matches video principles

**Key Insight from Videos:**
> "High timeframe = BIAS, Low timeframe = ENTRY"

**What to Add:**
```python
def validate_timeframe_usage(
    htf_bias_timeframe: str,
    ltf_entry_timeframe: str,
    setup_direction: str
) -> dict:
    """
    Check if timeframe usage matches 151 market_structure insights.

    Returns:
        validated: bool,
        violations: list[str],
        recommendations: list[str]
    """
```

**Validation Rules from Videos:**
- If day trading: Bias must come from 4H+ (not 15m)
- Entry must be lower TF than bias (15m entry needs 4H bias)
- Expected move speed must match timeframe

**Example Violation:**
```
❌ Invalid Setup Rejected:
- Bias: 15-minute chart (TOO LOW)
- Entry: 15-minute chart (SAME AS BIAS)

Video Insight Match:
"High timeframe analysis is used to identify a trading
bias, while low timeframes are used for entry execution
for day trading." (Confidence: 100%)

Required Fix:
- Use 4H for bias
- Use 15m/5m for entry
```

---

### Phase 6: Entry Timing Optimization
**Goal:** Apply 49 entry_timing insights to improve entry precision

**Key Insights to Apply:**

**1. Multiple Entry Opportunities**
> "Once liquidity is swept and reversal signal present,
> multiple entry opportunities arise."

**Implementation:**
```python
def find_multiple_entries(
    liquidity_swept: bool,
    reversal_confirmed: bool,
    timeframe: str
) -> list[dict]:
    """
    Don't panic and take first candle.
    Look for:
    - FVG entries
    - MSS entries
    - Order block entries
    """
```

**2. 8:30 AM Bias Formulation**
> "8:30 AM is considered a key pre-market time."

**Implementation:**
```python
def check_830_economic_data() -> dict:
    """
    Query economic calendar at 8:30 AM.
    Adjust bias based on data releases.
    """
```

**3. 9:30 Open Reference**
> "The open price of 9:30 AM candle can be used
> as reference for precise entries."

**Implementation:**
```python
def get_930_open_price(symbol: str) -> float:
    """
    Fetch 1-minute bar at 9:30 AM.
    Use open price as key level.
    """
```

---

### Phase 7: Risk Management from Videos
**Goal:** Apply 37 risk_management principles

**Key Principles:**
- Position sizing based on account risk
- Stops at structural levels, not arbitrary
- Targets at opposing liquidity
- Never risk more than emotionally manageable

**What to Add:**
```python
def validate_risk_parameters(
    entry: float,
    stop: float,
    target: float,
    position_size: int,
    account_equity: float
) -> dict:
    """
    Validate against 37 risk_management insights.

    Check:
    - Stop is at structural level (not 1.5x ATR arbitrary)
    - Target is at liquidity pool
    - R:R matches documented examples
    - Position size aligns with video principles
    """
```

---

### Phase 8: Setup Library Reference
**Goal:** Link current setup to documented video examples

**What to Add:**
```python
def get_similar_setups(
    current_setup: dict,
    symbol: str,
    direction: str,
    timeframe: str
) -> list[dict]:
    """
    Query video_trades for similar setups.

    Return:
    - Trade notes from videos
    - Entry/exit criteria
    - Result (win/loss if documented)
    - Frame references (chart images)
    """
```

**Use Case:**
Agent detects liquidity sweep → short SPY setup

**Query returns:**
```
📚 Similar Video Examples (3 found):

1. Liquidity Sweep → FVG Short (Video #2)
   "Price sweeps lunch high (buy-side liquidity),
    reversal signal appears, market structure breaks
    down, entry in 5m FVG, target Asia low."
   Result: Not documented
   Frame: data/frames/2/frame_001245.3s.jpg

2. Liquidity Sweep Short (Video #4)
   "Explained reasoning for taking short based on
    liquidity sweep of buy-side liquidity and
    targeting opposing liquidity (Asia low)."
   Result: Not documented

3. Order Block Short (Video #3)
   "Order block on 15-minute chart acts as potential
    entry for short trade targeting Asia lows."
   Result: Not documented
```

---

## Implementation Phases (Prioritized)

### ✅ Phase 1: Foundation (CRITICAL)
**Priority:** HIGH
**Effort:** 1-2 hours
**Impact:** Enables all other phases

**Tasks:**
1. Create `video_insights_loader.py`
2. Add PostgreSQL connection
3. Implement caching layer
4. Test database queries

**Deliverables:**
- Working DB connection
- Cached insights JSON
- Query functions for each table

---

### ✅ Phase 2: Setup Validation (HIGH VALUE)
**Priority:** HIGH
**Effort:** 2-3 hours
**Impact:** Immediate scoring improvement

**Tasks:**
1. Implement `validate_against_video_trades()`
2. Add +10 bonus when setup matches videos
3. Log matched examples in journal
4. Test with current market conditions

**Deliverables:**
- Setup validation function
- Enhanced scoring with video bonus
- Journal entries show matched examples

---

### ✅ Phase 3: Dynamic Confluence (MEDIUM VALUE)
**Priority:** MEDIUM
**Effort:** 3-4 hours
**Impact:** More nuanced scoring

**Tasks:**
1. Query confluence insights
2. Add bonus scoring for multiple factors
3. Weight by confidence scores
4. Update memories.py with VIDEO_INSIGHT_BONUS

**Deliverables:**
- Confluence checking function
- Updated scoring system
- Test results showing bonus application

---

### ✅ Phase 4: Psychology Reminders (QUALITY OF LIFE)
**Priority:** MEDIUM
**Effort:** 1-2 hours
**Impact:** Better discipline, fewer mistakes

**Tasks:**
1. Create `get_psychology_reminders()`
2. Display pre-trade
3. Log in journal
4. Add optional --show-psychology flag

**Deliverables:**
- Psychology reminder system
- Pre-trade display
- Journal documentation

---

### ✅ Phase 5: Timeframe Validation (PREVENTS ERRORS)
**Priority:** MEDIUM
**Effort:** 2-3 hours
**Impact:** Catches invalid setups early

**Tasks:**
1. Implement `validate_timeframe_usage()`
2. Add hard rules from 151 market_structure insights
3. Reject invalid setups
4. Log violations

**Deliverables:**
- Timeframe validation function
- Setup rejection when invalid
- Clear error messages citing video insights

---

### ⏳ Phase 6: Entry Timing (ADVANCED)
**Priority:** LOW
**Effort:** 3-4 hours
**Impact:** Better entry precision

**Tasks:**
1. 8:30 economic data checker
2. 9:30 open price reference
3. Multiple entry opportunity scanner
4. Apply 49 entry_timing principles

**Deliverables:**
- Enhanced entry timing logic
- Economic calendar integration
- Multiple entry detection

---

### ⏳ Phase 7: Risk Management (ADVANCED)
**Priority:** LOW
**Effort:** 2-3 hours
**Impact:** Better trade management

**Tasks:**
1. Structural stop validation
2. Liquidity target validation
3. R:R verification
4. Apply 37 risk_management insights

**Deliverables:**
- Risk validation function
- Improved stop/target placement
- Risk parameter checks

---

### ⏳ Phase 8: Setup Library (NICE TO HAVE)
**Priority:** LOW
**Effort:** 2-3 hours
**Impact:** Educational/reference

**Tasks:**
1. Similar setup finder
2. Link to chart frames
3. Display in journal
4. Optional --show-examples flag

**Deliverables:**
- Setup library viewer
- Frame references
- Enhanced journal entries

---

## Technical Implementation Details

### 1. Database Connection Module

**File:** `video_insights_loader.py`

```python
#!/usr/bin/env python3
"""
Video insights database loader.

Queries PostgreSQL for trading insights extracted from Mastermind videos.
Implements caching to avoid hitting DB on every agent scan.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = Path(__file__).parent / "journal" / "video_insights_cache.json"
CACHE_TTL_HOURS = 24  # Refresh daily

class VideoInsightsLoader:
    """Lazy-loading singleton for video insights."""

    _instance = None
    _cache = None
    _last_loaded = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_connection(self):
        """Create PostgreSQL connection."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return None
        return psycopg2.connect(db_url)

    def _load_from_cache(self) -> Optional[dict]:
        """Load from cache if fresh."""
        if not CACHE_FILE.exists():
            return None

        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)

        loaded_at = datetime.fromisoformat(cache["loaded_at"])
        age = datetime.now() - loaded_at

        if age < timedelta(hours=CACHE_TTL_HOURS):
            return cache["data"]

        return None

    def _save_to_cache(self, data: dict):
        """Save to cache file."""
        cache = {
            "loaded_at": datetime.now().isoformat(),
            "data": data
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)

    def load(self) -> dict:
        """
        Load video insights with caching.

        Returns dict with:
        - insights_by_category: {category: [insights]}
        - trades_by_setup: {setup_type: [trades]}
        - psychology_reminders: [insights]
        - market_structure_rules: [insights]
        - entry_timing_rules: [insights]
        """
        # Try cache first
        cached = self._load_from_cache()
        if cached:
            return cached

        # Load from database
        conn = self._get_connection()
        if not conn:
            return self._empty_data()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Load insights by category
                cur.execute("""
                    SELECT category, description, evidence,
                           confidence, tags
                    FROM video_insights
                    ORDER BY confidence DESC
                """)
                insights = cur.fetchall()

                # Load trades by setup type
                cur.execute("""
                    SELECT setup_type, direction, entry_criteria,
                           exit_criteria, notes, result
                    FROM video_trades
                    WHERE setup_type IS NOT NULL
                    ORDER BY created_at DESC
                """)
                trades = cur.fetchall()

            # Organize data
            data = self._organize_data(insights, trades)

            # Cache it
            self._save_to_cache(data)

            return data

        finally:
            conn.close()

    def _organize_data(self, insights: list, trades: list) -> dict:
        """Organize insights and trades into useful structure."""
        data = {
            "insights_by_category": {},
            "trades_by_setup": {},
            "psychology_reminders": [],
            "market_structure_rules": [],
            "entry_timing_rules": [],
            "risk_management_rules": [],
            "confluence_factors": [],
            "total_insights": len(insights),
            "total_trades": len(trades),
        }

        # Group insights by category
        for insight in insights:
            cat = insight["category"]
            if cat not in data["insights_by_category"]:
                data["insights_by_category"][cat] = []
            data["insights_by_category"][cat].append(dict(insight))

            # Also add to specific lists
            if cat == "psychology":
                data["psychology_reminders"].append(dict(insight))
            elif cat == "market_structure":
                data["market_structure_rules"].append(dict(insight))
            elif cat == "entry_timing":
                data["entry_timing_rules"].append(dict(insight))
            elif cat == "risk_management":
                data["risk_management_rules"].append(dict(insight))
            elif cat == "confluence":
                data["confluence_factors"].append(dict(insight))

        # Group trades by setup type
        for trade in trades:
            setup = trade["setup_type"]
            if setup not in data["trades_by_setup"]:
                data["trades_by_setup"][setup] = []
            data["trades_by_setup"][setup].append(dict(trade))

        return data

    def _empty_data(self) -> dict:
        """Return empty structure if DB unavailable."""
        return {
            "insights_by_category": {},
            "trades_by_setup": {},
            "psychology_reminders": [],
            "market_structure_rules": [],
            "entry_timing_rules": [],
            "risk_management_rules": [],
            "confluence_factors": [],
            "total_insights": 0,
            "total_trades": 0,
        }


# Singleton instance
_loader = VideoInsightsLoader()

def get_video_insights() -> dict:
    """Get cached video insights."""
    return _loader.load()

def get_matching_trades(setup_type: str, direction: str = None) -> list[dict]:
    """Get video trades matching setup type and direction."""
    insights = get_video_insights()
    matches = insights["trades_by_setup"].get(setup_type, [])

    if direction:
        matches = [t for t in matches if t.get("direction") == direction]

    return matches

def get_psychology_reminders(limit: int = 3) -> list[dict]:
    """Get top psychology insights."""
    insights = get_video_insights()
    return insights["psychology_reminders"][:limit]

def validate_setup_against_videos(
    setup_type: str,
    direction: str,
    confidence: int
) -> dict:
    """
    Validate current setup against documented video examples.

    Returns:
        matches_found: int
        validation_score: int (0-10 bonus points)
        similar_trades: list[dict]
    """
    matches = get_matching_trades(setup_type, direction)

    validation_score = 0
    if len(matches) >= 3:
        validation_score = 10  # Strong validation
    elif len(matches) >= 1:
        validation_score = 5   # Some validation

    return {
        "matches_found": len(matches),
        "validation_score": validation_score,
        "similar_trades": matches[:5],  # Top 5
    }
```

---

### 2. Enhanced Scoring with Video Validation

**File:** `agent.py` (modifications)

```python
# Add near top of file
from video_insights_loader import (
    get_video_insights,
    validate_setup_against_videos,
    get_psychology_reminders,
)

# In score_setup() function, after HTF bonus calculation:

# ── Video insights validation bonus ──────────────────────────────
video_bonus = 0
video_details = {}

try:
    # Map detected setup to video setup types
    setup_type_map = {
        "ema_pullback_long": "FVG_entry",
        "ema_bounce_short": "FVG_entry",
        "oversold_reversal": "liquidity_sweep",
        "overbought_reversal": "liquidity_sweep",
    }

    video_setup_type = setup_type_map.get(setup, setup)

    validation = validate_setup_against_videos(
        setup_type=video_setup_type,
        direction=side,
        confidence=analysis["confidence"]
    )

    video_bonus += validation["validation_score"]
    video_details = {
        "matches_found": validation["matches_found"],
        "validation_score": validation["validation_score"],
        "examples": validation["similar_trades"][:2],  # Top 2
    }

except Exception as e:
    print(f"    ⚠ Video validation error: {e}")

# Add video bonus to total (cap at 10)
video_bonus = min(video_bonus, 10)
total_with_video = total_with_htf + video_bonus

return (total_with_video, checks, {
    "htf": htf_details,
    "video": video_details,
})
```

---

### 3. Pre-Trade Psychology Display

**File:** `agent.py` (in execute_trade section)

```python
# Before executing trade, show psychology reminders
def show_psychology_check():
    """Display pre-trade psychology reminders."""
    reminders = get_psychology_reminders(limit=3)

    if reminders:
        print("\n  ⚠️  Psychology Check:")
        for i, reminder in enumerate(reminders, 1):
            desc = reminder["description"]
            # Truncate if too long
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"     {i}. {desc}")
        print()

# Call before execution
show_psychology_check()
```

---

## Success Metrics

### Quantitative:
- **Setup match rate:** % of trades that match documented video examples
- **Score improvement:** Average score increase with video bonus
- **Validation accuracy:** % of validated setups that win vs unvalidated

### Qualitative:
- **Better discipline:** Psychology reminders reduce impulsive trades
- **Clearer reasoning:** Journal shows video example references
- **Confidence:** Trader knows setup matches 340 learned principles

---

## Rollout Plan

### Week 1: Foundation
- Implement Phase 1 (DB connection + caching)
- Test queries and cache refresh
- Verify no performance impact

### Week 2: Core Features
- Implement Phase 2 (Setup validation)
- Implement Phase 4 (Psychology reminders)
- Test in dry-run mode

### Week 3: Advanced Features
- Implement Phase 3 (Confluence scoring)
- Implement Phase 5 (Timeframe validation)
- Monitor results

### Week 4+: Refinement
- Add remaining phases as needed
- Tune bonus scoring weights
- Collect feedback

---

## Risks & Mitigation

### Risk 1: Database Connection Failure
**Impact:** Agent can't query insights
**Mitigation:** Caching layer + graceful fallback to static scoring

### Risk 2: Performance Degradation
**Impact:** Agent scans take too long
**Mitigation:** Cache insights for 24h, only query once per day

### Risk 3: Over-Reliance on Videos
**Impact:** Agent only takes setups from videos
**Mitigation:** Video bonus capped at +10, base scoring still primary

### Risk 4: False Confidence
**Impact:** Trader assumes all validated setups will win
**Mitigation:** Show match count, not win rate (only 2 wins documented)

---

## Next Steps

1. **Review plan with user**
2. **Get approval for Phase 1-2**
3. **Implement foundation (video_insights_loader.py)**
4. **Test database connection**
5. **Add setup validation to agent.py**
6. **Run dry-run tests**
7. **Deploy to production**

---

## Questions to Answer

1. Should video bonus count toward A+ threshold (80) or be additive?
2. What weight for each phase? (Phase 2 = +10, Phase 3 = +5, etc.)
3. Show psychology reminders on every trade or only sub-80 scores?
4. Log matched video examples in journal or just count?
5. Auto-refresh cache daily or manual refresh command?

---

**Recommendation:** Start with **Phase 1 + Phase 2** (Foundation + Setup Validation)

**Effort:** 3-5 hours total
**Impact:** Immediate scoring improvement + validation against 38 documented examples
**Risk:** Low (caching prevents performance issues)

Ready to implement?

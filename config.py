"""
Central config for the outbound engine.
Target market: recently funded UK tech startups that are building a sales team.
Edit the ICP (ideal customer profile) here as you learn what converts.
"""
import os

# ---------- API keys (set these as environment variables, never hard-code) ----------
COMPANIES_HOUSE_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN", "")

# ---------- Targeting ----------
# 62012 business & domestic software development, 62020 IT consultancy,
# 62090 other IT services, 63110 data processing/hosting, 58290 other software publishing
SIC_CODES = ["62012", "58290", "63110", "62090", "62020"]

# Startups: incorporated within this window (older = less likely to be building a first sales team)
INCORPORATED_FROM = "2018-01-01"
INCORPORATED_TO = "2025-06-30"

# ---------- Funding signal (from Companies House filing history) ----------
# An SH01 filing = new shares allotted. For startups this usually means a funding round
# (but can also be option exercises or founder top-ups, so the LLM + you review it).
FUNDING_LOOKBACK_DAYS = 365          # only fetch full details for companies with an SH01 in this window
FUNDING_RECENCY_POINTS = [           # (max days since last SH01, points)
    (90, 35),
    (180, 25),
    (365, 10),
]
MULTIPLE_ALLOTMENTS_POINTS = 10      # 2+ SH01s in the window: active cap table, likely a priced round

# Companies House accounts type as a rough size proxy
ACCOUNTS_TYPE_POINTS = {
    "micro-entity": -5,
    "total-exemption-small": 5,
    "total-exemption-full": 5,
    "small": 10,
    "medium": 10,
    "full": 0,
    "group": -10,   # big groups have RevOps teams already
}

# ---------- Signals found on the company website / careers page ----------
WEBSITE_SIGNALS = {
    "hiring_first_sales": {
        "keywords": ["sales development representative", "sdr", "bdr", "business development representative",
                     "founding account executive", "founding ae", "first sales hire", "account executive"],
        "points": 25,
        "why": "Hiring sales reps: they need pipeline for them to work",
    },
    "hiring_sales_leader": {
        "keywords": ["head of sales", "vp sales", "head of growth", "head of revenue", "sales lead"],
        "points": 20,
        "why": "Hiring a sales leader: building the GTM function now",
    },
    "b2b_motion": {
        "keywords": ["book a demo", "request a demo", "talk to sales", "contact sales", "get a demo"],
        "points": 10,
        "why": "Sales-led B2B motion, so outbound matters to them",
    },
    "founder_led_sales": {
        "keywords": ["book a call with our founder", "speak to the founders", "calendly.com"],
        "points": 10,
        "why": "Founders still selling themselves: classic moment to systemise outbound",
    },
    # Negative: they've already got this covered
    "has_gtm_engineering": {
        "keywords": ["gtm engineer", "revops engineer", "revenue operations manager", "growth engineer"],
        "points": -50,
        "why": "Already has (or is hiring) GTM engineering / RevOps, so they don't need us",
    },
}

# Accounts scoring at or above this go to HubSpot and get a personalised first line
QUALIFY_THRESHOLD = 50

# ---------- Who you're targeting and what you're offering (used in the AI prompt) ----------
TARGET_DESCRIPTION = "recently funded UK B2B tech startups that are building their first sales team"
OFFER = (
    "I build signal-based outbound systems: an automated pipeline that finds companies showing "
    "buying signals, scores them, writes personalised openers and syncs them to the CRM, "
    "so a new sales team has qualified pipeline from week one."
)

ANTHROPIC_MODEL = "claude-sonnet-5-5"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

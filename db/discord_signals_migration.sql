-- Discord Signals Enhancement Migration
-- Adds channel tracking and signal extraction tables

-- ═══ DISCORD CHANNELS ═══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS discord_channels (
    id            BIGINT PRIMARY KEY,          -- Discord channel ID
    name          TEXT NOT NULL,               -- Channel name (stock-alerts, day-trade-alerts, swings)
    guild_id      BIGINT NOT NULL,             -- Server/Guild ID
    description   TEXT,                        -- Channel description
    priority      TEXT DEFAULT 'medium',       -- high, medium, low
    enabled       BOOLEAN DEFAULT TRUE,        -- Active monitoring flag
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ DISCORD SIGNALS (EXTRACTED FROM MESSAGES) ══════════════════════════════

CREATE TABLE IF NOT EXISTS discord_signals (
    id               SERIAL PRIMARY KEY,
    message_id       BIGINT REFERENCES discord_messages(id) ON DELETE CASCADE,
    channel_id       BIGINT REFERENCES discord_channels(id),
    extracted_at     TIMESTAMPTZ DEFAULT NOW(),

    -- Signal Classification
    signal_type      TEXT NOT NULL,           -- market_analysis, price_target, trade_call, risk_warning
    confidence       TEXT NOT NULL,           -- high, medium, low
    time_horizon     TEXT,                    -- short_term, medium_term, long_term

    -- Symbols & Sentiment
    symbols          TEXT[] NOT NULL,         -- ['SPY', 'QQQ']
    sentiment        TEXT NOT NULL,           -- bullish, bearish, neutral, mixed

    -- Price Levels
    support_levels   JSONB,                   -- {'SPY': [613, 590], 'QQQ': [540, 520]}
    resistance_levels JSONB,                  -- {'SPY': [670, 690], 'QQQ': [600, 620]}
    price_targets    JSONB,                   -- {'SPY': {'short': 613, 'long': 590}}

    -- Context & Insights
    key_insights     TEXT[],                  -- Array of extracted insights
    risk_factors     TEXT[],                  -- Array of risk mentions
    catalysts        TEXT[],                  -- Events that could trigger moves
    regime_context   TEXT,                    -- correction, bear_market, bull_market, etc.

    -- Technical Analysis Mentions
    technical_levels JSONB,                   -- {type: '300MA', level: 538, symbol: 'QQQ'}
    volume_context   TEXT,                    -- high_volume, low_volume, etc.

    -- Valuation Context
    valuation_notes  TEXT,                    -- PE ratios, fundamental mentions
    sector_context   TEXT,                    -- Sector rotation info

    -- Agent Interaction
    expires_at       TIMESTAMPTZ,             -- When signal becomes stale
    applied_to_trades TEXT[],                 -- Array of trade IDs influenced
    score_impact     JSONB,                   -- {trade_id: bonus_points}

    -- Metadata
    raw_text_snippet TEXT,                    -- First 500 chars for reference
    extraction_method TEXT DEFAULT 'pattern', -- pattern, llm, hybrid
    extraction_version TEXT,                  -- Version of extraction logic

    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ SIGNAL PERFORMANCE TRACKING ═════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS signal_performance (
    id               SERIAL PRIMARY KEY,
    signal_id        INTEGER REFERENCES discord_signals(id) ON DELETE CASCADE,
    trade_id         TEXT NOT NULL,           -- Reference to agent trade
    symbol           TEXT NOT NULL,

    -- Signal Details at Trade Time
    signal_sentiment TEXT NOT NULL,
    signal_confidence TEXT NOT NULL,
    score_bonus      INTEGER NOT NULL,        -- Points added by signal

    -- Trade Outcome
    trade_direction  TEXT NOT NULL,           -- buy, sell
    entry_price      FLOAT NOT NULL,
    exit_price       FLOAT,
    pnl              FLOAT,
    result           TEXT,                    -- win, loss, breakeven

    -- Performance Metrics
    signal_accuracy  TEXT,                    -- correct, incorrect, neutral
    distance_to_target FLOAT,                 -- How close to predicted level

    -- Timing
    signal_age_minutes INTEGER,               -- Age of signal when used
    trade_opened_at  TIMESTAMPTZ NOT NULL,
    trade_closed_at  TIMESTAMPTZ,

    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ AUTHOR CREDIBILITY TRACKING ═════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS signal_author_stats (
    id               SERIAL PRIMARY KEY,
    author_id        BIGINT NOT NULL,
    author_name      TEXT NOT NULL,

    -- Signal Stats
    total_signals    INTEGER DEFAULT 0,
    signals_used     INTEGER DEFAULT 0,       -- Signals that influenced trades

    -- Accuracy Metrics
    correct_calls    INTEGER DEFAULT 0,
    incorrect_calls  INTEGER DEFAULT 0,
    accuracy_rate    FLOAT,

    -- Influence Score
    avg_score_bonus  FLOAT,                   -- Average bonus points provided
    total_pnl_impact FLOAT,                   -- Total P&L from trades influenced

    -- Specialization
    best_symbols     TEXT[],                  -- Symbols they're most accurate on
    best_sentiment   TEXT,                    -- bullish or bearish accuracy

    last_signal_at   TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ INDEXES ═══════════════════════════════════════════════════════════════════

CREATE INDEX idx_discord_signals_symbols
    ON discord_signals USING GIN(symbols);

CREATE INDEX idx_discord_signals_active
    ON discord_signals(expires_at)
    WHERE expires_at > NOW();

CREATE INDEX idx_discord_signals_channel
    ON discord_signals(channel_id, extracted_at DESC);

CREATE INDEX idx_discord_signals_sentiment
    ON discord_signals(sentiment, confidence);

CREATE INDEX idx_signal_performance_symbol
    ON signal_performance(symbol, result);

CREATE INDEX idx_signal_performance_accuracy
    ON signal_performance(signal_accuracy, created_at DESC);

CREATE INDEX idx_signal_author_stats_accuracy
    ON signal_author_stats(accuracy_rate DESC, total_signals DESC);

-- ═══ VIEWS ══════════════════════════════════════════════════════════════════════

-- Active signals ready for agent consumption
CREATE OR REPLACE VIEW active_discord_signals AS
SELECT
    s.id,
    s.message_id,
    c.name as channel_name,
    s.symbols,
    s.sentiment,
    s.confidence,
    s.time_horizon,
    s.support_levels,
    s.resistance_levels,
    s.key_insights,
    s.risk_factors,
    s.expires_at,
    m.author_name,
    m.content as full_message,
    EXTRACT(EPOCH FROM (NOW() - s.extracted_at))/60 as age_minutes
FROM discord_signals s
JOIN discord_messages m ON s.message_id = m.id
JOIN discord_channels c ON s.channel_id = c.id
WHERE s.expires_at > NOW()
  AND c.enabled = TRUE
ORDER BY s.extracted_at DESC;

-- Signal effectiveness summary
CREATE OR REPLACE VIEW signal_effectiveness AS
SELECT
    s.channel_id,
    c.name as channel_name,
    s.sentiment,
    s.confidence,
    COUNT(*) as total_signals,
    COUNT(DISTINCT sp.trade_id) as trades_influenced,
    AVG(sp.score_bonus) as avg_bonus,
    SUM(CASE WHEN sp.result = 'win' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN sp.result = 'loss' THEN 1 ELSE 0 END) as losses,
    AVG(CASE WHEN sp.result IN ('win', 'loss')
        THEN CASE WHEN sp.result = 'win' THEN 1.0 ELSE 0.0 END
        ELSE NULL END) as win_rate,
    AVG(sp.pnl) as avg_pnl
FROM discord_signals s
LEFT JOIN signal_performance sp ON s.id = sp.signal_id
JOIN discord_channels c ON s.channel_id = c.id
GROUP BY s.channel_id, c.name, s.sentiment, s.confidence;

-- Top performing signal authors
CREATE OR REPLACE VIEW top_signal_authors AS
SELECT
    author_name,
    total_signals,
    signals_used,
    accuracy_rate,
    avg_score_bonus,
    total_pnl_impact,
    best_symbols,
    last_signal_at
FROM signal_author_stats
WHERE total_signals >= 5  -- Minimum sample size
ORDER BY accuracy_rate DESC, total_signals DESC
LIMIT 20;

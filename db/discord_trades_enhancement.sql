-- Discord Trade Lifecycle Tracking Enhancement
-- Handles multi-message trade sequences

-- ═══ TRADE LIFECYCLE TABLE ══════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS discord_trade_lifecycle (
    id                  SERIAL PRIMARY KEY,

    -- Trade Identification
    symbol              TEXT NOT NULL,              -- ES, SPY, QQQ, etc.
    author_id           BIGINT NOT NULL,
    author_name         TEXT NOT NULL,
    channel_id          BIGINT NOT NULL,

    -- Trade State
    status              TEXT NOT NULL DEFAULT 'open', -- open, partial_close, closed, stopped
    direction           TEXT NOT NULL,              -- long, short

    -- Entry Details (from first message)
    entry_message_id    BIGINT REFERENCES discord_messages(id),
    entry_price         FLOAT,
    entry_timestamp     TIMESTAMPTZ NOT NULL,
    entry_reasoning     TEXT,
    chart_entry_path    TEXT,                       -- Screenshot path

    -- Stop Loss / Take Profit (from chart or text)
    stop_loss           FLOAT,
    take_profit_1       FLOAT,
    take_profit_2       FLOAT,
    take_profit_final   FLOAT,

    -- Position Size
    contracts           INTEGER,
    position_size       FLOAT,

    -- Exit Details
    exit_message_ids    BIGINT[],                   -- Array of exit message IDs
    exit_prices         FLOAT[],                    -- Array of exit prices (partial exits)
    exit_timestamps     TIMESTAMPTZ[],
    exit_reasons        TEXT[],                     -- ['partial_profit', 'target_hit', 'stopped']

    -- P&L Tracking
    pnl_updates         JSONB,                      -- {message_id: pnl_amount}
    total_pnl           FLOAT,
    final_pnl           FLOAT,

    -- Screenshots
    chart_screenshots   TEXT[],                     -- Array of chart image paths
    chart_levels        JSONB,                      -- Extracted TP/SL from charts

    -- Context from messages
    market_context      TEXT,                       -- "DOL fake news pump", etc.
    updates             JSONB,                      -- Array of {timestamp, message, pnl}

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,

    UNIQUE(symbol, author_id, entry_timestamp)
);

-- ═══ MESSAGE INTENT CLASSIFICATION ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS message_intents (
    id                  SERIAL PRIMARY KEY,
    message_id          BIGINT REFERENCES discord_messages(id) ON DELETE CASCADE,

    -- Intent Classification
    intent_type         TEXT NOT NULL,              -- entry, update, partial_exit, full_exit, stopped, analysis
    confidence          FLOAT NOT NULL,             -- 0.0 - 1.0

    -- Linked Trade
    trade_lifecycle_id  INTEGER REFERENCES discord_trade_lifecycle(id),

    -- Extracted Entities
    symbols             TEXT[],
    direction           TEXT,                       -- long, short
    price_levels        JSONB,                      -- {entry: X, stop: Y, target: Z}
    pnl_amount          FLOAT,                      -- Extracted P&L amount
    pnl_per_contract    FLOAT,

    -- Context Clues
    keywords            TEXT[],                     -- ['short', 'here', '@everyone']
    mentions_everyone   BOOLEAN DEFAULT FALSE,
    has_chart           BOOLEAN DEFAULT FALSE,

    -- Chart Analysis (if image attached)
    chart_path          TEXT,
    chart_levels_ocr    JSONB,                      -- OCR extracted levels

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ PATTERN LIBRARY (INTENT DETECTION RULES) ═══════════════════════════════

CREATE TABLE IF NOT EXISTS intent_patterns (
    id                  SERIAL PRIMARY KEY,
    pattern_name        TEXT NOT NULL UNIQUE,
    intent_type         TEXT NOT NULL,

    -- Pattern Matching Rules
    keyword_regex       TEXT[],                     -- Array of regex patterns
    context_words       TEXT[],                     -- Supporting context words
    exclusion_words     TEXT[],                     -- Words that invalidate pattern

    -- Pattern Characteristics
    requires_symbol     BOOLEAN DEFAULT TRUE,
    requires_price      BOOLEAN DEFAULT FALSE,
    requires_direction  BOOLEAN DEFAULT FALSE,

    -- Examples
    example_messages    TEXT[],

    confidence_score    FLOAT DEFAULT 0.8,
    priority            INTEGER DEFAULT 50,         -- Higher = checked first

    active              BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ═══ SEED INTENT PATTERNS ═══════════════════════════════════════════════════

INSERT INTO intent_patterns (pattern_name, intent_type, keyword_regex, context_words, requires_symbol, requires_direction, confidence_score, priority, example_messages)
VALUES
-- Entry Patterns
('short_entry', 'entry', ARRAY['\\bshort\\b', '\\bhere\\b'], ARRAY['@everyone'], TRUE, TRUE, 0.95, 100,
 ARRAY['ES short here @everyone', 'SPY short here', 'Taking a short on QQQ here']),

('long_entry', 'entry', ARRAY['\\blong\\b', '\\bhere\\b'], ARRAY['@everyone'], TRUE, TRUE, 0.95, 100,
 ARRAY['ES long here @everyone', 'Going long SPY here']),

('buying_entry', 'entry', ARRAY['\\b(buy|buying|bought)\\b', '\\bhere\\b'], ARRAY['@everyone', 'entry'], TRUE, FALSE, 0.90, 90,
 ARRAY['Buying ES here', 'Bought 10 SPY calls here']),

('selling_entry', 'entry', ARRAY['\\b(sell|selling|sold)\\b', '\\bhere\\b'], ARRAY['@everyone', 'entry'], TRUE, FALSE, 0.90, 90,
 ARRAY['Selling QQQ here', 'Sold SPY at 650']),

-- Update Patterns
('profit_update', 'update', ARRAY['\\$\\d+', '\\b(per|/)\\s*(con|contract)'], ARRAY['up', '@everyone'], FALSE, FALSE, 0.85, 80,
 ARRAY['Up $600 per con here', '$950 per contract at this level']),

('target_approaching', 'update', ARRAY['\\balmost\\b', '\\b(at|near|approaching)\\b', '\\btarget\\b'], ARRAY['want', 'looking'], FALSE, FALSE, 0.75, 70,
 ARRAY['Almost at target', 'SPX is almost at 6500']),

-- Exit Patterns
('partial_exit', 'partial_exit', ARRAY['\\btake\\s*(it|profit)?\\b', '\\bif\\s*you\\s*wish\\b'], ARRAY['@everyone', 'here'], FALSE, FALSE, 0.90, 95,
 ARRAY['Take it if you wish @everyone', 'Taking partial profit here']),

('full_exit', 'full_exit', ARRAY['\\btaking\\s*it\\s*off\\b', '\\bclosed?\\b', '\\bexit(ed|ing)?\\b'], ARRAY['@everyone', 'here'], FALSE, FALSE, 0.95, 95,
 ARRAY['Taking it off here', 'Closed the trade', 'Exiting here @everyone']),

('target_hit', 'full_exit', ARRAY['\\btarget\\s*(hit|reached)\\b', '\\bhit\\s*(target|tp)\\b'], ARRAY['great trade', 'done'], FALSE, FALSE, 0.90, 90,
 ARRAY['Target hit, great trade', 'Hit target at 6500']),

('stopped_out', 'stopped', ARRAY['\\bstop(ped)?\\s*(out)?\\b', '\\bhit\\s*stop\\b'], ARRAY['loss'], FALSE, FALSE, 0.95, 95,
 ARRAY['Stopped out', 'Hit stop loss', 'Got stopped']),

-- Analysis Patterns
('price_target', 'analysis', ARRAY['\\btarget\\s*is\\b', '\\blooking\\s*(for|at)\\b'], ARRAY['expecting', 'watching'], TRUE, FALSE, 0.70, 60,
 ARRAY['Target is 6500', 'Looking for SPX to hit 6550']),

('market_context', 'analysis', ARRAY['\\b(fake|real)\\s*news\\b', '\\bpump\\b', '\\bdump\\b'], ARRAY['because', 'due to'], FALSE, FALSE, 0.65, 50,
 ARRAY['DOL is fake news pump', 'This rally is a pump']),

('support_resistance', 'analysis', ARRAY['\\b(support|resistance)\\b', '\\b(at|near)\\b', '\\$\\d+'], ARRAY['level', 'zone'], TRUE, FALSE, 0.70, 60,
 ARRAY['Support at 6500', 'Resistance near 650'])

ON CONFLICT (pattern_name) DO NOTHING;

-- ═══ INDEXES ════════════════════════════════════════════════════════════════

CREATE INDEX idx_trade_lifecycle_open
    ON discord_trade_lifecycle(status, author_id)
    WHERE status IN ('open', 'partial_close');

CREATE INDEX idx_trade_lifecycle_symbol_author
    ON discord_trade_lifecycle(symbol, author_id, entry_timestamp DESC);

CREATE INDEX idx_message_intents_type
    ON message_intents(intent_type, confidence DESC);

CREATE INDEX idx_message_intents_trade
    ON message_intents(trade_lifecycle_id);

-- ═══ FUNCTIONS ═══════════════════════════════════════════════════════════════

-- Auto-update timestamp on trade lifecycle updates
CREATE OR REPLACE FUNCTION update_trade_lifecycle_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    IF NEW.status = 'closed' AND OLD.status != 'closed' THEN
        NEW.closed_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trade_lifecycle_timestamp
    BEFORE UPDATE ON discord_trade_lifecycle
    FOR EACH ROW
    EXECUTE FUNCTION update_trade_lifecycle_timestamp();

-- ═══ VIEWS ═══════════════════════════════════════════════════════════════════

-- Open trades waiting for updates
CREATE OR REPLACE VIEW open_trades AS
SELECT
    tl.*,
    m.content as entry_message,
    EXTRACT(EPOCH FROM (NOW() - tl.entry_timestamp))/60 as minutes_open,
    COALESCE(jsonb_array_length(tl.updates), 0) as update_count
FROM discord_trade_lifecycle tl
JOIN discord_messages m ON tl.entry_message_id = m.id
WHERE tl.status IN ('open', 'partial_close')
ORDER BY tl.entry_timestamp DESC;

-- Recent message intents (for debugging)
CREATE OR REPLACE VIEW recent_intents AS
SELECT
    mi.id,
    mi.message_id,
    m.content,
    m.author_name,
    mi.intent_type,
    mi.confidence,
    mi.symbols,
    mi.direction,
    mi.pnl_amount,
    mi.trade_lifecycle_id,
    m.timestamp
FROM message_intents mi
JOIN discord_messages m ON mi.message_id = m.id
ORDER BY m.timestamp DESC
LIMIT 50;

-- Trade performance summary
CREATE OR REPLACE VIEW trade_performance_summary AS
SELECT
    author_name,
    COUNT(*) as total_trades,
    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_trades,
    SUM(CASE WHEN final_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN final_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    AVG(final_pnl) FILTER (WHERE final_pnl IS NOT NULL) as avg_pnl,
    SUM(final_pnl) as total_pnl,
    AVG(EXTRACT(EPOCH FROM (closed_at - entry_timestamp))/60) FILTER (WHERE closed_at IS NOT NULL) as avg_trade_duration_minutes
FROM discord_trade_lifecycle
GROUP BY author_name
ORDER BY total_pnl DESC NULLS LAST;

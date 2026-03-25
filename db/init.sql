-- Trading pipeline schema — runs once on first container boot.

-- ═══ VIDEO PIPELINE ════════════════════════════════════════════

CREATE TABLE media_sources (
    id            SERIAL PRIMARY KEY,
    file_path     TEXT NOT NULL UNIQUE,
    filename      TEXT NOT NULL,
    category      TEXT NOT NULL,
    program       TEXT,
    session       TEXT,
    duration_sec  INTEGER,
    file_size     BIGINT,
    status        TEXT DEFAULT 'pending',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transcripts (
    id            SERIAL PRIMARY KEY,
    source_id     INTEGER REFERENCES media_sources(id) ON DELETE CASCADE,
    segment_idx   INTEGER NOT NULL,
    start_sec     FLOAT NOT NULL,
    end_sec       FLOAT NOT NULL,
    text          TEXT NOT NULL,
    confidence    FLOAT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE frames (
    id            SERIAL PRIMARY KEY,
    source_id     INTEGER REFERENCES media_sources(id) ON DELETE CASCADE,
    timestamp_sec FLOAT NOT NULL,
    file_path     TEXT NOT NULL,
    is_chart      BOOLEAN DEFAULT FALSE,
    description   TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE session_chats (
    id            SERIAL PRIMARY KEY,
    source_id     INTEGER REFERENCES media_sources(id) ON DELETE CASCADE,
    author        TEXT,
    message       TEXT NOT NULL,
    timestamp     TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE video_trades (
    id             SERIAL PRIMARY KEY,
    source_id      INTEGER REFERENCES media_sources(id) ON DELETE CASCADE,
    transcript_id  INTEGER REFERENCES transcripts(id),
    frame_id       INTEGER REFERENCES frames(id),
    symbol         TEXT,
    direction      TEXT,
    setup_type     TEXT,
    entry_criteria JSONB,
    exit_criteria  JSONB,
    result         TEXT,
    notes          TEXT,
    video_time     FLOAT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE video_insights (
    id            SERIAL PRIMARY KEY,
    source_id     INTEGER REFERENCES media_sources(id) ON DELETE CASCADE,
    category      TEXT NOT NULL,
    description   TEXT NOT NULL,
    evidence      TEXT,
    confidence    FLOAT,
    tags          TEXT[],
    created_at    TIMESTAMPTZ DEFAULT NOW()
);


-- ═══ DISCORD PIPELINE ═════════════════════════════════════════

CREATE TABLE discord_messages (
    id            BIGINT PRIMARY KEY,
    author_id     BIGINT NOT NULL,
    author_name   TEXT NOT NULL,
    content       TEXT NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL,
    attachments   JSONB,
    reactions     JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE discord_trades (
    id            SERIAL PRIMARY KEY,
    message_id    BIGINT REFERENCES discord_messages(id) ON DELETE CASCADE,
    author_name   TEXT NOT NULL,
    symbol        TEXT,
    direction     TEXT,
    entry         FLOAT,
    stop_loss     FLOAT,
    target        FLOAT,
    setup_type    TEXT,
    reasoning     TEXT,
    chart_path    TEXT,
    chart_tf      TEXT,
    chart_levels  JSONB,
    result        TEXT,
    pnl_pct       FLOAT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);


-- ═══ SHARED ═══════════════════════════════════════════════════

CREATE TABLE pipeline_state (
    id            SERIAL PRIMARY KEY,
    source_type   TEXT NOT NULL,
    source_ref    TEXT NOT NULL,
    stage         TEXT NOT NULL,
    status        TEXT DEFAULT 'pending',
    last_offset   INTEGER DEFAULT 0,
    error         TEXT,
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_ref, stage)
);


-- ═══ INDEXES (agent-facing tables only) ═══════════════════════

CREATE INDEX idx_discord_msg_ts
    ON discord_messages(timestamp DESC);

CREATE INDEX idx_discord_trades_author_result
    ON discord_trades(author_name, result);

CREATE INDEX idx_discord_trades_symbol_ts
    ON discord_trades(symbol, created_at DESC);

CREATE INDEX idx_video_trades_setup
    ON video_trades(setup_type);

CREATE INDEX idx_video_insights_category
    ON video_insights(category);

CREATE INDEX idx_video_insights_tags
    ON video_insights USING GIN(tags);


-- ═══ MATERIALIZED VIEWS (pre-computed for agent runtime) ══════

CREATE MATERIALIZED VIEW trader_stats AS
SELECT
    author_name,
    COUNT(*)                                                  AS total_trades,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END)         AS wins,
    AVG(CASE WHEN result = 'win' THEN 1.0 ELSE 0.0 END)     AS win_rate,
    AVG(pnl_pct) FILTER (WHERE pnl_pct IS NOT NULL)         AS avg_pnl,
    MAX(created_at)                                           AS last_active
FROM discord_trades
WHERE result IS NOT NULL
GROUP BY author_name;

CREATE UNIQUE INDEX idx_trader_stats_name ON trader_stats(author_name);

CREATE MATERIALIZED VIEW setup_win_rates AS
SELECT
    setup_type,
    symbol,
    COUNT(*)                                                  AS total,
    AVG(CASE WHEN result = 'win' THEN 1.0 ELSE 0.0 END)     AS win_rate,
    AVG(pnl_pct) FILTER (WHERE pnl_pct IS NOT NULL)         AS avg_pnl
FROM (
    SELECT setup_type, symbol, result, pnl_pct FROM discord_trades
    UNION ALL
    SELECT setup_type, symbol, result, NULL AS pnl_pct FROM video_trades
) combined
WHERE result IS NOT NULL AND setup_type IS NOT NULL
GROUP BY setup_type, symbol;

CREATE UNIQUE INDEX idx_setup_wr ON setup_win_rates(setup_type, symbol);

CREATE TABLE IF NOT EXISTS regions (
    id BIGSERIAL PRIMARY KEY,
    sido VARCHAR(50) NOT NULL,
    sigungu VARCHAR(80),
    eupmyeondong VARCHAR(80),
    legal_dong_code VARCHAR(20),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sido, sigungu, eupmyeondong, legal_dong_code)
);

CREATE TABLE IF NOT EXISTS weather_stations (
    id BIGSERIAL PRIMARY KEY,
    station_code VARCHAR(20) NOT NULL UNIQUE,
    station_name VARCHAR(100) NOT NULL,
    region_id BIGINT REFERENCES regions(id),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    source VARCHAR(50) NOT NULL DEFAULT 'KMA',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rainfall_observations (
    id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES weather_stations(id),
    observed_at TIMESTAMPTZ NOT NULL,
    rainfall_mm NUMERIC(8, 2) NOT NULL DEFAULT 0,
    source_api VARCHAR(80) NOT NULL,
    raw_payload JSONB,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (station_id, observed_at, source_api)
);

CREATE TABLE IF NOT EXISTS flood_history (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT REFERENCES regions(id),
    event_date DATE,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    flood_type VARCHAR(80),
    depth_cm NUMERIC(8, 2),
    area_sqm NUMERIC(14, 2),
    source VARCHAR(100) NOT NULL,
    source_event_id VARCHAR(100),
    geometry_wkt TEXT,
    raw_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_event_id)
);

CREATE TABLE IF NOT EXISTS cctv_sources (
    id BIGSERIAL PRIMARY KEY,
    cctv_code VARCHAR(100) UNIQUE,
    cctv_name VARCHAR(150),
    region_id BIGINT REFERENCES regions(id),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    road_name VARCHAR(150),
    source VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cctv_media (
    id BIGSERIAL PRIMARY KEY,
    cctv_source_id BIGINT REFERENCES cctv_sources(id),
    captured_at TIMESTAMPTZ,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('image', 'video')),
    file_path TEXT NOT NULL,
    file_hash VARCHAR(128),
    width INTEGER,
    height INTEGER,
    duration_sec NUMERIC(10, 3),
    source_dataset VARCHAR(100),
    raw_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (file_path)
);

CREATE TABLE IF NOT EXISTS flood_labels (
    id BIGSERIAL PRIMARY KEY,
    cctv_media_id BIGINT NOT NULL REFERENCES cctv_media(id) ON DELETE CASCADE,
    label VARCHAR(30) NOT NULL CHECK (label IN ('normal', 'pre_flood', 'flooded', 'unknown')),
    confidence NUMERIC(5, 4),
    labeled_by VARCHAR(100),
    label_source VARCHAR(100) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (cctv_media_id, label_source)
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    job_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_rainfall_observed_at
    ON rainfall_observations (observed_at);

CREATE INDEX IF NOT EXISTS idx_rainfall_station_observed_at
    ON rainfall_observations (station_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_flood_history_event_date
    ON flood_history (event_date);

CREATE INDEX IF NOT EXISTS idx_cctv_media_captured_at
    ON cctv_media (captured_at);

CREATE INDEX IF NOT EXISTS idx_flood_labels_label
    ON flood_labels (label);

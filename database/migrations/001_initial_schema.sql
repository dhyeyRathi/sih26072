-- SIH26072 Thunderstorm & Lightning Nowcasting Platform
-- Initial Database Schema for Supabase (PostgreSQL + PostGIS + pgvector)
-- Run this in the Supabase SQL Editor

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE user_role AS ENUM ('admin', 'forecaster', 'disaster_authority', 'responder');
CREATE TYPE risk_level AS ENUM ('low', 'moderate', 'high', 'severe');
CREATE TYPE alert_status AS ENUM ('draft', 'pending_review', 'approved', 'dismissed', 'expired');
CREATE TYPE alert_action AS ENUM ('created', 'submitted', 'approved', 'edited', 'dismissed');
CREATE TYPE data_source_type AS ENUM ('radar', 'satellite', 'lightning', 'aws', 'nwp');
CREATE TYPE source_status AS ENUM ('live', 'delayed', 'stale', 'offline');
CREATE TYPE storm_intensity AS ENUM ('weak', 'moderate', 'strong', 'severe');
CREATE TYPE storm_trend AS ENUM ('intensifying', 'steady', 'weakening', 'dissipating');
CREATE TYPE asset_type AS ENUM (
    'hospital', 'school', 'airport', 'highway', 'railway',
    'power_station', 'emergency_facility', 'government_building', 'other'
);

-- =============================================================================
-- PROFILES (extends Supabase auth.users)
-- =============================================================================

CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'responder',
    organization TEXT,
    designation TEXT,
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, role)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
        COALESCE((NEW.raw_user_meta_data->>'role')::user_role, 'responder')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- =============================================================================
-- RADAR SITES
-- =============================================================================

CREATE TABLE radar_sites (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    elevation_m REAL,
    radar_type TEXT,
    range_km REAL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_radar_sites_geom ON radar_sites USING GIST (geom);

-- =============================================================================
-- WEATHER STATIONS (AWS)
-- =============================================================================

CREATE TABLE weather_stations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    elevation_m REAL,
    station_type TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_weather_stations_geom ON weather_stations USING GIST (geom);

-- =============================================================================
-- ADMINISTRATIVE REGIONS (States, Districts)
-- =============================================================================

CREATE TABLE administrative_regions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('country', 'state', 'district')),
    parent_id INTEGER REFERENCES administrative_regions(id),
    geom GEOMETRY(MultiPolygon, 4326) NOT NULL,
    population INTEGER,
    area_sq_km REAL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_admin_regions_geom ON administrative_regions USING GIST (geom);
CREATE INDEX idx_admin_regions_level ON administrative_regions (level);

-- =============================================================================
-- CRITICAL ASSETS (Hospitals, Schools, Airports, etc.)
-- =============================================================================

CREATE TABLE critical_assets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    asset_type asset_type NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    district_id INTEGER REFERENCES administrative_regions(id),
    address TEXT,
    capacity INTEGER,
    contact_info JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_critical_assets_geom ON critical_assets USING GIST (geom);
CREATE INDEX idx_critical_assets_type ON critical_assets (asset_type);

-- =============================================================================
-- DATA SOURCE HEALTH
-- =============================================================================

CREATE TABLE data_source_health (
    id SERIAL PRIMARY KEY,
    source data_source_type NOT NULL,
    status source_status NOT NULL DEFAULT 'offline',
    last_data_at TIMESTAMPTZ,
    last_check_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    latency_ms INTEGER,
    error_message TEXT,
    metadata JSONB,
    UNIQUE (source)
);

-- Insert default rows for all sources
INSERT INTO data_source_health (source, status) VALUES
    ('radar', 'offline'),
    ('satellite', 'offline'),
    ('lightning', 'offline'),
    ('aws', 'offline'),
    ('nwp', 'offline');

-- =============================================================================
-- MODEL RUNS
-- =============================================================================

CREATE TABLE model_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version TEXT NOT NULL,
    model_type TEXT NOT NULL DEFAULT 'persistence',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    input_sources JSONB,
    forecast_horizons INTEGER[] NOT NULL DEFAULT ARRAY[10, 20, 30, 40, 50, 60],
    metrics JSONB,
    metadata JSONB
);

CREATE INDEX idx_model_runs_started ON model_runs (started_at DESC);

-- =============================================================================
-- STORM CELLS
-- =============================================================================

CREATE TABLE storm_cells (
    id TEXT PRIMARY KEY,  -- e.g. C-1042
    first_detected_at TIMESTAMPTZ NOT NULL,
    last_observed_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    total_observations INTEGER NOT NULL DEFAULT 1,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- STORM CELL OBSERVATIONS (time-series per cell)
-- =============================================================================

CREATE TABLE storm_cell_observations (
    id SERIAL PRIMARY KEY,
    cell_id TEXT NOT NULL REFERENCES storm_cells(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    geom_centroid GEOMETRY(Point, 4326) NOT NULL,
    geom_footprint GEOMETRY(Polygon, 4326),
    intensity storm_intensity NOT NULL DEFAULT 'moderate',
    max_reflectivity_dbz REAL,
    mean_reflectivity_dbz REAL,
    area_sq_km REAL,
    lightning_rate REAL,  -- flashes per minute
    movement_speed_kmh REAL,
    movement_direction_deg REAL,
    trend storm_trend NOT NULL DEFAULT 'steady',
    model_run_id UUID REFERENCES model_runs(id),
    metadata JSONB,
    UNIQUE (cell_id, observed_at)
);

CREATE INDEX idx_storm_obs_cell ON storm_cell_observations (cell_id, observed_at DESC);
CREATE INDEX idx_storm_obs_geom ON storm_cell_observations USING GIST (geom_centroid);
CREATE INDEX idx_storm_obs_time ON storm_cell_observations (observed_at DESC);

-- =============================================================================
-- STORM CELL FORECASTS (predicted future positions)
-- =============================================================================

CREATE TABLE storm_cell_forecasts (
    id SERIAL PRIMARY KEY,
    cell_id TEXT NOT NULL REFERENCES storm_cells(id) ON DELETE CASCADE,
    model_run_id UUID NOT NULL REFERENCES model_runs(id),
    forecast_time TIMESTAMPTZ NOT NULL,
    horizon_minutes INTEGER NOT NULL,
    geom_predicted GEOMETRY(Point, 4326) NOT NULL,
    geom_footprint GEOMETRY(Polygon, 4326),
    geom_trajectory GEOMETRY(LineString, 4326),
    geom_uncertainty GEOMETRY(Polygon, 4326),  -- uncertainty corridor
    thunderstorm_probability REAL CHECK (thunderstorm_probability BETWEEN 0 AND 1),
    lightning_probability REAL CHECK (lightning_probability BETWEEN 0 AND 1),
    predicted_intensity storm_intensity,
    predicted_reflectivity_dbz REAL,
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),
    metadata JSONB,
    UNIQUE (cell_id, model_run_id, horizon_minutes)
);

CREATE INDEX idx_storm_fc_cell ON storm_cell_forecasts (cell_id, horizon_minutes);
CREATE INDEX idx_storm_fc_geom ON storm_cell_forecasts USING GIST (geom_predicted);
CREATE INDEX idx_storm_fc_model ON storm_cell_forecasts (model_run_id);

-- =============================================================================
-- RISK ZONES
-- =============================================================================

CREATE TABLE risk_zones (
    id SERIAL PRIMARY KEY,
    model_run_id UUID NOT NULL REFERENCES model_runs(id),
    risk_level risk_level NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    thunderstorm_probability REAL,
    lightning_probability REAL,
    affected_population INTEGER,
    affected_districts TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_risk_zones_geom ON risk_zones USING GIST (geom);
CREATE INDEX idx_risk_zones_level ON risk_zones (risk_level);
CREATE INDEX idx_risk_zones_valid ON risk_zones (valid_from, valid_to);

-- =============================================================================
-- ALERTS / WARNINGS
-- =============================================================================

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status alert_status NOT NULL DEFAULT 'draft',
    risk_level risk_level NOT NULL,
    model_run_id UUID REFERENCES model_runs(id),
    affected_area GEOMETRY(Polygon, 4326),
    affected_districts TEXT[],
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL,
    storm_cell_ids TEXT[],
    evidence JSONB,  -- signals that triggered the alert
    created_by UUID REFERENCES profiles(id),
    approved_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_status ON alerts (status);
CREATE INDEX idx_alerts_geom ON alerts USING GIST (affected_area);
CREATE INDEX idx_alerts_time ON alerts (created_at DESC);

-- =============================================================================
-- ALERT REVIEWS (audit trail)
-- =============================================================================

CREATE TABLE alert_reviews (
    id SERIAL PRIMARY KEY,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    reviewer_id UUID NOT NULL REFERENCES profiles(id),
    action alert_action NOT NULL,
    comment TEXT,
    previous_status alert_status,
    new_status alert_status,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alert_reviews_alert ON alert_reviews (alert_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_reviews ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read all, update own
CREATE POLICY "Profiles are viewable by authenticated users"
    ON profiles FOR SELECT TO authenticated USING (true);

CREATE POLICY "Users can update own profile"
    ON profiles FOR UPDATE TO authenticated USING (auth.uid() = id);

-- Alerts: all authenticated can read, forecasters+ can create/update
CREATE POLICY "Alerts are viewable by authenticated users"
    ON alerts FOR SELECT TO authenticated USING (true);

CREATE POLICY "Forecasters can manage alerts"
    ON alerts FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles
            WHERE profiles.id = auth.uid()
            AND profiles.role IN ('admin', 'forecaster')
        )
    );

-- Alert reviews: all authenticated can read, forecasters+ can create
CREATE POLICY "Alert reviews are viewable by authenticated users"
    ON alert_reviews FOR SELECT TO authenticated USING (true);

CREATE POLICY "Forecasters can create reviews"
    ON alert_reviews FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles
            WHERE profiles.id = auth.uid()
            AND profiles.role IN ('admin', 'forecaster')
        )
    );

-- Public tables: readable by all authenticated
ALTER TABLE radar_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE administrative_regions ENABLE ROW LEVEL SECURITY;
ALTER TABLE critical_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_source_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE storm_cells ENABLE ROW LEVEL SECURITY;
ALTER TABLE storm_cell_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE storm_cell_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_zones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read for authenticated" ON radar_sites FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON weather_stations FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON administrative_regions FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON critical_assets FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON data_source_health FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON model_runs FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON storm_cells FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON storm_cell_observations FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON storm_cell_forecasts FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read for authenticated" ON risk_zones FOR SELECT TO authenticated USING (true);

-- =============================================================================
-- USEFUL VIEWS
-- =============================================================================

-- Active storms with latest observation
CREATE VIEW active_storms AS
SELECT
    sc.id AS cell_id,
    sc.first_detected_at,
    sc.last_observed_at,
    sco.geom_centroid,
    sco.geom_footprint,
    sco.intensity,
    sco.max_reflectivity_dbz,
    sco.area_sq_km,
    sco.lightning_rate,
    sco.movement_speed_kmh,
    sco.movement_direction_deg,
    sco.trend,
    sc.total_observations
FROM storm_cells sc
JOIN storm_cell_observations sco ON sc.id = sco.cell_id
    AND sco.observed_at = sc.last_observed_at
WHERE sc.is_active = true;

-- Pending alerts for forecaster review
CREATE VIEW pending_alerts AS
SELECT
    a.*,
    p.full_name AS created_by_name
FROM alerts a
LEFT JOIN profiles p ON a.created_by = p.id
WHERE a.status = 'pending_review'
ORDER BY a.created_at DESC;

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Find critical assets within a risk zone
CREATE OR REPLACE FUNCTION find_exposed_assets(zone_geom GEOMETRY)
RETURNS TABLE (
    asset_id INTEGER,
    asset_name TEXT,
    asset_type asset_type,
    distance_km REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ca.id,
        ca.name,
        ca.asset_type,
        (ST_Distance(ca.geom::geography, zone_geom::geography) / 1000)::REAL AS distance_km
    FROM critical_assets ca
    WHERE ST_DWithin(ca.geom::geography, zone_geom::geography, 50000)  -- 50km radius
    ORDER BY ST_Distance(ca.geom::geography, zone_geom::geography);
END;
$$ LANGUAGE plpgsql;

-- Find districts intersecting a forecast area
CREATE OR REPLACE FUNCTION find_affected_districts(forecast_geom GEOMETRY)
RETURNS TABLE (
    district_id INTEGER,
    district_name TEXT,
    population INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ar.id,
        ar.name,
        ar.population
    FROM administrative_regions ar
    WHERE ar.level = 'district'
    AND ST_Intersects(ar.geom, forecast_geom);
END;
$$ LANGUAGE plpgsql;

-- Find storms near a point
CREATE OR REPLACE FUNCTION find_nearby_storms(
    lon DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    radius_km DOUBLE PRECISION DEFAULT 100
)
RETURNS TABLE (
    cell_id TEXT,
    distance_km REAL,
    intensity storm_intensity,
    movement_speed_kmh REAL,
    movement_direction_deg REAL,
    lightning_rate REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.cell_id,
        (ST_Distance(
            s.geom_centroid::geography,
            ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
        ) / 1000)::REAL AS distance_km,
        s.intensity,
        s.movement_speed_kmh,
        s.movement_direction_deg,
        s.lightning_rate
    FROM active_storms s
    WHERE ST_DWithin(
        s.geom_centroid::geography,
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
        radius_km * 1000
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

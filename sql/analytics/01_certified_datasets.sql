-- Certified analytics datasets. All views are read-only and deterministic.

CREATE SCHEMA IF NOT EXISTS analytics;

DROP VIEW IF EXISTS analytics.shift_trip_aggregate CASCADE;
DROP VIEW IF EXISTS analytics.olap_shift_cube CASCADE;
DROP VIEW IF EXISTS analytics.olap_trip_cube CASCADE;
DROP VIEW IF EXISTS analytics.trip_dropoff CASCADE;
DROP VIEW IF EXISTS analytics.trip_pickup CASCADE;
DROP VIEW IF EXISTS analytics.shift CASCADE;
DROP VIEW IF EXISTS analytics.dq_summary CASCADE;
DROP VIEW IF EXISTS analytics.dq_batch_summary CASCADE;
DROP VIEW IF EXISTS analytics.pareto_pickup_zone CASCADE;
DROP VIEW IF EXISTS analytics.top_pickup_zone_hour CASCADE;
DROP VIEW IF EXISTS analytics.driver_performance_summary CASCADE;
DROP VIEW IF EXISTS analytics.driver_performance_monthly CASCADE;
DROP VIEW IF EXISTS analytics.vehicle_performance_monthly CASCADE;
DROP VIEW IF EXISTS analytics.current_driver_segments CASCADE;
DROP VIEW IF EXISTS analytics.current_route_association_rules CASCADE;
DROP VIEW IF EXISTS analytics.current_model_runs CASCADE;

-- Exploratory model-run ledger. Result tables retain successful run history;
-- dashboard datasets read the current views below, never a mixed run population.
CREATE TABLE IF NOT EXISTS analytics.model_runs (
    model_run_id UUID PRIMARY KEY,
    model_type VARCHAR(64) NOT NULL CHECK (model_type IN ('DRIVER_SEGMENTATION', 'ROUTE_ASSOCIATION')),
    status VARCHAR(32) NOT NULL CHECK (status IN ('SUCCEEDED', 'FAILED')),
    model_run_at TIMESTAMPTZ NOT NULL,
    training_start DATE,
    training_end DATE,
    input_row_count BIGINT NOT NULL,
    eligible_row_count BIGINT NOT NULL,
    sample_method TEXT NOT NULL,
    parameters JSONB NOT NULL,
    evaluation_metrics JSONB NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_model_runs_current_type
    ON analytics.model_runs (model_type) WHERE is_current;

-- Physical table for K-Means driver segments
CREATE TABLE IF NOT EXISTS analytics.driver_segments (
    driver_key VARCHAR(50) NOT NULL,
    driver_id VARCHAR(50),
    driver_name VARCHAR(100),
    completed_shifts INTEGER,
    trips_per_shift NUMERIC(10, 2),
    revenue_per_hour NUMERIC(10, 2),
    utilization_rate NUMERIC(5, 4),
    idle_minutes_per_shift NUMERIC(10, 2),
    average_trip_distance NUMERIC(10, 2),
    tips_per_trip NUMERIC(10, 2),
    cluster_id INTEGER,
    segment_label VARCHAR(50),
    model_run_id UUID,
    model_run_at TIMESTAMPTZ,
    training_start DATE,
    training_end DATE,
    feature_set TEXT,
    model_k SMALLINT,
    silhouette_score NUMERIC(8, 6)
);

ALTER TABLE analytics.driver_segments
    ADD COLUMN IF NOT EXISTS model_run_id UUID,
    ADD COLUMN IF NOT EXISTS model_run_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS training_start DATE,
    ADD COLUMN IF NOT EXISTS training_end DATE,
    ADD COLUMN IF NOT EXISTS feature_set TEXT,
    ADD COLUMN IF NOT EXISTS model_k SMALLINT,
    ADD COLUMN IF NOT EXISTS silhouette_score NUMERIC(8, 6);
ALTER TABLE analytics.driver_segments DROP CONSTRAINT IF EXISTS driver_segments_pkey;
CREATE UNIQUE INDEX IF NOT EXISTS ux_driver_segments_run_driver
    ON analytics.driver_segments (model_run_id, driver_key);

-- Physical table for Route Association Rules
CREATE TABLE IF NOT EXISTS analytics.route_association_rules (
    rule_id SERIAL PRIMARY KEY,
    antecedent VARCHAR(500),
    consequent VARCHAR(500),
    support NUMERIC(8, 6),
    confidence NUMERIC(8, 6),
    lift NUMERIC(12, 6),
    antecedent_support NUMERIC(8, 6),
    consequent_support NUMERIC(8, 6),
    model_run_id UUID,
    model_run_at TIMESTAMPTZ,
    training_start DATE,
    training_end DATE,
    basket_count INTEGER,
    rules_generated INTEGER,
    rules_published INTEGER,
    min_support NUMERIC(8, 6),
    min_confidence NUMERIC(8, 6),
    min_lift NUMERIC(12, 6),
    antecedent_pickup_borough VARCHAR(100),
    antecedent_pickup_zone VARCHAR(100),
    antecedent_hour_bucket VARCHAR(50),
    antecedent_day_type VARCHAR(50),
    antecedent_vendor VARCHAR(100),
    consequent_dropoff_borough VARCHAR(100),
    consequent_dropoff_zone VARCHAR(100),
    antecedent_count INTEGER,
    stability_score NUMERIC(8, 6)
);

ALTER TABLE analytics.route_association_rules
    ADD COLUMN IF NOT EXISTS model_run_id UUID,
    ADD COLUMN IF NOT EXISTS model_run_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS training_start DATE,
    ADD COLUMN IF NOT EXISTS training_end DATE,
    ADD COLUMN IF NOT EXISTS basket_count INTEGER,
    ADD COLUMN IF NOT EXISTS rules_generated INTEGER,
    ADD COLUMN IF NOT EXISTS rules_published INTEGER,
    ADD COLUMN IF NOT EXISTS min_support NUMERIC(8, 6),
    ADD COLUMN IF NOT EXISTS min_confidence NUMERIC(8, 6),
    ADD COLUMN IF NOT EXISTS min_lift NUMERIC(12, 6),
    ADD COLUMN IF NOT EXISTS antecedent_pickup_borough VARCHAR(100),
    ADD COLUMN IF NOT EXISTS antecedent_pickup_zone VARCHAR(100),
    ADD COLUMN IF NOT EXISTS antecedent_hour_bucket VARCHAR(50),
    ADD COLUMN IF NOT EXISTS antecedent_day_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS antecedent_vendor VARCHAR(100),
    ADD COLUMN IF NOT EXISTS consequent_dropoff_borough VARCHAR(100),
    ADD COLUMN IF NOT EXISTS consequent_dropoff_zone VARCHAR(100),
    ADD COLUMN IF NOT EXISTS antecedent_count INTEGER,
    ADD COLUMN IF NOT EXISTS stability_score NUMERIC(8, 6);
CREATE UNIQUE INDEX IF NOT EXISTS ux_route_rules_run_rule
    ON analytics.route_association_rules (model_run_id, antecedent, consequent);

-- Current-run boundary for Superset. Historical rows remain available for audit
-- through the physical tables and the run ledger.
CREATE OR REPLACE VIEW analytics.current_model_runs AS
SELECT
    model_run_id, model_type, status, model_run_at, training_start, training_end,
    input_row_count, eligible_row_count, sample_method, parameters,
    evaluation_metrics, is_current, created_at
FROM analytics.model_runs
WHERE is_current AND status = 'SUCCEEDED';

CREATE OR REPLACE VIEW analytics.current_driver_segments AS
SELECT
    ds.*,
    mr.input_row_count AS model_input_driver_count,
    mr.eligible_row_count AS model_eligible_driver_count,
    mr.sample_method AS model_sample_method,
    mr.parameters ->> 'scaler' AS model_scaler,
    (mr.evaluation_metrics ->> 'davies_bouldin')::numeric AS davies_bouldin_score,
    (mr.evaluation_metrics ->> 'calinski_harabasz')::numeric AS calinski_harabasz_score,
    (mr.evaluation_metrics ->> 'stability_ari')::numeric AS stability_ari
FROM analytics.driver_segments ds
JOIN analytics.current_model_runs mr ON mr.model_run_id = ds.model_run_id
WHERE mr.model_type = 'DRIVER_SEGMENTATION';

CREATE OR REPLACE VIEW analytics.current_route_association_rules AS
SELECT
    rr.*,
    mr.sample_method AS model_sample_method,
    (mr.evaluation_metrics ->> 'rule_coverage')::numeric AS rule_coverage
FROM analytics.route_association_rules rr
JOIN analytics.current_model_runs mr ON mr.model_run_id = rr.model_run_id
WHERE mr.model_type = 'ROUTE_ASSOCIATION';

-- Grain: one row per trip. Default temporal/location role: pickup.
CREATE OR REPLACE VIEW analytics.trip_pickup AS
SELECT
    f.trip_id,
    f.shift_id,
    pickup_date.date + pickup_time.time_of_day AS pickup_datetime,
    dropoff_date.date + dropoff_time.time_of_day AS dropoff_datetime,
    pickup_time.hour AS pickup_hour,
    pickup_date.day_of_week AS pickup_day_of_week,
    pickup_date.day_name AS pickup_day_name,
    pickup_date.day_of_week::text || ' - ' || pickup_date.day_name AS pickup_weekday_label,
    pickup_date.year AS pickup_year,
    pickup_date.month AS pickup_month,
    dropoff_time.hour AS dropoff_hour,
    dropoff_date.day_of_week AS dropoff_day_of_week,
    dropoff_date.day_name AS dropoff_day_name,
    dropoff_date.day_of_week::text || ' - ' || dropoff_date.day_name AS dropoff_weekday_label,
    f.pickup_date_key,
    f.pickup_time_key,
    f.dropoff_date_key,
    f.dropoff_time_key,
    f.driver_key,
    driver.driver_id,
    driver.display_name AS driver_name,
    driver.home_borough AS driver_home_borough,
    driver.employment_status AS driver_employment_status,
    f.vehicle_key,
    vehicle.vehicle_id,
    vehicle.vehicle_type,
    vehicle.vehicle_status,
    f.vendor_key,
    vendor.vendor_id,
    vendor.vendor_name,
    f.pickup_location_key,
    pickup_location.location_id AS pickup_location_id,
    pickup_location.borough AS pickup_borough,
    pickup_location.zone AS pickup_zone,
    pickup_location.service_zone AS pickup_service_zone,
    f.dropoff_location_key,
    dropoff_location.location_id AS dropoff_location_id,
    dropoff_location.borough AS dropoff_borough,
    dropoff_location.zone AS dropoff_zone,
    dropoff_location.service_zone AS dropoff_service_zone,
    junk.payment_type_desc,
    junk.ratecode_desc,
    junk.trip_type_desc,
    junk.assignment_method,
    junk.is_anomaly AS is_trip_anomaly,
    f.passenger_count,
    f.trip_distance,
    f.trip_duration_minutes,
    f.fare_amount,
    f.extra,
    f.mta_tax,
    f.tip_amount,
    f.tolls_amount,
    f.improvement_surcharge,
    f.total_amount,
    f.assignment_delay_minutes,
    f.source_file,
    f.source_row_number,
    f.batch_id
FROM dds.fact_driver_trip AS f
JOIN dds.dim_date AS pickup_date
  ON pickup_date.date_key = f.pickup_date_key
JOIN dds.dim_time AS pickup_time
  ON pickup_time.time_key = f.pickup_time_key
JOIN dds.dim_date AS dropoff_date
  ON dropoff_date.date_key = f.dropoff_date_key
JOIN dds.dim_time AS dropoff_time
  ON dropoff_time.time_key = f.dropoff_time_key
JOIN dds.dim_driver AS driver
  ON driver.driver_key = f.driver_key
JOIN dds.dim_vehicle AS vehicle
  ON vehicle.vehicle_key = f.vehicle_key
JOIN dds.dim_vendor AS vendor
  ON vendor.vendor_key = f.vendor_key
JOIN dds.dim_location AS pickup_location
  ON pickup_location.location_key = f.pickup_location_key
JOIN dds.dim_location AS dropoff_location
  ON dropoff_location.location_key = f.dropoff_location_key
JOIN dds.dim_junk_trip AS junk
  ON junk.junk_trip_key = f.junk_trip_key;

-- Grain: one row per trip. Default temporal/location role: dropoff.
CREATE OR REPLACE VIEW analytics.trip_dropoff AS
SELECT
    trip_id,
    shift_id,
    pickup_datetime,
    dropoff_datetime,
    pickup_hour,
    pickup_day_of_week,
    pickup_day_name,
    pickup_weekday_label,
    pickup_year,
    pickup_month,
    dropoff_hour,
    dropoff_day_of_week,
    dropoff_day_name,
    dropoff_weekday_label,
    pickup_date_key,
    pickup_time_key,
    dropoff_date_key,
    dropoff_time_key,
    driver_key,
    driver_id,
    driver_name,
    driver_home_borough,
    driver_employment_status,
    vehicle_key,
    vehicle_id,
    vehicle_type,
    vehicle_status,
    vendor_key,
    vendor_id,
    vendor_name,
    pickup_location_key,
    pickup_location_id,
    pickup_borough,
    pickup_zone,
    pickup_service_zone,
    dropoff_location_key,
    dropoff_location_id,
    dropoff_borough,
    dropoff_zone,
    dropoff_service_zone,
    payment_type_desc,
    ratecode_desc,
    trip_type_desc,
    assignment_method,
    is_trip_anomaly,
    passenger_count,
    trip_distance,
    trip_duration_minutes,
    fare_amount,
    extra,
    mta_tax,
    tip_amount,
    tolls_amount,
    improvement_surcharge,
    total_amount,
    assignment_delay_minutes,
    source_file,
    source_row_number,
    batch_id
FROM analytics.trip_pickup;

-- Grain: one row per completed shift. Location roles are resolved 1:1 by shift_id.
CREATE OR REPLACE VIEW analytics.shift AS
SELECT
    f.shift_id,
    f.shift_start,
    f.shift_end,
    f.shift_start_date_key,
    f.shift_start_time_key,
    start_time.hour AS shift_start_hour,
    start_date.day_of_week AS shift_start_day_of_week,
    start_date.day_name AS shift_start_day_name,
    start_date.day_of_week::text || ' - ' || start_date.day_name AS shift_start_weekday_label,
    f.driver_key,
    driver.driver_id,
    driver.display_name AS driver_name,
    driver.home_borough AS driver_home_borough,
    driver.employment_status AS driver_employment_status,
    f.vehicle_key,
    vehicle.vehicle_id,
    vehicle.vehicle_type,
    vehicle.vehicle_status,
    f.vendor_key,
    vendor.vendor_id,
    vendor.vendor_name,
    start_location.location_id AS shift_start_location_id,
    start_location.borough AS shift_start_borough,
    start_location.zone AS shift_start_zone,
    start_location.service_zone AS shift_start_service_zone,
    end_location.location_id AS shift_end_location_id,
    end_location.borough AS shift_end_borough,
    end_location.zone AS shift_end_zone,
    end_location.service_zone AS shift_end_service_zone,
    f.shift_status,
    f.is_anomaly AS is_shift_anomaly,
    DATE_TRUNC('month', f.shift_start)::date =
        MAX(DATE_TRUNC('month', f.shift_start)::date) OVER () AS is_latest_shift_month,
    ROW_NUMBER() OVER (
        PARTITION BY DATE_TRUNC('month', f.shift_start)::date
        ORDER BY
            f.occupied_minutes / NULLIF(f.shift_duration_minutes, 0) ASC NULLS LAST,
            f.shift_id
    ) AS monthly_utilization_rank,
    f.shift_duration_minutes,
    f.trip_count,
    f.occupied_minutes,
    f.idle_minutes,
    f.total_revenue,
    f.total_revenue * 60 / NULLIF(f.shift_duration_minutes, 0)
        AS shift_revenue_per_hour,
    f.occupied_minutes / NULLIF(f.shift_duration_minutes, 0)
        AS shift_utilization_rate,
    f.occupied_minutes * 100 / NULLIF(f.shift_duration_minutes, 0)
        AS shift_utilization_pct,
    f.total_tips,
    f.batch_id
FROM dds.fact_driver_shift AS f
JOIN dds.dim_driver AS driver
  ON driver.driver_key = f.driver_key
JOIN dds.dim_vehicle AS vehicle
  ON vehicle.vehicle_key = f.vehicle_key
JOIN dds.dim_vendor AS vendor
  ON vendor.vendor_key = f.vendor_key
JOIN dds.dim_date AS start_date
  ON start_date.date_key = f.shift_start_date_key
JOIN dds.dim_time AS start_time
  ON start_time.time_key = f.shift_start_time_key
JOIN nds.nds_shift AS source_shift
  ON source_shift.shift_nk = f.shift_id
JOIN nds.nds_location AS source_start_location
  ON source_start_location.location_sk = source_shift.assigned_start_zone
JOIN dds.dim_location AS start_location
  ON start_location.location_id = source_start_location.location_nk
JOIN nds.nds_location AS source_end_location
  ON source_end_location.location_sk = source_shift.actual_end_zone
JOIN dds.dim_location AS end_location
  ON end_location.location_id = source_end_location.location_nk;

-- Grain: one row per shift_id. Safe input for 1:1 shift reconciliation.
CREATE OR REPLACE VIEW analytics.shift_trip_aggregate AS
SELECT
    shift_id,
    COUNT(trip_id) AS trip_count,
    COALESCE(SUM(total_amount), 0::numeric) AS total_revenue,
    COALESCE(SUM(fare_amount), 0::numeric) AS fare_revenue,
    COALESCE(SUM(tip_amount), 0::numeric) AS total_tips,
    COALESCE(SUM(trip_distance), 0::numeric) AS total_distance,
    COALESCE(SUM(trip_duration_minutes), 0::numeric) AS occupied_minutes,
    COUNT(trip_id) FILTER (WHERE is_trip_anomaly) AS anomaly_trip_count
FROM analytics.trip_pickup
GROUP BY shift_id;

-- Grain: one row per trip with OLAP-friendly dimension attributes and additive measures.
-- Source boundary: approved analytics.trip_pickup view, not staging/NDS.
CREATE OR REPLACE VIEW analytics.olap_trip_cube AS
SELECT
    trip_id,
    shift_id,
    pickup_datetime,
    dropoff_datetime,
    pickup_datetime::date AS pickup_date,
    pickup_year,
    EXTRACT(quarter FROM pickup_datetime)::integer AS pickup_quarter,
    pickup_month,
    EXTRACT(day FROM pickup_datetime)::integer AS pickup_day,
    pickup_hour,
    CASE
        WHEN pickup_hour BETWEEN 0 AND 5 THEN '00-05 Overnight'
        WHEN pickup_hour BETWEEN 6 AND 11 THEN '06-11 Morning'
        WHEN pickup_hour BETWEEN 12 AND 17 THEN '12-17 Afternoon'
        ELSE '18-23 Evening'
    END AS pickup_hour_bucket,
    pickup_day_of_week,
    pickup_day_name,
    pickup_weekday_label,
    dropoff_datetime::date AS dropoff_date,
    EXTRACT(year FROM dropoff_datetime)::integer AS dropoff_year,
    EXTRACT(quarter FROM dropoff_datetime)::integer AS dropoff_quarter,
    EXTRACT(month FROM dropoff_datetime)::integer AS dropoff_month,
    EXTRACT(day FROM dropoff_datetime)::integer AS dropoff_day,
    dropoff_hour,
    dropoff_day_of_week,
    dropoff_day_name,
    dropoff_weekday_label,
    vendor_key,
    vendor_id,
    vendor_name,
    driver_key,
    driver_id,
    driver_name,
    driver_home_borough,
    driver_employment_status,
    vehicle_key,
    vehicle_id,
    vehicle_type,
    vehicle_status,
    pickup_location_key,
    pickup_location_id,
    pickup_borough,
    pickup_zone,
    pickup_service_zone,
    dropoff_location_key,
    dropoff_location_id,
    dropoff_borough,
    dropoff_zone,
    dropoff_service_zone,
    payment_type_desc,
    ratecode_desc,
    trip_type_desc,
    assignment_method,
    is_trip_anomaly,
    passenger_count,
    trip_distance,
    trip_duration_minutes,
    1::bigint AS total_trips,
    COALESCE(total_amount, 0::numeric) AS total_revenue,
    COALESCE(fare_amount, 0::numeric) AS fare_revenue,
    COALESCE(tip_amount, 0::numeric) AS total_tips,
    trip_distance AS total_distance,
    trip_duration_minutes AS total_trip_minutes,
    CASE WHEN is_trip_anomaly THEN 1 ELSE 0 END::bigint AS anomaly_trip_count,
    batch_id
FROM analytics.trip_pickup;

-- Grain: one row per completed shift with OLAP-friendly dimension attributes and additive measures.
-- Source boundary: approved analytics.shift view; no row-level join to trip fact.
CREATE OR REPLACE VIEW analytics.olap_shift_cube AS
SELECT
    shift_id,
    shift_start,
    shift_end,
    shift_start::date AS shift_start_date,
    EXTRACT(year FROM shift_start)::integer AS shift_start_year,
    EXTRACT(quarter FROM shift_start)::integer AS shift_start_quarter,
    EXTRACT(month FROM shift_start)::integer AS shift_start_month,
    EXTRACT(day FROM shift_start)::integer AS shift_start_day,
    shift_start_hour,
    CASE
        WHEN shift_start_hour BETWEEN 0 AND 5 THEN '00-05 Overnight'
        WHEN shift_start_hour BETWEEN 6 AND 11 THEN '06-11 Morning'
        WHEN shift_start_hour BETWEEN 12 AND 17 THEN '12-17 Afternoon'
        ELSE '18-23 Evening'
    END AS shift_start_hour_bucket,
    shift_start_day_of_week,
    shift_start_day_name,
    shift_start_weekday_label,
    shift_end::date AS shift_end_date,
    EXTRACT(year FROM shift_end)::integer AS shift_end_year,
    EXTRACT(quarter FROM shift_end)::integer AS shift_end_quarter,
    EXTRACT(month FROM shift_end)::integer AS shift_end_month,
    EXTRACT(day FROM shift_end)::integer AS shift_end_day,
    EXTRACT(hour FROM shift_end)::integer AS shift_end_hour,
    vendor_key,
    vendor_id,
    vendor_name,
    driver_key,
    driver_id,
    driver_name,
    driver_home_borough,
    driver_employment_status,
    vehicle_key,
    vehicle_id,
    vehicle_type,
    vehicle_status,
    shift_start_location_id,
    shift_start_borough,
    shift_start_zone,
    shift_start_service_zone,
    shift_end_location_id,
    shift_end_borough,
    shift_end_zone,
    shift_end_service_zone,
    shift_status,
    is_shift_anomaly,
    1::bigint AS completed_shifts,
    COALESCE(trip_count, 0)::bigint AS total_trips,
    COALESCE(shift_duration_minutes, 0::numeric) AS shift_duration_minutes,
    COALESCE(occupied_minutes, 0::numeric) AS occupied_minutes,
    COALESCE(idle_minutes, 0::numeric) AS idle_minutes,
    COALESCE(total_revenue, 0::numeric) AS total_revenue,
    COALESCE(total_tips, 0::numeric) AS total_tips,
    CASE WHEN is_shift_anomaly THEN 1 ELSE 0 END::bigint AS anomaly_shift_count,
    batch_id
FROM analytics.shift;

-- Grain: one row per UTC date/batch/release/source/rule/severity/event type.
CREATE OR REPLACE VIEW analytics.dq_summary AS
SELECT
    issue.detected_at::date AS event_date_utc,
    issue.batch_id,
    issue.release_id,
    issue.source_system_code,
    issue.source_entity,
    issue.rule_code,
    issue.severity,
    'ISSUE'::text AS event_type,
    COUNT(issue.dq_issue_id) AS issue_count,
    0::bigint AS quarantine_count
FROM dq.dq_issue AS issue
GROUP BY
    issue.detected_at::date,
    issue.batch_id,
    issue.release_id,
    issue.source_system_code,
    issue.source_entity,
    issue.rule_code,
    issue.severity
UNION ALL
SELECT
    quarantine.quarantined_at::date AS event_date_utc,
    quarantine.batch_id,
    quarantine.release_id,
    quarantine.source_system_code,
    quarantine.source_entity,
    quarantine.error_rule_code AS rule_code,
    quarantine.severity,
    'QUARANTINE'::text AS event_type,
    0::bigint AS issue_count,
    COUNT(quarantine.quarantine_id) AS quarantine_count
FROM dq.quarantine_record AS quarantine
GROUP BY
    quarantine.quarantined_at::date,
    quarantine.batch_id,
    quarantine.release_id,
    quarantine.source_system_code,
    quarantine.source_entity,
    quarantine.error_rule_code,
    quarantine.severity;

-- Grain: one row per successful NDS pipeline run, including runs with zero DQ
-- events. This prevents "latest run" from silently meaning "latest run that
-- happened to have an issue". Issue events remain events, not affected rows.
CREATE OR REPLACE VIEW analytics.dq_batch_summary AS
WITH batch_rollup AS (
    SELECT
        batch_id,
        release_id,
        MAX(event_date_utc) AS latest_event_date_utc,
        COALESCE(SUM(issue_count), 0)::bigint AS dq_issue_count,
        COALESCE(SUM(quarantine_count), 0)::bigint AS quarantine_count,
        COUNT(DISTINCT source_system_code) AS source_system_count,
        COUNT(DISTINCT rule_code) AS rule_count
    FROM analytics.dq_summary
    GROUP BY batch_id, release_id
),
ranked AS (
    SELECT
        metadata.batch_id,
        metadata.release_id,
        batch_rollup.latest_event_date_utc,
        metadata.pipeline_name,
        metadata.batch_status,
        metadata.batch_started_at,
        metadata.batch_completed_at,
        metadata.row_count_expected,
        metadata.row_count_loaded,
        COALESCE(batch_rollup.dq_issue_count, 0)::bigint AS dq_issue_count,
        COALESCE(batch_rollup.quarantine_count, 0)::bigint AS quarantine_count,
        COALESCE(batch_rollup.source_system_count, 0)::bigint AS source_system_count,
        COALESCE(batch_rollup.rule_count, 0)::bigint AS rule_count,
        ROW_NUMBER() OVER (
            ORDER BY metadata.batch_completed_at DESC, metadata.batch_id DESC
        ) AS batch_recency_rank
    FROM audit.metadata_etl_batch AS metadata
    LEFT JOIN batch_rollup
      ON batch_rollup.batch_id = metadata.batch_id
    WHERE metadata.pipeline_name = 'warehouse_nds'
      AND metadata.batch_status = 'SUCCEEDED'
      AND metadata.batch_completed_at IS NOT NULL
)
SELECT
    batch_id,
    release_id,
    latest_event_date_utc,
    pipeline_name,
    batch_status,
    batch_started_at,
    batch_completed_at,
    row_count_expected,
    row_count_loaded,
    dq_issue_count,
    quarantine_count,
    source_system_count,
    rule_count,
    batch_recency_rank,
    batch_recency_rank = 1 AS is_latest_dq_batch
FROM ranked;

-- Grain: one row per pickup zone. Pre-calculates cumulative contribution metrics.
CREATE OR REPLACE VIEW analytics.pareto_pickup_zone AS
WITH zone_trips AS (
    SELECT
        pickup_location_key,
        pickup_zone,
        pickup_borough,
        COUNT(*) AS trips,
        SUM(total_amount) AS revenue
    FROM analytics.trip_pickup
    GROUP BY pickup_location_key, pickup_zone, pickup_borough
),
zone_cum AS (
    SELECT
        pickup_location_key,
        pickup_zone,
        pickup_borough,
        trips,
        revenue,
        SUM(trips) OVER (ORDER BY trips DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_trips,
        SUM(trips) OVER () AS total_trips,
        SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_revenue,
        SUM(revenue) OVER () AS total_revenue
    FROM zone_trips
)
SELECT
    pickup_location_key,
    pickup_zone,
    pickup_borough,
    trips,
    revenue,
    cum_trips::double precision / NULLIF(total_trips, 0) AS cum_trips_pct,
    cum_revenue::double precision / NULLIF(total_revenue, 0) AS cum_revenue_pct
FROM zone_cum;

-- Grain: one row per top pickup zone and pickup hour. The cohort is selected by
-- all-period observed trip volume so every selected zone retains all 24 hours.
CREATE OR REPLACE VIEW analytics.top_pickup_zone_hour AS
WITH zone_totals AS (
    SELECT
        pickup_borough,
        pickup_zone,
        COUNT(trip_id) AS zone_trips,
        ROW_NUMBER() OVER (
            ORDER BY COUNT(trip_id) DESC, pickup_borough, pickup_zone
        ) AS zone_rank
    FROM analytics.trip_pickup
    GROUP BY pickup_borough, pickup_zone
),
top_zones AS (
    SELECT pickup_borough, pickup_zone, zone_rank
    FROM zone_totals
    WHERE zone_rank <= 12
)
SELECT
    top_zones.zone_rank,
    trip.pickup_borough,
    trip.pickup_zone,
    trip.pickup_borough || ' · ' || trip.pickup_zone AS pickup_zone_label,
    trip.pickup_hour,
    COUNT(trip.trip_id) AS observed_trips,
    COALESCE(SUM(trip.total_amount), 0::numeric) AS total_revenue
FROM analytics.trip_pickup AS trip
JOIN top_zones
  ON top_zones.pickup_borough = trip.pickup_borough
 AND top_zones.pickup_zone = trip.pickup_zone
GROUP BY
    top_zones.zone_rank,
    trip.pickup_borough,
    trip.pickup_zone,
    trip.pickup_hour;

-- Grain: one row per driver across the certified completed-shift population.
CREATE OR REPLACE VIEW analytics.driver_performance_summary AS
WITH driver_rollup AS (
    SELECT
        driver_key,
        driver_id,
        driver_name,
        COUNT(shift_id) AS completed_shifts,
        SUM(trip_count)::numeric / NULLIF(COUNT(shift_id), 0) AS trips_per_shift,
        SUM(total_revenue) / NULLIF(COUNT(shift_id), 0) AS revenue_per_shift,
        SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0) AS revenue_per_hour,
        SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0) AS utilization_rate,
        SUM(idle_minutes)::numeric / NULLIF(COUNT(shift_id), 0) AS idle_minutes_per_shift
    FROM analytics.shift
    GROUP BY driver_key, driver_id, driver_name
),
benchmarked AS (
    SELECT
        driver_rollup.*,
        PERCENT_RANK() OVER (ORDER BY revenue_per_hour) AS revenue_per_hour_percentile,
        PERCENT_RANK() OVER (ORDER BY utilization_rate) AS utilization_percentile,
        PERCENT_RANK() OVER (ORDER BY idle_minutes_per_shift) AS idle_percentile
    FROM driver_rollup
)
SELECT
    driver_key,
    driver_id,
    driver_name,
    completed_shifts,
    trips_per_shift,
    revenue_per_shift,
    revenue_per_hour,
    utilization_rate,
    idle_minutes_per_shift,
    revenue_per_hour_percentile,
    utilization_percentile,
    idle_percentile,
    revenue_per_hour_percentile < 0.25
        AND idle_percentile >= 0.75 AS needs_review,
    CASE
        WHEN revenue_per_hour_percentile < 0.25 AND idle_percentile >= 0.75
            THEN 'Low revenue/hour and high idle/shift'
        WHEN revenue_per_hour_percentile < 0.25
            THEN 'Low revenue/hour'
        WHEN idle_percentile >= 0.75
            THEN 'High idle/shift'
        ELSE 'Within peer range'
    END AS review_reason
FROM benchmarked;

-- Grain: one row per driver and reporting month. Additive components are kept so
-- Superset can recompute ratio-of-sums for a selected month range.
CREATE OR REPLACE VIEW analytics.driver_performance_monthly AS
WITH monthly_rollup AS (
    SELECT
        DATE_TRUNC('month', shift_start)::date AS reporting_month,
        driver_key,
        driver_id,
        driver_name,
        COUNT(shift_id) AS completed_shifts,
        COALESCE(SUM(trip_count), 0)::bigint AS total_trips,
        COALESCE(SUM(total_revenue), 0::numeric) AS total_revenue,
        COALESCE(SUM(occupied_minutes), 0::numeric) AS occupied_minutes,
        COALESCE(SUM(idle_minutes), 0::numeric) AS idle_minutes,
        COALESCE(SUM(shift_duration_minutes), 0::numeric) AS shift_duration_minutes
    FROM analytics.shift
    GROUP BY DATE_TRUNC('month', shift_start)::date, driver_key, driver_id, driver_name
),
benchmarked AS (
    SELECT
        monthly_rollup.*,
        PERCENT_RANK() OVER (
            PARTITION BY reporting_month
            ORDER BY total_revenue * 60 / NULLIF(shift_duration_minutes, 0)
        ) AS revenue_per_hour_percentile,
        PERCENT_RANK() OVER (
            PARTITION BY reporting_month
            ORDER BY idle_minutes::numeric / NULLIF(completed_shifts, 0)
        ) AS idle_minutes_per_shift_percentile
    FROM monthly_rollup
)
SELECT
    reporting_month,
    driver_key,
    driver_id,
    driver_name,
    completed_shifts,
    total_trips,
    total_revenue,
    occupied_minutes,
    idle_minutes,
    shift_duration_minutes,
    total_trips::numeric / NULLIF(completed_shifts, 0) AS trips_per_shift,
    total_revenue * 60 / NULLIF(shift_duration_minutes, 0) AS revenue_per_hour,
    occupied_minutes / NULLIF(shift_duration_minutes, 0) AS utilization_rate,
    idle_minutes::numeric / NULLIF(completed_shifts, 0) AS idle_minutes_per_shift,
    revenue_per_hour_percentile,
    idle_minutes_per_shift_percentile,
    completed_shifts >= 10
        AND revenue_per_hour_percentile < 0.25
        AND idle_minutes_per_shift_percentile >= 0.75 AS needs_review,
    CASE
        WHEN completed_shifts < 10 THEN 'Below minimum sample'
        WHEN revenue_per_hour_percentile < 0.25
             AND idle_minutes_per_shift_percentile >= 0.75 THEN 'Needs review'
        ELSE 'Peer range'
    END AS review_status,
    CASE
        WHEN completed_shifts < 10 THEN 'Below provisional minimum shift sample'
        WHEN revenue_per_hour_percentile < 0.25
             AND idle_minutes_per_shift_percentile >= 0.75
            THEN 'Low revenue/hour and high idle/shift'
        WHEN revenue_per_hour_percentile < 0.25 THEN 'Low revenue/hour'
        WHEN idle_minutes_per_shift_percentile >= 0.75 THEN 'High idle/shift'
        ELSE 'Within peer range'
    END AS review_reason,
    reporting_month = MAX(reporting_month) OVER () AS is_latest_reporting_month
FROM benchmarked;

-- Grain: one row per vehicle and reporting month. This is an exploratory peer
-- benchmark: the provisional 10-shift sample rule is not a certified KPI.
CREATE OR REPLACE VIEW analytics.vehicle_performance_monthly AS
WITH monthly_rollup AS (
    SELECT
        DATE_TRUNC('month', shift_start)::date AS reporting_month,
        vehicle_key,
        vehicle_id,
        vehicle_type,
        COUNT(shift_id) AS completed_shifts,
        COALESCE(SUM(trip_count), 0)::bigint AS total_trips,
        COALESCE(SUM(total_revenue), 0::numeric) AS total_revenue,
        COALESCE(SUM(occupied_minutes), 0::numeric) AS occupied_minutes,
        COALESCE(SUM(idle_minutes), 0::numeric) AS idle_minutes,
        COALESCE(SUM(shift_duration_minutes), 0::numeric) AS shift_duration_minutes
    FROM analytics.shift
    GROUP BY
        DATE_TRUNC('month', shift_start)::date,
        vehicle_key,
        vehicle_id,
        vehicle_type
),
benchmarked AS (
    SELECT
        monthly_rollup.*,
        PERCENT_RANK() OVER (
            PARTITION BY reporting_month, vehicle_type
            ORDER BY occupied_minutes / NULLIF(shift_duration_minutes, 0)
        ) AS utilization_percentile
    FROM monthly_rollup
)
SELECT
    reporting_month,
    vehicle_key,
    vehicle_id,
    vehicle_type,
    completed_shifts,
    total_trips,
    total_revenue,
    occupied_minutes,
    idle_minutes,
    shift_duration_minutes,
    total_trips::numeric / NULLIF(completed_shifts, 0) AS trips_per_shift,
    total_revenue * 60 / NULLIF(shift_duration_minutes, 0) AS revenue_per_hour,
    occupied_minutes / NULLIF(shift_duration_minutes, 0) AS utilization_rate,
    utilization_percentile,
    completed_shifts >= 10 AND utilization_percentile < 0.25 AS is_review_candidate,
    reporting_month = MAX(reporting_month) OVER () AS is_latest_reporting_month
FROM benchmarked;

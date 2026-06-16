-- Certified analytics datasets. All views are read-only and deterministic.

CREATE SCHEMA IF NOT EXISTS analytics;

DROP VIEW IF EXISTS analytics.shift_trip_aggregate CASCADE;
DROP VIEW IF EXISTS analytics.trip_dropoff CASCADE;
DROP VIEW IF EXISTS analytics.trip_pickup CASCADE;
DROP VIEW IF EXISTS analytics.shift CASCADE;
DROP VIEW IF EXISTS analytics.dq_summary CASCADE;
DROP VIEW IF EXISTS analytics.pareto_pickup_zone CASCADE;
DROP VIEW IF EXISTS analytics.driver_performance_summary CASCADE;

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
    pickup_date.year AS pickup_year,
    pickup_date.month AS pickup_month,
    dropoff_time.hour AS dropoff_hour,
    dropoff_date.day_of_week AS dropoff_day_of_week,
    dropoff_date.day_name AS dropoff_day_name,
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
    pickup_year,
    pickup_month,
    dropoff_hour,
    dropoff_day_of_week,
    dropoff_day_name,
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
    f.shift_duration_minutes,
    f.trip_count,
    f.occupied_minutes,
    f.idle_minutes,
    f.total_revenue,
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

"""Idempotently provision the Green Taxi Superset semantic layer and dashboard.

This script runs inside ``superset shell`` after metadata migrations and
``superset init``. It intentionally uses Superset's ORM so the local demo can be
rebuilt without browser-only setup steps.
"""

from __future__ import annotations

import json
import os
from urllib.parse import quote_plus

from flask import current_app
from werkzeug.security import generate_password_hash

from superset import db, security_manager
from superset.connectors.sqla.models import SqlMetric, SqlaTable
from superset.models.core import Database
from superset.models.dashboard import Dashboard
from superset.models.slice import Slice
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm.attributes import set_committed_value


DATABASE_NAME = "Green Taxi Analytics Warehouse"
CERTIFIED_BY = "Analytics Semantic Contract Owner"
CERTIFICATION_DETAILS = (
    "Certified against docs/analytics/semantic-contract.md and "
    "docs/analytics/metric-catalog.md."
)

DATASETS = {
    "trip_pickup": {
        "main_dttm_col": "pickup_datetime",
        "description": "One row per trip; default pickup time and pickup location role.",
    },
    "trip_dropoff": {
        "main_dttm_col": "dropoff_datetime",
        "description": "One row per trip; explicit dropoff time and dropoff location role.",
    },
    "shift": {
        "main_dttm_col": "shift_start",
        "description": "One row per completed shift; default shift-start role.",
    },
    "dq_summary": {
        "main_dttm_col": "event_date_utc",
        "description": "One row per UTC date/batch/release/source/rule/severity/event type.",
    },
    "dq_batch_summary": {
        "main_dttm_col": "batch_completed_at",
        "description": "One row per ETL batch; exposes batch status, row reconciliation and latest-batch context.",
    },
    "pareto_pickup_zone": {
        "main_dttm_col": None,
        "description": "One row per pickup zone; pre-calculated cumulative contribution metrics.",
    },
    "top_pickup_zone_hour": {
        "main_dttm_col": None,
        "description": "One row per top-12 pickup zone and pickup hour for a complete 12 by 24 demand heatmap.",
    },
    "driver_performance_summary": {
        "main_dttm_col": None,
        "description": "One row per driver with peer percentiles and an explicit review rule.",
    },
    "driver_performance_monthly": {
        "main_dttm_col": "reporting_month",
        "description": "One row per driver and reporting month; ratios use additive shift components.",
    },
    "vehicle_performance_monthly": {
        "main_dttm_col": "reporting_month",
        "description": "One row per vehicle and reporting month; peer-review flag is a provisional triage signal.",
        "certified": False,
    },
    "olap_trip_cube": {
        "main_dttm_col": "pickup_datetime",
        "description": "ROLAP trip cube view for slice, dice, drill-down, roll-up and pivot demos.",
    },
    "olap_shift_cube": {
        "main_dttm_col": "shift_start",
        "description": "ROLAP shift cube view for utilization, idle time and revenue/hour demos.",
    },
    "current_driver_segments": {
        "main_dttm_col": None,
        "description": "Current successful K-Means run; one row per eligible driver.",
        "certified": False,
    },
    "current_route_association_rules": {
        "main_dttm_col": None,
        "description": "Current successful Apriori run; one row per published rule.",
        "certified": False,
    },
}

DRIVER_SEGMENTS_METRICS = {
    "driver_count": ("Số tài xế", "COUNT(driver_key)", ",d"),
    "completed_shifts": ("Số ca hoàn tất", "SUM(completed_shifts)", ",d"),
    "avg_driver_revenue_per_hour": ("Doanh thu mỗi giờ ca (thăm dò)", "AVG(revenue_per_hour)", "$,.2f"),
    "avg_driver_utilization_rate": ("Tỷ lệ sử dụng ca (thăm dò)", "AVG(utilization_rate)", ".2%"),
    "idle_minutes_per_shift": (
        "Phút rảnh trung bình mỗi ca",
        "AVG(idle_minutes_per_shift)",
        ",.2f",
    ),
    "trips_per_shift": ("Số chuyến trung bình mỗi ca", "AVG(trips_per_shift)", ",.2f"),
    "average_trip_distance": ("Quãng đường trung bình", "AVG(average_trip_distance)", ",.2f"),
    "tips_per_trip": ("Tiền tip trung bình chuyến", "AVG(tips_per_trip)", "$,.2f"),
    "model_stability_ari": ("Độ ổn định phân cụm (ARI)", "MAX(stability_ari)", ".3f"),
}

ROUTE_ASSOCIATION_RULES_METRICS = {
    "published_rule_count": ("Số luật đã công bố", "COUNT(rule_id)", ",d"),
    "rule_support": ("Độ hỗ trợ (Support)", "MAX(support)", ".4%"),
    "rule_confidence": ("Độ tin cậy (Confidence)", "MAX(confidence)", ".2%"),
    "rule_lift": ("Độ nâng (Lift)", "MAX(lift)", ",.4f"),
    "rule_stability": ("Độ ổn định luật", "MAX(stability_score)", ".2%"),
}

DQ_BATCH_METRICS = {
    "run_recency_rank": ("Thứ tự lần chạy", "MIN(batch_recency_rank)", ",d"),
    "dq_issue_count": ("Tổng số lỗi DQ", "COALESCE(SUM(dq_issue_count), 0)", ",d"),
    "quarantine_count": ("Số dòng bị cách ly", "COALESCE(SUM(quarantine_count), 0)", ",d"),
    "rows_loaded": ("Số dòng đã nạp", "COALESCE(SUM(row_count_loaded), 0)", ",d"),
    "batch_count": ("Số batch", "COUNT(batch_id)", ",d"),
}

DRIVER_MONTHLY_METRICS = {
    "completed_shifts": ("Số ca hoàn tất", "SUM(completed_shifts)", ",d"),
    "revenue_per_hour": ("Doanh thu mỗi giờ ca", "SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0)", "$,.2f"),
    "utilization_rate": ("Tỷ lệ sử dụng ca", "SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0)", ".2%"),
    "idle_minutes_per_shift": ("Phút rảnh trung bình mỗi ca", "SUM(idle_minutes) / NULLIF(SUM(completed_shifts), 0)", ",.2f"),
    "trips_per_shift": ("Số chuyến trung bình mỗi ca", "SUM(total_trips)::numeric / NULLIF(SUM(completed_shifts), 0)", ",.2f"),
    "revenue_per_hour_percentile": ("Phân vị doanh thu mỗi giờ", "AVG(revenue_per_hour_percentile)", ".1%"),
    "review_driver_count": ("Số tài xế cần xem xét", "COUNT(*) FILTER (WHERE needs_review)", ",d"),
}

VEHICLE_MONTHLY_METRICS = {
    "completed_shifts": ("Số ca hoàn tất", "SUM(completed_shifts)", ",d"),
    "revenue_per_hour": ("Doanh thu mỗi giờ ca", "SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0)", "$,.2f"),
    "utilization_rate": ("Tỷ lệ sử dụng ca", "SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0)", ".2%"),
    "utilization_percentile": ("Phân vị sử dụng xe", "AVG(utilization_percentile)", ".1%"),
    "review_vehicle_count": ("Số xe cần xem xét", "COUNT(*) FILTER (WHERE is_review_candidate)", ",d"),
}

CHART_DESCRIPTIONS = {
    "c_t1_kpi_rev": "Executive KPI for total Green Taxi payment amount in the selected analytical context.",
    "c_t1_kpi_trips": "Executive KPI for accepted trip activity; reconciles to DDS trip count.",
    "c_t1_kpi_drv": "Executive KPI for drivers with fact activity, not current HR headcount.",
    "c_t1_kpi_veh": "Executive KPI for vehicles with fact activity, not fleet master status.",
    "c_t1_kpi_util": "Executive KPI for ratio-of-sums shift utilization across completed shifts.",
    "c_t1_trend": "BQ01 monthly revenue trend. Trip volume is intentionally separated to avoid a mixed-unit axis.",
    "c_t1_trip_trend": "BQ01 monthly observed-trip trend aligned with, but visually separated from, total payment revenue.",
    "c_t1_borough": "BQ01 pickup borough ranking for capacity planning.",
    "c_t2_heatmap": "BQ01 demand heatmap by ordered weekday label and pickup hour.",
    "c_t2_zone_hour": "BQ01 primary output: observed trips by pickup zone and pickup hour; served demand is not unmet demand.",
    "c_t2_hourly": "BQ01 hourly demand profile for shift staffing windows.",
    "c_t2_zone_trips": "BQ01 Pareto-style pickup zone concentration table.",
    "c_t2_zone_revenue": "BQ01 zone value profile comparing observed-trip volume with revenue per trip; it replaces a redundant second ranking.",
    "c_t3_kpi_shifts": "BQ02 completed shifts for the latest available reporting month.",
    "c_t3_kpi_rev_hour": "BQ02 revenue per scheduled shift hour for the latest reporting month using a ratio of additive components.",
    "c_t3_kpi_util": "BQ03 drivers meeting the explicit latest-month peer-review rule.",
    "c_t3_driver_scatter": "BQ03 latest-month peer matrix using three action statuses: needs review, peer range and below minimum sample.",
    "c_t3_driver_ranking": "BQ03 latest-month review queue driven by the certified needs_review rule.",
    "c_t3_shift_review": "BQ02 latest-month shift action queue ranked from lowest utilization upward.",
    "c_t3_vehicle_review": "BQ04 latest-month provisional vehicle peer-review queue; threshold needs business-owner validation.",
    "c_t4_kpi_dq": "BQ05 DQ issue-event count for the latest successful NDS run, including a valid zero state.",
    "c_t4_kpi_quarantine": "BQ05 quarantined-row count for the latest successful NDS run.",
    "c_t4_kpi_loaded": "BQ05 loaded-row reconciliation for the latest successful NDS run.",
    "c_t4_dq_trend": "BQ05 successful NDS run health table, including row reconciliation and valid zero-event runs.",
    "c_t4_dq_rules": "BQ05 historical DQ findings by rule and source; issue events are not unique affected records.",
    "c_t5_slice": "OLAP01 single-member slice for Manhattan in July 2021, displayed as an hourly profile.",
    "c_t5_dice": "OLAP01 dice example across month, borough and vehicle type.",
    "c_t5_drilldown": "OLAP01 drill detail for the July 2021 Manhattan member at day-by-hour grain.",
    "c_t5_rollup": "OLAP01 location hierarchy roll-up from pickup zone to borough for 2021.",
    "c_t5_pivot": "OLAP01 pivot example for borough by pickup hour bucket.",
    "c_dm_model_run": "DM01 published model-run metadata, training window, features, K, silhouette and driver coverage.",
    "c_dm_driver_scatter": "DM01 driver segmentation scatter for coaching and dispatch support.",
    "c_dm_driver_table": "DM01 segment profile table for operational interpretation.",
    "c_dm_rules_run": "DM02 published association-rule run metadata, thresholds, basket count and publication cap.",
    "c_dm_rules_table": "DM02 published route and demand association rules ranked by lift.",
}

# Dashboard-facing language is intentionally consistent. The underlying metric
# identifiers stay stable for API and contract compatibility.
METRIC_LABEL_OVERRIDES = {
    "total_trips": "Observed trips",
    "total_revenue": "Total payment revenue",
    "fare_revenue": "Fare revenue",
    "total_tips": "Tips",
    "total_distance": "Trip distance",
    "total_trip_minutes": "Trip minutes",
    "average_fare": "Average fare",
    "average_trip_distance": "Average trip distance",
    "average_trip_duration": "Average trip duration",
    "anomaly_trip_count": "Trip anomaly cases",
    "anomaly_rate": "Trip anomaly rate",
    "active_driver_count": "Drivers with trip activity",
    "active_vehicle_count": "Vehicles with trip activity",
    "completed_shifts": "Completed shifts",
    "trips_per_shift": "Trips / shift",
    "revenue_per_shift": "Revenue / shift",
    "revenue_per_hour": "Revenue / scheduled shift hour",
    "occupied_minutes": "Occupied minutes",
    "idle_minutes": "Idle minutes",
    "avg_idle_minutes": "Idle minutes / shift",
    "idle_minutes_per_shift": "Idle minutes / shift",
    "shift_duration_minutes": "Scheduled shift minutes",
    "utilization_rate": "Shift utilization",
    "anomaly_shift_count": "Shift anomaly cases",
    "dq_issue_count": "DQ issue events",
    "quarantine_count": "Quarantined rows",
    "rows_loaded": "Rows loaded",
    "batch_count": "Successful NDS runs",
    "run_recency_rank": "Run recency",
    "cum_trips_pct": "Cumulative trip share",
    "revenue_per_trip": "Revenue / trip",
    "cum_revenue_pct": "Cumulative revenue share",
    "driver_count": "Drivers covered",
    "review_driver_count": "Drivers needing review",
    "review_vehicle_count": "Vehicles needing review",
    "revenue_per_hour_percentile": "Revenue/hour percentile",
    "utilization_percentile": "Peer utilization percentile",
    "priority_rank": "Priority rank",
    "avg_driver_revenue_per_hour": "Avg. driver revenue / shift hour",
    "avg_driver_utilization_rate": "Avg. driver shift utilization",
    "published_rule_count": "Published rules",
    "rule_support": "Support",
    "rule_confidence": "Confidence",
    "rule_lift": "Lift",
}

COLUMN_LABEL_OVERRIDES = {
    "pickup_zone": "Pickup zone",
    "pickup_borough": "Pickup borough",
    "pickup_hour": "Pickup hour",
    "pickup_weekday_label": "Pickup weekday",
    "driver_id": "Driver ID",
    "driver_name": "Driver name",
    "review_reason": "Review reason",
    "review_status": "Review status",
    "revenue_per_hour_percentile": "Revenue/hour percentile",
    "reporting_month": "Reporting month",
    "monthly_utilization_rank": "Priority rank",
    "shift_id": "Shift ID",
    "shift_start": "Shift start",
    "vehicle_id": "Vehicle ID",
    "vehicle_type": "Vehicle type",
    "utilization_percentile": "Peer utilization percentile",
    "rule_code": "DQ rule",
    "source_system_code": "Source system",
    "source_entity": "Source entity",
    "severity": "Severity",
    "batch_completed_at": "Run completed (UTC)",
    "pickup_year": "Year",
    "pickup_month": "Month",
    "pickup_day": "Day",
    "pickup_hour_bucket": "Hour band",
    "model_run_at": "Model run (UTC)",
    "training_start": "Training start",
    "training_end": "Training end",
    "feature_set": "Feature set",
    "model_k": "K",
    "silhouette_score": "Silhouette score",
    "segment_label": "Driver segment",
    "antecedent": "If",
    "consequent": "Then",
    "basket_count": "Baskets",
    "rules_generated": "Rules generated",
    "rules_published": "Rules published",
    "min_support": "Minimum support",
    "min_confidence": "Minimum confidence",
    "min_lift": "Minimum lift",
}

TRIP_METRICS = {
    "total_trips": ("Tổng số chuyến", "COUNT(trip_id)", ",d"),
    "total_revenue": ("Tổng doanh thu", "COALESCE(SUM(total_amount), 0)", "$,.2f"),
    "fare_revenue": ("Tổng cước gốc", "COALESCE(SUM(fare_amount), 0)", "$,.2f"),
    "total_tips": ("Tổng tiền tip", "COALESCE(SUM(tip_amount), 0)", "$,.2f"),
    "total_distance": ("Tổng quãng đường", "COALESCE(SUM(trip_distance), 0)", ",.2f"),
    "total_trip_minutes": (
        "Tổng phút chuyến đi",
        "COALESCE(SUM(trip_duration_minutes), 0)",
        ",.2f",
    ),
    "average_fare": (
        "Cước trung bình",
        "SUM(fare_amount) / NULLIF(COUNT(trip_id), 0)",
        "$,.2f",
    ),
    "average_trip_distance": (
        "Quãng đường trung bình",
        "SUM(trip_distance) / NULLIF(COUNT(trip_distance), 0)",
        ",.2f",
    ),
    "average_trip_duration": (
        "Thời lượng chuyến trung bình",
        "SUM(trip_duration_minutes) / NULLIF(COUNT(trip_duration_minutes), 0)",
        ",.2f",
    ),
    "anomaly_trip_count": (
        "Số chuyến bất thường",
        "COUNT(*) FILTER (WHERE is_trip_anomaly)",
        ",d",
    ),
    "anomaly_rate": (
        "Tỷ lệ chuyến bất thường",
        "COUNT(*) FILTER (WHERE is_trip_anomaly)::numeric / NULLIF(COUNT(*), 0)",
        ".2%",
    ),
    "active_driver_count": (
        "Số tài xế hoạt động",
        "COUNT(DISTINCT driver_key)",
        ",d",
    ),
    "active_vehicle_count": (
        "Số xe hoạt động",
        "COUNT(DISTINCT vehicle_key)",
        ",d",
    ),
}

SHIFT_METRICS = {
    "completed_shifts": ("Số ca hoàn tất", "COUNT(shift_id)", ",d"),
    "total_revenue": ("Tổng doanh thu theo ca", "COALESCE(SUM(total_revenue), 0)", "$,.2f"),
    "total_tips": ("Tổng tiền tip theo ca", "COALESCE(SUM(total_tips), 0)", "$,.2f"),
    "trips_per_shift": (
        "Số chuyến trung bình mỗi ca",
        "SUM(trip_count)::numeric / NULLIF(COUNT(shift_id), 0)",
        ",.2f",
    ),
    "revenue_per_shift": (
        "Doanh thu trung bình mỗi ca",
        "SUM(total_revenue) / NULLIF(COUNT(shift_id), 0)",
        "$,.2f",
    ),
    "revenue_per_hour": (
        "Doanh thu mỗi giờ ca",
        "SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0)",
        "$,.2f",
    ),
    "occupied_minutes": (
        "Tổng phút có khách",
        "COALESCE(SUM(occupied_minutes), 0)",
        ",.2f",
    ),
    "idle_minutes": ("Tổng phút rảnh", "COALESCE(SUM(idle_minutes), 0)", ",.2f"),
    "avg_idle_minutes": (
        "Phút rảnh trung bình ca",
        "SUM(idle_minutes)::numeric / NULLIF(COUNT(shift_id), 0)",
        ",.2f",
    ),
    "shift_duration_minutes": (
        "Tổng phút ca",
        "COALESCE(SUM(shift_duration_minutes), 0)",
        ",.2f",
    ),
    "utilization_rate": (
        "Tỷ lệ sử dụng ca",
        "SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0)",
        ".2%",
    ),
    "priority_rank": (
        "Thứ tự ưu tiên",
        "MIN(monthly_utilization_rank)",
        ",d",
    ),
    "anomaly_shift_count": (
        "Số ca bất thường",
        "COUNT(*) FILTER (WHERE is_shift_anomaly)",
        ",d",
    ),
}

DQ_METRICS = {
    "dq_issue_count": ("Tổng số lỗi DQ", "COALESCE(SUM(issue_count), 0)", ",d"),
    "quarantine_count": ("Số dòng bị cách ly", "COALESCE(SUM(quarantine_count), 0)", ",d"),
}

PARETO_METRICS = {
    "total_trips": ("Tổng số chuyến", "SUM(trips)", ",d"),
    "cum_trips_pct": ("Tỷ lệ tích lũy chuyến", "MAX(cum_trips_pct)", ".2%"),
    "total_revenue": ("Tổng doanh thu", "SUM(revenue)", "$,.2f"),
    "revenue_per_trip": ("Doanh thu mỗi chuyến", "SUM(revenue) / NULLIF(SUM(trips), 0)", "$,.2f"),
    "cum_revenue_pct": ("Tỷ lệ tích lũy doanh thu", "MAX(cum_revenue_pct)", ".2%"),
}

ZONE_HOUR_METRICS = {
    "total_trips": ("Observed trips", "SUM(observed_trips)", ",d"),
    "total_revenue": ("Total payment revenue", "SUM(total_revenue)", "$,.2f"),
}

DRIVER_PERFORMANCE_METRICS = {
    "driver_count": ("Số tài xế", "COUNT(driver_key)", ",d"),
    "completed_shifts": ("Số ca hoàn tất", "SUM(completed_shifts)", ",d"),
    "revenue_per_hour": ("Doanh thu mỗi giờ ca", "AVG(revenue_per_hour)", "$,.2f"),
    "utilization_rate": ("Tỷ lệ sử dụng ca", "AVG(utilization_rate)", ".2%"),
    "idle_minutes_per_shift": (
        "Phút rảnh trung bình mỗi ca",
        "AVG(idle_minutes_per_shift)",
        ",.2f",
    ),
    "trips_per_shift": ("Số chuyến trung bình mỗi ca", "AVG(trips_per_shift)", ",.2f"),
    "review_driver_count": (
        "Số tài xế cần xem xét",
        "COUNT(*) FILTER (WHERE needs_review)",
        ",d",
    ),
}

OLAP_TRIP_METRICS = {
    "total_trips": ("Tổng số chuyến", "COALESCE(SUM(total_trips), 0)", ",d"),
    "total_revenue": ("Tổng doanh thu", "COALESCE(SUM(total_revenue), 0)", "$,.2f"),
    "fare_revenue": ("Tổng cước gốc", "COALESCE(SUM(fare_revenue), 0)", "$,.2f"),
    "total_tips": ("Tổng tiền tip", "COALESCE(SUM(total_tips), 0)", "$,.2f"),
    "total_distance": ("Tổng quãng đường", "COALESCE(SUM(total_distance), 0)", ",.2f"),
    "total_trip_minutes": (
        "Tổng phút chuyến đi",
        "COALESCE(SUM(total_trip_minutes), 0)",
        ",.2f",
    ),
    "average_fare": (
        "Cước trung bình",
        "SUM(fare_revenue) / NULLIF(SUM(total_trips), 0)",
        "$,.2f",
    ),
    "average_trip_distance": (
        "Quãng đường trung bình",
        "SUM(total_distance) / NULLIF(COUNT(trip_distance), 0)",
        ",.2f",
    ),
    "average_trip_duration": (
        "Thời lượng chuyến trung bình",
        "SUM(total_trip_minutes) / NULLIF(COUNT(trip_duration_minutes), 0)",
        ",.2f",
    ),
    "anomaly_trip_count": (
        "Số chuyến bất thường",
        "COALESCE(SUM(anomaly_trip_count), 0)",
        ",d",
    ),
    "anomaly_rate": (
        "Tỷ lệ chuyến bất thường",
        "SUM(anomaly_trip_count)::numeric / NULLIF(SUM(total_trips), 0)",
        ".2%",
    ),
    "active_driver_count": (
        "Số tài xế hoạt động",
        "COUNT(DISTINCT driver_key)",
        ",d",
    ),
    "active_vehicle_count": (
        "Số xe hoạt động",
        "COUNT(DISTINCT vehicle_key)",
        ",d",
    ),
}

OLAP_SHIFT_METRICS = {
    "completed_shifts": ("Số ca hoàn tất", "COALESCE(SUM(completed_shifts), 0)", ",d"),
    "total_trips": ("Tổng số chuyến theo ca", "COALESCE(SUM(total_trips), 0)", ",d"),
    "total_revenue": ("Tổng doanh thu theo ca", "COALESCE(SUM(total_revenue), 0)", "$,.2f"),
    "total_tips": ("Tổng tiền tip theo ca", "COALESCE(SUM(total_tips), 0)", "$,.2f"),
    "trips_per_shift": (
        "Số chuyến trung bình mỗi ca",
        "SUM(total_trips)::numeric / NULLIF(SUM(completed_shifts), 0)",
        ",.2f",
    ),
    "revenue_per_shift": (
        "Doanh thu trung bình mỗi ca",
        "SUM(total_revenue) / NULLIF(SUM(completed_shifts), 0)",
        "$,.2f",
    ),
    "revenue_per_hour": (
        "Doanh thu mỗi giờ ca",
        "SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes), 0)",
        "$,.2f",
    ),
    "occupied_minutes": (
        "Tổng phút có khách",
        "COALESCE(SUM(occupied_minutes), 0)",
        ",.2f",
    ),
    "idle_minutes": ("Tổng phút rảnh", "COALESCE(SUM(idle_minutes), 0)", ",.2f"),
    "shift_duration_minutes": (
        "Tổng phút ca",
        "COALESCE(SUM(shift_duration_minutes), 0)",
        ",.2f",
    ),
    "utilization_rate": (
        "Tỷ lệ sử dụng ca",
        "SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0)",
        ".2%",
    ),
    "anomaly_shift_count": (
        "Số ca bất thường",
        "COALESCE(SUM(anomaly_shift_count), 0)",
        ",d",
    ),
}


def certification_extra(certified: bool = True) -> str:
    if not certified:
        return json.dumps(
            {
                "semantic_status": "exploratory",
                "details": "Exploratory output: validate model provenance and operational thresholds before action.",
            }
        )
    return json.dumps(
        {
            "certification": {
                "certified_by": CERTIFIED_BY,
                "details": CERTIFICATION_DETAILS,
            }
        }
    )


def warehouse_uri() -> str:
    user = quote_plus(os.environ["SUPERSET_WAREHOUSE_USER"])
    password = quote_plus(os.environ["SUPERSET_WAREHOUSE_PASSWORD"])
    host = os.environ["SUPERSET_WAREHOUSE_HOST"]
    port = os.environ.get("SUPERSET_WAREHOUSE_PORT", "5432")
    database = os.environ["SUPERSET_WAREHOUSE_DB"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def ensure_database() -> Database:
    database = db.session.query(Database).filter_by(database_name=DATABASE_NAME).one_or_none()
    if database is None:
        database = Database(database_name=DATABASE_NAME)
        db.session.add(database)
    database.sqlalchemy_uri = warehouse_uri()
    database.expose_in_sqllab = True
    database.allow_dml = False
    database.allow_ctas = False
    database.allow_cvas = False
    database.allow_file_upload = False
    database.extra = json.dumps(
        {
            "metadata_params": {},
            "engine_params": {"connect_args": {"options": "-c statement_timeout=120000"}},
            "schemas_allowed_for_file_upload": [],
        }
    )
    db.session.flush()
    return database


def ensure_dataset(database: Database, table_name: str, spec: dict[str, str]) -> SqlaTable:
    dataset = (
        db.session.query(SqlaTable)
        .filter_by(database_id=database.id, schema="analytics", table_name=table_name)
        .one_or_none()
    )
    if dataset is None:
        dataset = SqlaTable(
            database=database,
            schema="analytics",
            table_name=table_name,
        )
        db.session.add(dataset)
        db.session.flush()
    dataset.main_dttm_col = spec["main_dttm_col"]
    dataset.description = spec["description"]
    dataset.extra = certification_extra(spec.get("certified", True))
    dataset.fetch_metadata()
    for column in dataset.columns:
        column.verbose_name = COLUMN_LABEL_OVERRIDES.get(
            column.column_name,
            column.verbose_name,
        )
    db.session.flush()
    return dataset


def ensure_metrics(
    dataset: SqlaTable,
    definitions: dict[str, tuple[str, str, str]],
    *,
    certified: bool = True,
) -> None:
    existing = {metric.metric_name: metric for metric in dataset.metrics}
    for metric_name, metric in existing.items():
        if metric_name not in definitions:
            db.session.delete(metric)
    for metric_name, (verbose_name, expression, d3format) in definitions.items():
        metric = existing.get(metric_name)
        if metric is None:
            metric = SqlMetric(metric_name=metric_name, table=dataset)
            db.session.add(metric)
        metric.verbose_name = METRIC_LABEL_OVERRIDES.get(metric_name, verbose_name)
        metric.expression = expression
        status = CERTIFICATION_DETAILS if certified else "Exploratory metric; not a certified KPI."
        metric.description = f"Metric ID: {metric_name}. {status}"
        metric.d3format = d3format
        metric.extra = certification_extra(certified)


def chart_params(dataset: SqlaTable, viz_type: str, **kwargs: object) -> str:
    params = {
        "datasource": f"{dataset.id}__table",
        "viz_type": viz_type,
        "adhoc_filters": [],
        "time_range": "No filter",
        "row_limit": 10000,
        "show_legend": False,
        "truncate_metric": True,
    }
    params.update(kwargs)
    return json.dumps(params)


def ensure_chart(
    admin: object,
    dataset: SqlaTable,
    name: str,
    viz_type: str,
    description: str | None = None,
    **params: object,
) -> Slice:
    chart = db.session.query(Slice).filter_by(slice_name=name).one_or_none()
    if chart is None:
        chart = Slice(slice_name=name)
        db.session.add(chart)
    chart.datasource_id = dataset.id
    chart.datasource_type = "table"
    chart.datasource_name = f"analytics.{dataset.table_name}"
    chart.viz_type = viz_type
    chart.params = chart_params(dataset, viz_type, **params)
    chart.description = description or f"Green Taxi certified chart using analytics.{dataset.table_name}."
    exploratory = dataset.table_name in {"current_driver_segments", "current_route_association_rules", "vehicle_performance_monthly"}
    chart.certified_by = None if exploratory else CERTIFIED_BY
    chart.certification_details = (
        "Exploratory chart; validate model run and provisional thresholds before action."
        if exploratory
        else CERTIFICATION_DETAILS
    )
    chart.owners = [admin]

    # Generate query_context dynamically to enable REST API v1 chart data retrieval
    query_obj = {
        "time_range": "No filter",
        "row_limit": params.get("row_limit") or 10000,
    }
    simple_filters = []
    for adhoc_filter in params.get("adhoc_filters", []):
        if adhoc_filter.get("expressionType") == "SIMPLE":
            simple_filters.append(
                {
                    "col": adhoc_filter.get("subject"),
                    "op": adhoc_filter.get("operator"),
                    "val": adhoc_filter.get("comparator"),
                }
            )
    if simple_filters:
        query_obj["filters"] = simple_filters

    # Map parameters to query context object based on viz_type
    if viz_type == "big_number_total":
        query_obj["metrics"] = [params.get("metric")]
    elif viz_type == "bubble":
        query_obj["metrics"] = [params.get("x"), params.get("y"), params.get("size")]
        query_obj["columns"] = [params.get("entity")]
    elif viz_type == "heatmap_v2":
        query_obj["metrics"] = [params.get("metric")]
        query_obj["columns"] = [params.get("x_axis"), params.get("groupby")]
    elif viz_type == "pie":
        query_obj["metrics"] = [params.get("metric")]
        query_obj["columns"] = params.get("groupby", [])
    elif viz_type == "table":
        query_obj["metrics"] = params.get("metrics", [])
        query_obj["columns"] = params.get("groupby", [])
        if "order_by_cols" in params:
            orderby_list = []
            for col_order in params["order_by_cols"]:
                if isinstance(col_order, str):
                    try:
                        col_order = json.loads(col_order)
                    except Exception:
                        pass
                if isinstance(col_order, list) and len(col_order) == 2:
                    orderby_list.append(col_order)
            if orderby_list:
                query_obj["orderby"] = orderby_list
    elif viz_type == "pivot_table_v2":
        row_columns = params.get("groupbyRows", [])
        column_columns = params.get("groupbyColumns", [])
        query_obj["metrics"] = params.get("metrics", [])
        query_obj["columns"] = row_columns + column_columns
        query_obj["series_columns"] = row_columns
    elif viz_type in ("echarts_timeseries_line", "echarts_timeseries_bar"):
        query_obj["metrics"] = params.get("metrics", [])
        if "granularity_sqla" in params:
            query_obj["granularity"] = params["granularity_sqla"]
            query_obj["time_grain_sqla"] = params.get("time_grain_sqla")
        if "x_axis" in params:
            query_obj["columns"] = [params["x_axis"]]

    chart.query_context = json.dumps({
        "datasource": {"id": dataset.id, "type": "table"},
        "force": False,
        "queries": [query_obj],
        "result_format": "json",
        "result_type": "full"
    })

    db.session.flush()
    return chart


def dashboard_layout(charts_by_id: dict[str, Slice]) -> str:
    layout: dict[str, object] = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
        "GRID_ID": {
            "id": "GRID_ID",
            "type": "GRID",
            "children": ["TABS_ID"],
            "parents": ["ROOT_ID"],
        },
        "TABS_ID": {
            "id": "TABS_ID",
            "type": "TABS",
            "children": ["TAB-1", "TAB-2", "TAB-3", "TAB-4", "TAB-5", "TAB-6"],
            "parents": ["ROOT_ID", "GRID_ID"],
        },
    }

    tab_rows = {
        "TAB-1": [
            ("TAB1-KPI", ["c_t1_kpi_rev", "c_t1_kpi_trips", "c_t1_kpi_drv", "c_t1_kpi_veh", "c_t1_kpi_util"]),
            ("TAB1-TRENDS", ["c_t1_trend", "c_t1_trip_trend"]),
            ("TAB1-MARKET", ["c_t1_borough"]),
        ],
        "TAB-2": [
            ("TAB2-HERO", ["c_t2_zone_hour"]),
            ("TAB2-TIME", ["c_t2_heatmap", "c_t2_hourly"]),
            ("TAB2-ZONES", ["c_t2_zone_trips", "c_t2_zone_revenue"]),
        ],
        "TAB-3": [
            ("TAB3-KPI", ["c_t3_kpi_shifts", "c_t3_kpi_rev_hour", "c_t3_kpi_util"]),
            ("TAB3-DRIVER", ["c_t3_driver_ranking"]),
            ("TAB3-PEERS", ["c_t3_driver_scatter", "c_t3_vehicle_review"]),
            ("TAB3-SHIFTS", ["c_t3_shift_review"]),
        ],
        "TAB-4": [
            ("TAB4-KPI", ["c_t4_kpi_dq", "c_t4_kpi_quarantine", "c_t4_kpi_loaded"]),
            ("TAB4-MAIN", ["c_t4_dq_trend"]),
            ("TAB4-INVESTIGATE", ["c_t4_dq_rules"]),
        ],
        "TAB-5": [
            ("TAB5-PIVOT", ["c_t5_pivot"]),
            ("TAB5-HIERARCHY", ["c_t5_slice", "c_t5_rollup"]),
            ("TAB5-EXPLORERS", ["c_t5_dice", "c_t5_drilldown"]),
        ],
        "TAB-6": [
            ("TAB6-MODEL", ["c_dm_model_run"]),
            ("TAB6-RULE-MODEL", ["c_dm_rules_run"]),
            ("TAB6-DRIVER", ["c_dm_driver_scatter", "c_dm_driver_table"]),
            ("TAB6-RULES", ["c_dm_rules_table"]),
        ],
    }
    tab_titles = {
        "TAB-1": "Executive pulse",
        "TAB-2": "Demand patterns",
        "TAB-3": "Workforce actions",
        "TAB-4": "Trust & data health",
        "TAB-5": "OLAP lab",
        "TAB-6": "Exploratory models",
    }
    tab_context = {
        "TAB-1": "## Executive pulse\n**Certified historical view · 01 Jan 2020–31 Jul 2021 · America/New_York.** Revenue and trip volume use aligned small multiples, never a shared mixed-unit axis.",
        "TAB-2": "## Demand patterns\nObserved trips measure served activity, not unmet demand. Read the zone × hour pattern first, then use concentration and value views to prioritize investigation.",
        "TAB-3": "## Workforce action center\nAll action views use the latest available reporting month. Peer flags are triage signals; validate sample size and the underlying shift before action.",
        "TAB-4": "## Trust & data health\nLatest successful NDS run is selected dynamically from audit metadata, including valid zero-event runs. Historical rule findings remain available below; empty anomaly queues are intentionally suppressed.",
        "TAB-5": "## OLAP analysis lab\nFive explicit operations on the approved cube: slice, dice, drill-down, roll-up and pivot. Every visual uses one unit per axis and names its selected members.",
        "TAB-6": "## Exploratory models — not certified KPIs\nK-Means and Apriori outputs require a published model run, training window and thresholds before operational use.",
    }

    kpi_keys = {
        key
        for rows in tab_rows.values()
        for row_name, keys in rows
        if row_name.endswith("KPI")
        for key in keys
    }
    wide_keys = {"c_t1_trend", "c_t1_trip_trend", "c_t2_zone_hour", "c_t3_driver_ranking", "c_t3_shift_review", "c_t4_dq_trend", "c_t5_pivot", "c_dm_rules_table"}
    compact_keys = {"c_t1_borough", "c_t4_dq_trend", "c_t4_dq_rules", "c_dm_model_run", "c_dm_rules_run"}

    for tab_id, rows in tab_rows.items():
        layout[tab_id] = {
            "id": tab_id,
            "type": "TAB",
            "children": [f"MARKDOWN-{tab_id}"] + [row_id for row_id, _ in rows],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID"],
            "meta": {"text": tab_titles[tab_id]},
        }
        layout[f"MARKDOWN-{tab_id}"] = {
            "id": f"MARKDOWN-{tab_id}",
            "type": "MARKDOWN",
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", tab_id],
            "meta": {"code": tab_context[tab_id], "height": 12, "width": 12},
        }
        for row_id, keys in rows:
            chart_ids = [
                f"CHART-{charts_by_id[key].id}" for key in keys if key in charts_by_id
            ]
            layout[row_id] = {
                "id": row_id,
                "type": "ROW",
                "children": chart_ids,
                "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", tab_id],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            for key in keys:
                if key not in charts_by_id:
                    continue
                chart = charts_by_id[key]
                position = keys.index(key)
                two_column_widths = {
                    "TAB2-TIME": [7, 5],
                    "TAB2-ZONES": [7, 5],
                    "TAB3-PEERS": [4, 8],
                    "TAB5-EXPLORERS": [5, 7],
                    "TAB6-DRIVER": [8, 4],
                }
                row_widths = {
                    1: [12],
                    2: two_column_widths.get(row_id, [6, 6]),
                    3: [4, 4, 4],
                    4: [3, 3, 3, 3],
                    5: [3, 3, 2, 2, 2],
                }
                width = row_widths.get(len(chart_ids), [12 // len(chart_ids)] * len(chart_ids))[position]
                height = 16 if key in kpi_keys else 42
                if key in wide_keys:
                    height = 46
                if key in compact_keys:
                    height = 26
                layout[f"CHART-{chart.id}"] = {
                    "id": f"CHART-{chart.id}",
                    "type": "CHART",
                    "children": [],
                    "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", tab_id, row_id],
                    "meta": {
                        "chartId": chart.id,
                        "height": height,
                        "width": width,
                        "sliceName": chart.slice_name,
                    },
                }

    return json.dumps(layout)


def ensure_security_roles(datasets: dict[str, SqlaTable]) -> None:
    # 1. Custom Role GreenTaxiViewer
    role_name = "GreenTaxiViewer"
    role = security_manager.find_role(role_name)
    if role is None:
        role = security_manager.add_role(role_name)

    gamma_role = security_manager.find_role("Gamma")
    if gamma_role is None:
        raise RuntimeError("Gamma role was not found in Superset security manager.")

    # Copy Gamma permissions
    role.permissions = list(gamma_role.permissions)

    # Add datasource access for all analytics datasets.
    for dataset in datasets.values():
        perm = dataset.get_perm()
        pvm = security_manager.find_permission_view_menu("datasource_access", perm)
        if pvm is None:
            pvm = security_manager.add_permission_view_menu("datasource_access", perm)
        if pvm not in role.permissions:
            role.permissions.append(pvm)

    # 2. Viewer User
    username = os.environ.get("SUPERSET_VIEWER_USERNAME", "superset_viewer")
    password = os.environ.get("SUPERSET_VIEWER_PASSWORD")
    if not password:
        raise ValueError(
            "SUPERSET_VIEWER_PASSWORD must be provided in the environment. "
            "Provisioning failed for security compliance."
        )

    viewer = security_manager.find_user(username=username)
    if viewer is None:
        security_manager.add_user(
            username=username,
            first_name="Viewer",
            last_name="GreenTaxi",
            email="viewer@greentaxi.local",
            role=[gamma_role, role],
            password=password
        )
    else:
        # Update user roles if exist to ensure correctness
        viewer.roles = [gamma_role, role]
        # Update password in database
        viewer.password = generate_password_hash(password)

    db.session.flush()
    db.session.commit()


def main() -> None:
    admin = security_manager.find_user(username=os.environ["SUPERSET_ADMIN_USERNAME"])
    if admin is None:
        raise RuntimeError("Superset admin user was not created.")

    database = ensure_database()
    datasets = {
        name: ensure_dataset(database, name, spec) for name, spec in DATASETS.items()
    }
    ensure_metrics(datasets["trip_pickup"], TRIP_METRICS)
    ensure_metrics(datasets["trip_dropoff"], TRIP_METRICS)
    ensure_metrics(datasets["shift"], SHIFT_METRICS)
    ensure_metrics(datasets["dq_summary"], DQ_METRICS)
    ensure_metrics(datasets["dq_batch_summary"], DQ_BATCH_METRICS)
    ensure_metrics(datasets["pareto_pickup_zone"], PARETO_METRICS)
    ensure_metrics(datasets["top_pickup_zone_hour"], ZONE_HOUR_METRICS)
    ensure_metrics(
        datasets["driver_performance_summary"],
        DRIVER_PERFORMANCE_METRICS,
    )
    ensure_metrics(datasets["driver_performance_monthly"], DRIVER_MONTHLY_METRICS)
    ensure_metrics(
        datasets["vehicle_performance_monthly"], VEHICLE_MONTHLY_METRICS, certified=False
    )
    ensure_metrics(datasets["olap_trip_cube"], OLAP_TRIP_METRICS)
    ensure_metrics(datasets["olap_shift_cube"], OLAP_SHIFT_METRICS)
    ensure_metrics(datasets["current_driver_segments"], DRIVER_SEGMENTS_METRICS, certified=False)
    ensure_metrics(
        datasets["current_route_association_rules"], ROUTE_ASSOCIATION_RULES_METRICS, certified=False
    )
    db.session.flush()

    charts_spec = {
        # Tab 1: Operations Overview
        "c_t1_kpi_rev": (datasets["trip_pickup"], "Total payment revenue", "big_number_total", {"metric": "total_revenue", "y_axis_format": "$,.3s"}),
        "c_t1_kpi_trips": (datasets["trip_pickup"], "Observed trips", "big_number_total", {"metric": "total_trips", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_drv": (datasets["trip_pickup"], "Drivers with trip activity", "big_number_total", {"metric": "active_driver_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_veh": (datasets["trip_pickup"], "Vehicles with trip activity", "big_number_total", {"metric": "active_vehicle_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_util": (datasets["shift"], "Shift utilization", "big_number_total", {"metric": "utilization_rate", "y_axis_format": ".2%"}),
        "c_t1_trend": (datasets["trip_pickup"], "Monthly total payment revenue", "echarts_timeseries_line", {
            "granularity_sqla": "pickup_datetime",
            "time_grain_sqla": "P1M",
            "metrics": ["total_revenue"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
            "show_legend": False,
        }),
        "c_t1_trip_trend": (datasets["trip_pickup"], "Monthly observed trips", "echarts_timeseries_line", {
            "granularity_sqla": "pickup_datetime",
            "time_grain_sqla": "P1M",
            "metrics": ["total_trips"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
            "show_legend": False,
        }),
        "c_t1_borough": (datasets["trip_pickup"], "Observed trips by pickup borough", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough", "groupby": [], "metrics": ["total_trips"],
            "orientation": "horizontal", "sort_series_type": "sum", "order_desc": True,
            "show_legend": False,
        }),

        # Tab 2: Demand Patterns
        "c_t2_zone_hour": (datasets["top_pickup_zone_hour"], "Observed trips by pickup zone and hour", "heatmap_v2", {
            "x_axis": "pickup_hour",
            "groupby": "pickup_zone_label",
            "metric": "total_trips",
            "row_limit": 1000,
            "linear_color_scheme": "schemeGreen",
            "show_legend": False,
        }),
        "c_t2_heatmap": (datasets["trip_pickup"], "Observed trips by weekday and hour", "heatmap_v2", {
            "x_axis": "pickup_hour",
            "groupby": "pickup_weekday_label",
            "metric": "total_trips",
            "linear_color_scheme": "schemeGreen",
            "show_legend": False,
        }),
        "c_t2_hourly": (datasets["trip_pickup"], "Observed trips by pickup hour", "echarts_timeseries_line", {
            "x_axis": "pickup_hour", "groupby": [], "metrics": ["total_trips"],
            "show_legend": False,
        }),
        "c_t2_zone_trips": (datasets["pareto_pickup_zone"], "Pickup-zone concentration", "table", {
            "query_mode": "aggregate",
            "groupby": ["pickup_zone", "pickup_borough"],
            "metrics": ["total_trips", "cum_trips_pct"],
            "order_by_cols": [json.dumps(["total_trips", False])],
            "timeseries_limit_metric": "total_trips",
            "order_desc": True,
            "row_limit": 500,
            "page_length": 15,
        }),
        "c_t2_zone_revenue": (datasets["pareto_pickup_zone"], "Zone value profile — volume vs revenue per trip", "bubble", {
            "series": "pickup_borough",
            "entity": "pickup_zone",
            "x": "total_trips",
            "y": "revenue_per_trip",
            "size": "total_revenue",
            "row_limit": 300,
            "show_legend": True,
        }),

        # Tab 3: latest-month workforce action center
        "c_t3_kpi_shifts": (datasets["driver_performance_monthly"], "Completed shifts — latest month", "big_number_total", {
            "metric": "completed_shifts",
            "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_reporting_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_driver_month_shifts"}],
        }),
        "c_t3_kpi_rev_hour": (datasets["driver_performance_monthly"], "Revenue / scheduled shift hour — latest month", "big_number_total", {
            "metric": "revenue_per_hour",
            "y_axis_format": "$,.2f",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_reporting_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_driver_month_revenue"}],
        }),
        "c_t3_kpi_util": (datasets["driver_performance_monthly"], "Drivers needing review — latest month", "big_number_total", {
            "metric": "review_driver_count",
            "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_reporting_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_driver_month_review_count"}],
        }),
        "c_t3_driver_scatter": (datasets["driver_performance_monthly"], "Driver peer matrix — latest month", "bubble", {
            "series": "review_status",
            "entity": "driver_id",
            "x": "utilization_rate",
            "y": "revenue_per_hour",
            "size": "completed_shifts",
            "row_limit": 1000,
            "show_legend": True,
            "label_colors": json.dumps({
                "Peer range": "#107C10",
                "Needs review": "#D13438",
                "Below minimum sample": "#8A8886",
            }),
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_reporting_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_driver_month_scatter"}],
        }),
        "c_t3_driver_ranking": (datasets["driver_performance_monthly"], "Driver review queue — latest month", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["driver_id", "driver_name", "review_reason"],
            "metrics": ["revenue_per_hour_percentile", "completed_shifts", "revenue_per_hour", "utilization_rate", "idle_minutes_per_shift"],
            "timeseries_limit_metric": "revenue_per_hour_percentile",
            "order_desc": False,
            "page_length": 15,
            "table_timestamp_format": "%b %Y",
            "adhoc_filters": [
                {
                    "expressionType": "SIMPLE",
                    "subject": "is_latest_reporting_month",
                    "operator": "==",
                    "comparator": True,
                    "clause": "WHERE",
                    "filterOptionName": "latest_driver_month_queue",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "needs_review",
                    "operator": "==",
                    "comparator": True,
                    "clause": "WHERE",
                    "filterOptionName": "driver_review_rule",
                }
            ],
        }),
        "c_t3_shift_review": (datasets["shift"], "30 lowest-utilization shifts — latest month", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["shift_id", "shift_start", "driver_id", "driver_name", "vehicle_id", "vehicle_type"],
            "metrics": ["priority_rank", "completed_shifts", "trips_per_shift", "revenue_per_hour", "utilization_rate", "avg_idle_minutes"],
            "timeseries_limit_metric": "priority_rank",
            "order_desc": False,
            "page_length": 15,
            "row_limit": 1000,
            "table_timestamp_format": "%d %b %Y %H:%M",
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "subject": "is_latest_shift_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_shift_month_queue"},
                {"expressionType": "SIMPLE", "subject": "monthly_utilization_rank", "operator": "<=", "comparator": 30, "clause": "WHERE", "filterOptionName": "lowest_thirty_shifts"},
            ],
        }),
        "c_t3_vehicle_review": (datasets["vehicle_performance_monthly"], "Vehicle peer-review queue — latest month · provisional", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["reporting_month", "vehicle_id", "vehicle_type"],
            "metrics": ["utilization_percentile", "completed_shifts", "revenue_per_hour", "utilization_rate"],
            "timeseries_limit_metric": "utilization_percentile",
            "order_desc": False,
            "page_length": 15,
            "table_timestamp_format": "%b %Y",
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "subject": "is_latest_reporting_month", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_vehicle_month_queue"},
                {"expressionType": "SIMPLE", "subject": "is_review_candidate", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "vehicle_review_rule"},
            ],
        }),

        # Tab 4: Data Quality & Anomalies
        "c_t4_kpi_dq": (datasets["dq_batch_summary"], "DQ issue events — latest successful run", "big_number_total", {
            "metric": "dq_issue_count", "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_dq_batch", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_dq_batch"}],
        }),
        "c_t4_kpi_quarantine": (datasets["dq_batch_summary"], "Quarantined rows — latest successful run", "big_number_total", {
            "metric": "quarantine_count", "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_dq_batch", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_quarantine_batch"}],
        }),
        "c_t4_kpi_loaded": (datasets["dq_batch_summary"], "Rows loaded — latest successful run", "big_number_total", {
            "metric": "rows_loaded", "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [{"expressionType": "SIMPLE", "subject": "is_latest_dq_batch", "operator": "==", "comparator": True, "clause": "WHERE", "filterOptionName": "latest_loaded_batch"}],
        }),
        "c_t4_dq_trend": (datasets["dq_batch_summary"], "Successful NDS run health", "table", {
            "query_mode": "aggregate",
            "groupby": ["batch_completed_at", "batch_status"],
            "metrics": ["run_recency_rank", "rows_loaded", "dq_issue_count", "quarantine_count"],
            "timeseries_limit_metric": "run_recency_rank",
            "order_desc": False,
            "page_length": 10,
            "row_limit": 100,
            "table_timestamp_format": "%d %b %Y %H:%M",
        }),
        "c_t4_dq_rules": (datasets["dq_summary"], "Historical DQ findings by rule", "table", {
            "query_mode": "aggregate",
            "groupby": ["rule_code", "source_system_code", "source_entity", "severity"],
            "metrics": ["dq_issue_count", "quarantine_count"],
            "order_by_cols": [json.dumps(["dq_issue_count", False])],
            "timeseries_limit_metric": "dq_issue_count",
            "order_desc": True,
            "page_length": 15,
        }),

        # Tab 5: OLAP Demo
        "c_t5_slice": (datasets["olap_trip_cube"], "Slice — Jul 2021 · Manhattan hourly profile", "echarts_timeseries_bar", {
            "x_axis": "pickup_hour",
            "groupby": [],
            "metrics": ["total_trips"],
            "show_legend": False,
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "subject": "pickup_year", "operator": "==", "comparator": 2021, "clause": "WHERE", "filterOptionName": "olap_slice_year"},
                {"expressionType": "SIMPLE", "subject": "pickup_month", "operator": "==", "comparator": 7, "clause": "WHERE", "filterOptionName": "olap_slice_month"},
                {"expressionType": "SIMPLE", "subject": "pickup_borough", "operator": "==", "comparator": "Manhattan", "clause": "WHERE", "filterOptionName": "olap_slice_borough"},
            ],
        }),
        "c_t5_dice": (datasets["olap_trip_cube"], "Dice subset — Q1 2021 · Manhattan/Queens · Sedan", "table", {
            "query_mode": "aggregate",
            "groupby": ["pickup_month", "pickup_borough", "vehicle_type"],
            "metrics": ["total_trips", "total_revenue", "average_fare"],
            "order_by_cols": [json.dumps(["total_revenue", False])],
            "page_length": 15,
            "adhoc_filters": [
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_year",
                    "operator": "==",
                    "comparator": 2021,
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_year",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_month",
                    "operator": "IN",
                    "comparator": [1, 2, 3],
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_month",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_borough",
                    "operator": "IN",
                    "comparator": ["Manhattan", "Queens"],
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_borough",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "vehicle_type",
                    "operator": "IN",
                    "comparator": ["SEDAN"],
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_vehicle_type",
                },
            ],
        }),
        "c_t5_drilldown": (datasets["olap_trip_cube"], "Drill detail — Jul 2021 · Manhattan day × hour", "heatmap_v2", {
            "x_axis": "pickup_hour",
            "groupby": "pickup_day",
            "metric": "total_trips",
            "row_limit": 1000,
            "linear_color_scheme": "schemeGreen",
            "show_legend": False,
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "subject": "pickup_year", "operator": "==", "comparator": 2021, "clause": "WHERE", "filterOptionName": "olap_drill_year"},
                {"expressionType": "SIMPLE", "subject": "pickup_month", "operator": "==", "comparator": 7, "clause": "WHERE", "filterOptionName": "olap_drill_month"},
                {"expressionType": "SIMPLE", "subject": "pickup_borough", "operator": "==", "comparator": "Manhattan", "clause": "WHERE", "filterOptionName": "olap_drill_borough"},
            ],
        }),
        "c_t5_rollup": (datasets["olap_trip_cube"], "Roll-up — 2021 pickup zone → borough", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough",
            "groupby": [],
            "metrics": ["total_trips"],
            "orientation": "horizontal",
            "sort_series_type": "sum",
            "order_desc": True,
            "show_legend": False,
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "subject": "pickup_year", "operator": "==", "comparator": 2021, "clause": "WHERE", "filterOptionName": "olap_rollup_year"},
            ],
        }),
        "c_t5_pivot": (datasets["olap_trip_cube"], "Pivot matrix — pickup borough × hour bucket", "pivot_table_v2", {
            "groupbyRows": ["pickup_borough"],
            "groupbyColumns": ["pickup_hour_bucket"],
            "metrics": ["total_trips"],
            "row_limit": 10000,
        }),

        # Tab 6: Exploratory Models
        "c_dm_model_run": (datasets["current_driver_segments"], "Published driver-segmentation model run", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["model_run_at", "training_start", "training_end", "feature_set", "model_k", "silhouette_score", "davies_bouldin_score", "stability_ari"],
            "metrics": ["driver_count", "model_stability_ari"],
            "order_by_cols": [json.dumps(["model_run_at", False])],
            "page_length": 5,
            "row_limit": 5,
            "table_timestamp_format": "%d %b %Y %H:%M",
        }),
        "c_dm_driver_scatter": (datasets["current_driver_segments"], "Driver segments — utilization vs revenue per shift hour", "bubble", {
            "series": "segment_label",
            "entity": "driver_id",
            "x": "avg_driver_utilization_rate",
            "y": "avg_driver_revenue_per_hour",
            "size": "completed_shifts",
            "row_limit": 1000,
            "show_legend": True,
        }),
        "c_dm_driver_table": (datasets["current_driver_segments"], "Segment profile — exploratory driver averages", "table", {
            "query_mode": "aggregate",
            "groupby": ["segment_label"],
            "metrics": ["driver_count", "completed_shifts", "avg_driver_revenue_per_hour", "avg_driver_utilization_rate", "idle_minutes_per_shift", "trips_per_shift"],
            "order_by_cols": [json.dumps(["avg_driver_revenue_per_hour", False])],
            "timeseries_limit_metric": "avg_driver_revenue_per_hour",
            "order_desc": True,
        }),
        "c_dm_rules_run": (datasets["current_route_association_rules"], "Published association-rule model run", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["model_run_at", "training_start", "training_end", "basket_count", "rules_generated", "min_support", "min_confidence", "min_lift"],
            "metrics": ["published_rule_count"],
            "page_length": 5,
            "row_limit": 5,
            "table_timestamp_format": "%d %b %Y %H:%M",
        }),
        "c_dm_rules_table": (datasets["current_route_association_rules"], "Published association rules — ranked by lift", "table", {
            "query_mode": "aggregate",
            "show_cell_bars": False,
            "groupby": ["antecedent", "consequent"],
            "metrics": ["rule_support", "rule_confidence", "rule_lift", "rule_stability"],
            "order_by_cols": [json.dumps(["rule_lift", False])],
            "timeseries_limit_metric": "rule_lift",
            "order_desc": True,
            "page_length": 15,
            "row_limit": 500,
        }),
    }

    charts = {}
    for key, (dataset, name, viz_type, params) in charts_spec.items():
        charts[key] = ensure_chart(
            admin,
            dataset,
            name,
            viz_type,
            description=CHART_DESCRIPTIONS.get(key),
            **params,
        )
    db.session.flush()

    # Retrieve existing slices of this dashboard and remove those not in our list
    dashboard = (
        db.session.query(Dashboard)
        .filter_by(slug="green-taxi-driver-operations")
        .one_or_none()
    )
    if dashboard is None:
        dashboard = Dashboard(slug="green-taxi-driver-operations")
        db.session.add(dashboard)

    # ------------------ IDEMPOTENT CLEANUP ------------------
    # Retrieve all existing slices currently associated with this dashboard
    old_slices = list(dashboard.slices) if dashboard.slices else []
    active_slice_ids = {c.id for c in charts.values()}

    # Clear association rows explicitly so replacing the collection is
    # idempotent even when SQLAlchemy has a previously loaded relationship.
    dashboard_slices = Dashboard.slices.property.secondary
    with db.session.no_autoflush:
        db.session.execute(
            dashboard_slices.delete().where(
                dashboard_slices.c.dashboard_id == dashboard.id
            )
        )
    set_committed_value(dashboard, "slices", [])

    # Delete slices from the metadata database if they are no longer active.
    for slc in old_slices:
        if slc.id not in active_slice_ids:
            db.session.delete(slc)
    db.session.flush()
    # --------------------------------------------------------

    dashboard.dashboard_title = "NYC Green Taxi - Driver Operations"
    dashboard.description = (
        "Operational monitoring dashboard with OLAP and Data Mining insights on PostgreSQL."
    )
    dashboard.certified_by = CERTIFIED_BY
    dashboard.certification_details = CERTIFICATION_DETAILS
    dashboard.published = True
    dashboard.owners = [admin]
    linked_slice_ids = set(
        db.session.execute(
            select(dashboard_slices.c.slice_id).where(
                dashboard_slices.c.dashboard_id == dashboard.id
            )
        ).scalars()
    )
    missing_links = [
        {"dashboard_id": dashboard.id, "slice_id": chart.id}
        for chart in charts.values()
        if chart.id not in linked_slice_ids
    ]
    if missing_links:
        with db.session.no_autoflush:
            db.session.execute(
                pg_insert(dashboard_slices).on_conflict_do_nothing(
                    index_elements=["dashboard_id", "slice_id"]
                ),
                missing_links,
            )
    set_committed_value(dashboard, "slices", list(charts.values()))
    dashboard.position_json = dashboard_layout(charts)
    dashboard.json_metadata = json.dumps(
        {
            "color_scheme": "supersetColors",
            "refresh_frequency": 0,
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "default_filters": "{}",
            "native_filter_configuration": [],
        }
    )
    dashboard.css = """
.dashboard,
.dashboard-container,
.dashboard-layout {
  background: #f4f7fb !important;
  color: #24364b !important;
  font-family: "Segoe UI", Inter, Arial, sans-serif !important;
}
.dashboard-header {
  background: #ffffff !important;
  border-bottom: 1px solid #dfe7f0 !important;
  box-shadow: 0 1px 3px rgba(31, 55, 78, 0.06) !important;
  padding: 10px 18px !important;
}
.dashboard-content {
  width: 100% !important;
  max-width: 1760px;
  margin: 0 auto;
  padding: 18px 20px 32px !important;
}
.dashboard-component-tabs .ant-tabs-nav {
  background: #ffffff !important;
  border: 1px solid #dfe7f0 !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(31, 55, 78, 0.04) !important;
  margin: 0 0 14px !important;
  padding: 4px 6px !important;
}
.dashboard-component-tabs .ant-tabs-tab {
  color: #5b6b7f !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  margin: 0 2px !important;
  padding: 9px 13px !important;
  transition: background 120ms ease, color 120ms ease !important;
}
.dashboard-component-tabs .ant-tabs-tab:hover {
  background: #f1f6fc !important;
  color: #0f6cbd !important;
}
.dashboard-component-tabs .ant-tabs-tab-active,
.dashboard-component-tabs .ant-tabs-tab-active * {
  background: #e7f1fb !important;
  color: #0f6cbd !important;
}
.dashboard-component-tabs .ant-tabs-ink-bar {
  background: transparent !important;
}
.dashboard-markdown {
  background: linear-gradient(110deg, #edf6ff 0%, #f7fbff 68%, #ffffff 100%) !important;
  border: 1px solid #d5e6f7 !important;
  border-left: 4px solid #0f6cbd !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(31, 55, 78, 0.04) !important;
  padding: 13px 17px !important;
}
.dashboard-markdown h2 {
  color: #17324d !important;
  font-size: 21px !important;
  font-weight: 650 !important;
  line-height: 28px !important;
  margin: 0 0 4px !important;
}
.dashboard-markdown p,
.dashboard-markdown strong {
  color: #53677d !important;
  font-size: 12px !important;
  line-height: 18px !important;
  margin: 0 !important;
}
.dashboard-component-chart-holder {
  background: #ffffff !important;
  border: 1px solid #dfe7f0 !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(31, 55, 78, 0.06) !important;
  overflow: hidden !important;
  transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease !important;
}
.dashboard-component-chart-holder:hover {
  border-color: #b8d3ed !important;
  box-shadow: 0 6px 18px rgba(31, 55, 78, 0.10) !important;
  transform: translateY(-1px) !important;
}
.chart-header,
[data-test="slice-header"] {
  background: #ffffff !important;
  border-bottom: 1px solid #edf1f6 !important;
  min-height: 42px !important;
  padding: 9px 13px 7px !important;
}
.chart-header .header-title,
[data-test="slice-header"] .header-title,
[data-test="slice-header"] .header-title a {
  color: #213547 !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  letter-spacing: 0 !important;
}
.dashboard-component-row {
  margin-bottom: 14px !important;
}
.slice_container {
  background: #ffffff !important;
  padding: 5px 11px 11px !important;
}
.big_number_total {
  color: #0f4c75 !important;
  font-weight: 650 !important;
}
.big_number_total .header-line,
.big_number_total .subheader-line {
  color: #0f4c75 !important;
}
[data-test="slice-header"] .header-controls svg {
  color: #6b7f94 !important;
}
.table-condensed > thead > tr > th {
  background: #f3f6fa !important;
  color: #40566d !important;
  border-color: #dfe7f0 !important;
  font-weight: 650 !important;
}
.table-condensed > tbody > tr > td {
  color: #2f4357 !important;
  border-color: #edf1f6 !important;
}
.table-condensed > tbody > tr:hover {
  background: #f5f9fd !important;
}
.cell-bar.positive {
  background: rgba(15, 108, 189, 0.18) !important;
}
.cell-bar.negative {
  background: rgba(209, 52, 56, 0.18) !important;
}
.ant-pagination-item-active {
  border-color: #0f6cbd !important;
}
.ant-pagination-item-active a {
  color: #0f6cbd !important;
}
@media (max-width: 1440px) {
  .dashboard-content { padding: 14px 12px 26px !important; }
  .dashboard-component-tabs .ant-tabs-tab { padding: 8px 9px !important; }
  .chart-header .header-title { font-size: 13px !important; }
}
"""
    db.session.flush()
    ensure_security_roles(datasets)
    db.session.commit()

    current_app.logger.info(
        "Successfully provisioned %s datasets, %s charts, role, viewer and dashboard %s",
        len(datasets),
        len(charts),
        dashboard.slug,
    )


main()

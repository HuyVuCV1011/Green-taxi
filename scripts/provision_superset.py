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
    "pareto_pickup_zone": {
        "main_dttm_col": None,
        "description": "One row per pickup zone; pre-calculated cumulative contribution metrics.",
    },
    "driver_performance_summary": {
        "main_dttm_col": None,
        "description": "One row per driver with peer percentiles and an explicit review rule.",
    },
    "olap_trip_cube": {
        "main_dttm_col": "pickup_datetime",
        "description": "ROLAP trip cube view for slice, dice, drill-down, roll-up and pivot demos.",
    },
    "olap_shift_cube": {
        "main_dttm_col": "shift_start",
        "description": "ROLAP shift cube view for utilization, idle time and revenue/hour demos.",
    },
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
    "cum_revenue_pct": ("Tỷ lệ tích lũy doanh thu", "MAX(cum_revenue_pct)", ".2%"),
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


def certification_extra() -> str:
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
    dataset.extra = certification_extra()
    dataset.fetch_metadata()
    db.session.flush()
    return dataset


def ensure_metrics(dataset: SqlaTable, definitions: dict[str, tuple[str, str, str]]) -> None:
    existing = {metric.metric_name: metric for metric in dataset.metrics}
    for metric_name, metric in existing.items():
        if metric_name not in definitions:
            db.session.delete(metric)
    for metric_name, (verbose_name, expression, d3format) in definitions.items():
        metric = existing.get(metric_name)
        if metric is None:
            metric = SqlMetric(metric_name=metric_name, table=dataset)
            db.session.add(metric)
        metric.verbose_name = verbose_name
        metric.expression = expression
        metric.description = f"Metric ID: {metric_name}. {CERTIFICATION_DETAILS}"
        metric.d3format = d3format
        metric.extra = certification_extra()


def chart_params(dataset: SqlaTable, viz_type: str, **kwargs: object) -> str:
    params = {
        "datasource": f"{dataset.id}__table",
        "viz_type": viz_type,
        "adhoc_filters": [],
        "time_range": "No filter",
        "row_limit": 10000,
        "show_legend": True,
        "truncate_metric": True,
    }
    params.update(kwargs)
    return json.dumps(params)


def ensure_chart(
    admin: object,
    dataset: SqlaTable,
    name: str,
    viz_type: str,
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
    chart.description = f"Green Taxi certified chart using analytics.{dataset.table_name}."
    chart.certified_by = CERTIFIED_BY
    chart.certification_details = CERTIFICATION_DETAILS
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
        query_obj["metrics"] = params.get("metrics", [])
        query_obj["columns"] = params.get("groupbyColumns", [])
        query_obj["series_columns"] = params.get("groupbyRows", [])
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
            "children": ["TAB-1", "TAB-2", "TAB-3", "TAB-4", "TAB-5"],
            "parents": ["ROOT_ID", "GRID_ID"],
        },
    }

    tab_rows = {
        "TAB-1": [
            ("TAB1-KPI", ["c_t1_kpi_rev", "c_t1_kpi_trips", "c_t1_kpi_drv", "c_t1_kpi_veh", "c_t1_kpi_util"]),
            ("TAB1-MAIN", ["c_t1_trend", "c_t1_borough"]),
            ("TAB1-SUPPORT", ["c_t1_zones", "c_t1_weekday"]),
        ],
        "TAB-2": [
            ("TAB2-MAIN", ["c_t2_heatmap", "c_t2_hourly"]),
            ("TAB2-ZONES", ["c_t2_zone_trips", "c_t2_zone_revenue"]),
            ("TAB2-GEO", ["c_t2_pickup_borough", "c_t2_dropoff_borough", "c_t2_distance_borough"]),
        ],
        "TAB-3": [
            ("TAB3-KPI", ["c_t3_kpi_shifts", "c_t3_kpi_rev_hour", "c_t3_kpi_trips_shift", "c_t3_kpi_util"]),
            ("TAB3-DRIVER", ["c_t3_driver_scatter", "c_t3_driver_ranking"]),
            ("TAB3-FLEET", ["c_t3_vehicle_type", "c_t3_vehicle_table"]),
        ],
        "TAB-4": [
            ("TAB4-KPI", ["c_t4_kpi_dq", "c_t4_kpi_quarantine", "c_t4_kpi_trip_anomaly", "c_t4_kpi_shift_anomaly"]),
            ("TAB4-MAIN", ["c_t4_dq_trend", "c_t4_dq_severity"]),
            ("TAB4-SUPPORT", ["c_t4_dq_source", "c_t4_dq_rules"]),
        ],
        "TAB-5": [
            ("TAB5-FILTERS", ["c_t5_slice", "c_t5_dice"]),
            ("TAB5-HIERARCHY", ["c_t5_drilldown", "c_t5_rollup"]),
            ("TAB5-PIVOT", ["c_t5_pivot"]),
        ],
    }
    tab_titles = {
        "TAB-1": "Operations Overview",
        "TAB-2": "Demand Patterns",
        "TAB-3": "Driver & Fleet Performance",
        "TAB-4": "Data Quality & Anomalies",
        "TAB-5": "OLAP Demo",
    }

    kpi_keys = {
        key
        for rows in tab_rows.values()
        for row_name, keys in rows
        if row_name.endswith("KPI")
        for key in keys
    }
    wide_keys = {"c_t1_trend", "c_t2_heatmap", "c_t3_driver_scatter", "c_t4_dq_trend", "c_t5_pivot"}

    for tab_id, rows in tab_rows.items():
        layout[tab_id] = {
            "id": tab_id,
            "type": "TAB",
            "children": [row_id for row_id, _ in rows],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID"],
            "meta": {"text": tab_titles[tab_id]},
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
                width = 12 // max(1, len(chart_ids))
                height = 24 if key in kpi_keys else 58
                if key in wide_keys:
                    height = 64
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
    ensure_metrics(datasets["pareto_pickup_zone"], PARETO_METRICS)
    ensure_metrics(
        datasets["driver_performance_summary"],
        DRIVER_PERFORMANCE_METRICS,
    )
    ensure_metrics(datasets["olap_trip_cube"], OLAP_TRIP_METRICS)
    ensure_metrics(datasets["olap_shift_cube"], OLAP_SHIFT_METRICS)
    db.session.flush()

    charts_spec = {
        # Tab 1: Operations Overview
        "c_t1_kpi_rev": (datasets["trip_pickup"], "Total Revenue", "big_number_total", {"metric": "total_revenue", "y_axis_format": "$,.2f"}),
        "c_t1_kpi_trips": (datasets["trip_pickup"], "Total Trips", "big_number_total", {"metric": "total_trips", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_drv": (datasets["trip_pickup"], "Active Drivers", "big_number_total", {"metric": "active_driver_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_veh": (datasets["trip_pickup"], "Active Vehicles", "big_number_total", {"metric": "active_vehicle_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_util": (datasets["shift"], "Overall Shift Utilization", "big_number_total", {"metric": "utilization_rate", "y_axis_format": ".2%"}),
        "c_t1_trend": (datasets["trip_pickup"], "Monthly Revenue & Trip Volume", "echarts_timeseries_line", {
            "granularity_sqla": "pickup_datetime",
            "time_grain_sqla": "P1M",
            "metrics": ["total_revenue", "total_trips"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
        }),
        "c_t1_borough": (datasets["trip_pickup"], "Trips by Pickup Borough", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough", "groupby": [], "metrics": ["total_trips"],
            "orientation": "horizontal", "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t1_zones": (datasets["trip_pickup"], "Top Pickup Zones", "echarts_timeseries_bar", {
            "x_axis": "pickup_zone", "groupby": [], "metrics": ["total_trips"],
            "orientation": "horizontal", "row_limit": 10, "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t1_weekday": (datasets["trip_pickup"], "Trips by Weekday", "echarts_timeseries_bar", {
            "x_axis": "pickup_day_name", "groupby": [], "metrics": ["total_trips"],
            "sort_series_type": "sum", "order_desc": False,
        }),

        # Tab 2: Demand Patterns
        "c_t2_heatmap": (datasets["trip_pickup"], "Demand by Weekday & Hour", "heatmap_v2", {
            "x_axis": "pickup_hour",
            "groupby": "pickup_day_name",
            "metric": "total_trips",
            "linear_color_scheme": "schemeGreen",
        }),
        "c_t2_hourly": (datasets["trip_pickup"], "Hourly Demand Profile", "echarts_timeseries_line", {
            "x_axis": "pickup_hour", "groupby": [], "metrics": ["total_trips"],
        }),
        "c_t2_zone_trips": (datasets["pareto_pickup_zone"], "Zone Concentration by Trips", "table", {
            "query_mode": "aggregate",
            "groupby": ["pickup_zone", "pickup_borough"],
            "metrics": ["total_trips", "cum_trips_pct"],
            "order_by_cols": [json.dumps(["total_trips", False])],
            "row_limit": 15,
            "page_length": 15,
        }),
        "c_t2_zone_revenue": (datasets["trip_pickup"], "Top Pickup Zones by Revenue", "echarts_timeseries_bar", {
            "x_axis": "pickup_zone", "groupby": [], "metrics": ["total_revenue"],
            "orientation": "horizontal", "row_limit": 15, "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t2_pickup_borough": (datasets["trip_pickup"], "Pickup Borough Volume", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough", "groupby": [], "metrics": ["total_trips"],
            "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t2_dropoff_borough": (datasets["trip_dropoff"], "Dropoff Borough Volume", "echarts_timeseries_bar", {
            "x_axis": "dropoff_borough", "groupby": [], "metrics": ["total_trips"],
            "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t2_distance_borough": (datasets["trip_pickup"], "Average Trip Distance by Borough", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough", "groupby": [], "metrics": ["average_trip_distance"],
            "sort_series_type": "sum", "order_desc": True,
        }),

        # Tab 3: Driver & Fleet Performance
        "c_t3_kpi_shifts": (datasets["shift"], "Completed Shifts", "big_number_total", {"metric": "completed_shifts", "y_axis_format": "SMART_NUMBER"}),
        "c_t3_kpi_rev_hour": (datasets["shift"], "Revenue per Shift Hour", "big_number_total", {"metric": "revenue_per_hour", "y_axis_format": "$,.2f"}),
        "c_t3_kpi_trips_shift": (datasets["shift"], "Trips per Shift", "big_number_total", {"metric": "trips_per_shift", "y_axis_format": ",.2f"}),
        "c_t3_kpi_util": (datasets["shift"], "Performance Shift Utilization", "big_number_total", {"metric": "utilization_rate", "y_axis_format": ".2%"}),
        "c_t3_driver_scatter": (datasets["driver_performance_summary"], "Driver Performance Matrix", "bubble", {
            "series": "driver_name",
            "entity": "driver_name",
            "x": "utilization_rate",
            "y": "revenue_per_hour",
            "size": "completed_shifts",
            "row_limit": 1000,
        }),
        "c_t3_driver_ranking": (datasets["driver_performance_summary"], "Driver Review Queue", "table", {
            "query_mode": "aggregate",
            "groupby": ["driver_name", "review_reason"],
            "metrics": ["completed_shifts", "revenue_per_hour", "utilization_rate", "idle_minutes_per_shift"],
            "order_by_cols": [json.dumps(["revenue_per_hour", True])],
            "page_length": 15,
            "adhoc_filters": [
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
        "c_t3_vehicle_type": (datasets["shift"], "Vehicle Type Performance", "echarts_timeseries_bar", {
            "x_axis": "vehicle_type",
            "groupby": [],
            "metrics": ["utilization_rate", "trips_per_shift"],
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t3_vehicle_table": (datasets["shift"], "Vehicle Performance Detail", "table", {
            "query_mode": "aggregate",
            "groupby": ["vehicle_id", "vehicle_type"],
            "metrics": ["completed_shifts", "trips_per_shift", "revenue_per_shift", "utilization_rate"],
            "order_by_cols": [json.dumps(["utilization_rate", True])],
            "page_length": 15,
        }),

        # Tab 4: Data Quality & Anomalies
        "c_t4_kpi_dq": (datasets["dq_summary"], "DQ Issues", "big_number_total", {"metric": "dq_issue_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t4_kpi_quarantine": (datasets["dq_summary"], "Quarantine Records", "big_number_total", {"metric": "quarantine_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t4_kpi_trip_anomaly": (datasets["trip_pickup"], "Trip Anomalies", "big_number_total", {"metric": "anomaly_trip_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t4_kpi_shift_anomaly": (datasets["shift"], "Shift Anomalies", "big_number_total", {"metric": "anomaly_shift_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t4_dq_trend": (datasets["dq_summary"], "DQ Issues over Time", "echarts_timeseries_line", {
            "granularity_sqla": "event_date_utc",
            "time_grain_sqla": "P1D",
            "metrics": ["dq_issue_count", "quarantine_count"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
        }),
        "c_t4_dq_severity": (datasets["dq_summary"], "Issues by Severity", "echarts_timeseries_bar", {
            "x_axis": "severity", "groupby": [], "metrics": ["dq_issue_count"],
            "sort_series_type": "sum", "order_desc": True,
        }),
        "c_t4_dq_source": (datasets["dq_summary"], "Issues by Source System", "echarts_timeseries_bar", {
            "x_axis": "source_system_code",
            "groupby": ["severity"],
            "metrics": ["dq_issue_count"],
            "bar_stacked": True,
        }),
        "c_t4_dq_rules": (datasets["dq_summary"], "Top Data Quality Rules", "table", {
            "query_mode": "aggregate",
            "groupby": ["rule_code", "source_entity", "severity"],
            "metrics": ["dq_issue_count", "quarantine_count"],
            "order_by_cols": [json.dumps(["dq_issue_count", False])],
            "page_length": 15,
        }),

        # Tab 5: OLAP Demo
        "c_t5_slice": (datasets["olap_trip_cube"], "OLAP Slice - Monthly Pickup Borough Revenue", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough",
            "groupby": [],
            "metrics": ["total_revenue", "total_trips"],
            "sort_series_type": "sum",
            "order_desc": True,
            "adhoc_filters": [
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_month",
                    "operator": "==",
                    "comparator": 1,
                    "clause": "WHERE",
                    "filterOptionName": "olap_slice_month",
                }
            ],
        }),
        "c_t5_dice": (datasets["olap_trip_cube"], "OLAP Dice - Month Borough Vehicle", "table", {
            "query_mode": "aggregate",
            "groupby": ["pickup_month", "pickup_borough", "vehicle_type"],
            "metrics": ["total_trips", "total_revenue", "average_fare"],
            "order_by_cols": [json.dumps(["total_revenue", False])],
            "page_length": 15,
            "adhoc_filters": [
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_month",
                    "operator": "IS NOT NULL",
                    "comparator": None,
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_month",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "pickup_borough",
                    "operator": "IS NOT NULL",
                    "comparator": None,
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_borough",
                },
                {
                    "expressionType": "SIMPLE",
                    "subject": "vehicle_type",
                    "operator": "IS NOT NULL",
                    "comparator": None,
                    "clause": "WHERE",
                    "filterOptionName": "olap_dice_vehicle_type",
                },
            ],
        }),
        "c_t5_drilldown": (datasets["olap_trip_cube"], "OLAP Drill-down - Time Hierarchy", "table", {
            "query_mode": "aggregate",
            "groupby": ["pickup_year", "pickup_month", "pickup_day", "pickup_hour"],
            "metrics": ["total_trips", "total_revenue", "average_trip_distance"],
            "order_by_cols": [json.dumps(["pickup_year", True]), json.dumps(["pickup_month", True]), json.dumps(["pickup_day", True])],
            "page_length": 20,
        }),
        "c_t5_rollup": (datasets["olap_shift_cube"], "OLAP Roll-up - Zone to Borough Utilization", "echarts_timeseries_bar", {
            "x_axis": "shift_start_borough",
            "groupby": [],
            "metrics": ["completed_shifts", "utilization_rate", "revenue_per_hour"],
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t5_pivot": (datasets["olap_trip_cube"], "OLAP Pivot - Borough by Hour Bucket", "pivot_table_v2", {
            "groupbyRows": ["pickup_borough"],
            "groupbyColumns": ["pickup_hour_bucket"],
            "metrics": ["total_trips", "total_revenue"],
            "row_limit": 10000,
        }),
    }

    charts = {}
    for key, (dataset, name, viz_type, params) in charts_spec.items():
        charts[key] = ensure_chart(admin, dataset, name, viz_type, **params)
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
        "Operational monitoring dashboard with OLAP demo views on PostgreSQL ROLAP."
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
            "color_scheme": "bnbColors",
            "refresh_frequency": 0,
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "default_filters": "{}",
            "native_filter_configuration": [],
        }
    )
    dashboard.css = """
.dashboard {
  background: #f4f6f8;
  color: #24313d;
}
.dashboard-header {
  background: #ffffff;
  border-bottom: 1px solid #e3e8ec;
  box-shadow: 0 1px 3px rgba(36, 49, 61, 0.06);
  padding: 12px 18px;
}
.dashboard-header .dashboard-component-header {
  font-weight: 700;
}
.dashboard-content {
  padding: 12px 16px 24px;
}
.dashboard-component-tabs .ant-tabs-nav {
  background: #ffffff;
  border: 1px solid #e3e8ec;
  border-radius: 10px;
  margin: 0 0 14px;
  padding: 0 10px;
}
.dashboard-component-tabs .ant-tabs-tab {
  color: #667785;
  font-weight: 600;
  padding: 12px 16px;
}
.dashboard-component-tabs .ant-tabs-tab-active {
  color: #157a55;
}
.dashboard-component-tabs .ant-tabs-ink-bar {
  background: #157a55;
  height: 3px;
}
.dashboard-component-chart-holder {
  background: #ffffff;
  border: 1px solid #e3e8ec;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(36, 49, 61, 0.05);
  overflow: hidden;
}
.dashboard-component-chart-holder:hover {
  border-color: #b9c9c1;
  box-shadow: 0 4px 12px rgba(36, 49, 61, 0.08);
}
.chart-header {
  border-bottom: 1px solid #eef1f3;
  padding: 10px 12px 8px;
}
.chart-header .header-title {
  color: #24313d;
  font-size: 14px;
  font-weight: 650;
}
.dashboard-component-row {
  margin-bottom: 12px;
}
.slice_container {
  padding: 4px 8px 8px;
}
.big_number_total {
  color: #157a55;
}
.table-condensed > thead > tr > th {
  background: #f7f9fa;
  color: #526270;
  font-weight: 650;
}
.table-condensed > tbody > tr:hover {
  background: #f0f7f4;
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

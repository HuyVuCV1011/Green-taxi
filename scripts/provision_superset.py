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
    # 3 tabs layout structure
    layout: dict[str, object] = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {
            "id": "ROOT_ID",
            "type": "ROOT",
            "children": ["GRID_ID"]
        },
        "GRID_ID": {
            "id": "GRID_ID",
            "type": "GRID",
            "children": ["TABS_ID"],
            "parents": ["ROOT_ID"]
        },
        "TABS_ID": {
            "id": "TABS_ID",
            "type": "TABS",
            "children": ["TAB-1", "TAB-2", "TAB-3"],
            "parents": ["ROOT_ID", "GRID_ID"]
        },
        "TAB-1": {
            "id": "TAB-1",
            "type": "TAB",
            "children": ["TAB1-ROW-1", "TAB1-ROW-2", "TAB1-ROW-3", "TAB1-ROW-4"],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID"],
            "meta": {"text": "1. Tổng quan vận hành"}
        },
        "TAB-2": {
            "id": "TAB-2",
            "type": "TAB",
            "children": ["TAB2-ROW-1", "TAB2-ROW-2", "TAB2-ROW-3"],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID"],
            "meta": {"text": "2. Hiệu suất & Năng suất"}
        },
        "TAB-3": {
            "id": "TAB-3",
            "type": "TAB",
            "children": ["TAB3-ROW-1", "TAB3-ROW-2", "TAB3-ROW-3", "TAB3-ROW-4", "TAB3-ROW-5"],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID"],
            "meta": {"text": "3. Bất thường & Chất lượng"}
        }
    }

    # Tab 1 Rows Setup (9 charts)
    t1_kpis = ["c_t1_kpi_rev", "c_t1_kpi_trips", "c_t1_kpi_drv", "c_t1_kpi_veh"]
    layout["TAB1-ROW-1"] = {
        "id": "TAB1-ROW-1",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t1_kpis if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-1"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    layout["TAB1-ROW-2"] = {
        "id": "TAB1-ROW-2",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id['c_t1_trend'].id}"] if "c_t1_trend" in charts_by_id else [],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-1"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t1_mid = ["c_t1_heatmap", "c_t1_borough"]
    layout["TAB1-ROW-3"] = {
        "id": "TAB1-ROW-3",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t1_mid if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-1"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t1_bot = ["c_t1_top_zones", "c_t1_dest_borough"]
    layout["TAB1-ROW-4"] = {
        "id": "TAB1-ROW-4",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t1_bot if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-1"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    # Tab 2 Rows Setup (7 charts - KPI-Active Vehicles removed)
    t2_kpis = ["c_t2_kpi_completed", "c_t2_kpi_util", "c_t2_kpi_avg_rev"]
    layout["TAB2-ROW-1"] = {
        "id": "TAB2-ROW-1",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t2_kpis if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-2"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t2_mid = ["c_t2_driver_scatter", "c_t2_driver_table"]
    layout["TAB2-ROW-2"] = {
        "id": "TAB2-ROW-2",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t2_mid if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-2"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t2_bot = ["c_t2_vehicle_type_bar", "c_t2_vehicle_table"]
    layout["TAB2-ROW-3"] = {
        "id": "TAB2-ROW-3",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t2_bot if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-2"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    # Tab 3 Rows Setup (10 charts)
    t3_kpis1 = ["c_t3_kpi_anom_trip", "c_t3_kpi_anom_trip_rate", "c_t3_kpi_anom_shf"]
    layout["TAB3-ROW-1"] = {
        "id": "TAB3-ROW-1",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t3_kpis1 if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-3"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t3_kpis2 = ["c_t3_kpi_dq_issues", "c_t3_kpi_dq_quar"]
    layout["TAB3-ROW-2"] = {
        "id": "TAB3-ROW-2",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t3_kpis2 if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-3"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t3_mid = ["c_t3_dq_trend", "c_t3_dq_source"]
    layout["TAB3-ROW-3"] = {
        "id": "TAB3-ROW-3",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t3_mid if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-3"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    layout["TAB3-ROW-4"] = {
        "id": "TAB3-ROW-4",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id['c_t3_dq_rules'].id}"] if "c_t3_dq_rules" in charts_by_id else [],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-3"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    t3_bot = ["c_t3_anom_zones", "c_t3_anom_drivers"]
    layout["TAB3-ROW-5"] = {
        "id": "TAB3-ROW-5",
        "type": "ROW",
        "children": [f"CHART-{charts_by_id[c].id}" for c in t3_bot if c in charts_by_id],
        "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", "TAB-3"],
        "meta": {"background": "BACKGROUND_TRANSPARENT"}
    }

    # Helper to calculate width and define nodes
    for key, chart in charts_by_id.items():
        chart_id = f"CHART-{chart.id}"
        # Determine parent ROW
        parent_row = None
        for row_name, row_def in layout.items():
            if row_name.startswith("TAB") and isinstance(row_def, dict) and chart_id in row_def.get("children", []):
                parent_row = row_name
                break

        # Calculate width
        width = 4
        height = 50
        if key in t1_kpis:
            width = 3
            height = 24
        elif key in t2_kpis:
            width = 4
            height = 24
        elif key in t3_kpis1:
            width = 4
            height = 24
        elif key in t3_kpis2:
            width = 6
            height = 24
        elif key in ["c_t1_trend", "c_t3_dq_rules"]:
            width = 12
            height = 80
        else:
            width = 6
            height = 70

        layout[chart_id] = {
            "id": chart_id,
            "type": "CHART",
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", "TABS_ID", parent_row.split("-")[0].replace("ROW", ""), parent_row],
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

    # Add datasource access for 4 datasets
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
    db.session.flush()

    charts_spec = {
        # Tab 1 Charts (9 charts)
        "c_t1_kpi_rev": (datasets["trip_pickup"], "KPI - Tổng doanh thu", "big_number_total", {"metric": "total_revenue", "y_axis_format": "$,.2f"}),
        "c_t1_kpi_trips": (datasets["trip_pickup"], "KPI - Tổng số chuyến", "big_number_total", {"metric": "total_trips", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_drv": (datasets["trip_pickup"], "KPI - Tài xế hoạt động", "big_number_total", {"metric": "active_driver_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_kpi_veh": (datasets["trip_pickup"], "KPI - Xe hoạt động", "big_number_total", {"metric": "active_vehicle_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t1_trend": (datasets["trip_pickup"], "Xu hướng vận hành theo tháng", "echarts_timeseries_line", {
            "granularity_sqla": "pickup_datetime",
            "time_grain_sqla": "P1M",
            "metrics": ["total_revenue", "total_trips"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
        }),
        "c_t1_borough": (datasets["trip_pickup"], "Nhu cầu theo khu vực Pickup", "echarts_timeseries_bar", {
            "x_axis": "pickup_borough",
            "groupby": [],
            "metrics": ["total_trips"],
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t1_heatmap": (datasets["trip_pickup"], "Heatmap Khung giờ & Thứ", "heatmap_v2", {
            "x_axis": "pickup_hour",
            "groupby": "pickup_day_name",
            "metric": "total_trips",
            "linear_color_scheme": "schemeGreen",
        }),
        "c_t1_top_zones": (datasets["trip_pickup"], "Top 15 Zones Pickup", "echarts_timeseries_bar", {
            "x_axis": "pickup_zone",
            "groupby": [],
            "metrics": ["total_trips"],
            "row_limit": 15,
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t1_dest_borough": (datasets["trip_dropoff"], "Điểm đến theo Borough", "pie", {
            "groupby": ["dropoff_borough"],
            "metric": "total_trips",
            "donut": True,
            "show_labels_threshold": 5,
        }),

        # Tab 2 Charts (7 charts - Active Vehicles KPI removed)
        "c_t2_kpi_completed": (datasets["shift"], "KPI - Số ca hoàn tất", "big_number_total", {"metric": "completed_shifts", "y_axis_format": "SMART_NUMBER"}),
        "c_t2_kpi_util": (datasets["shift"], "KPI - Tỷ lệ sử dụng ca", "big_number_total", {"metric": "utilization_rate", "y_axis_format": ".2%"}),
        "c_t2_kpi_avg_rev": (datasets["shift"], "KPI - Doanh thu trung bình ca", "big_number_total", {"metric": "revenue_per_shift", "y_axis_format": "$,.2f"}),
        "c_t2_driver_scatter": (datasets["shift"], "Phân nhóm hiệu suất Tài xế (Nhóm cần xem xét)", "bubble", {
            "series": "driver_name",
            "entity": "driver_name",
            "x": "utilization_rate",
            "y": "revenue_per_hour",
            "size": "completed_shifts",
            "row_limit": 5000,
        }),
        "c_t2_driver_table": (datasets["shift"], "Hiệu suất tài xế theo ca (Nhóm cần xem xét)", "table", {
            "query_mode": "aggregate",
            "groupby": ["driver_name"],
            "metrics": ["completed_shifts", "revenue_per_hour", "utilization_rate", "idle_minutes"],
            "order_by_cols": [json.dumps(["revenue_per_hour", False])],
            "page_length": 15,
        }),
        "c_t2_vehicle_type_bar": (datasets["shift"], "Hiệu suất theo loại phương tiện", "echarts_timeseries_bar", {
            "x_axis": "vehicle_type",
            "groupby": [],
            "metrics": ["utilization_rate", "trips_per_shift"],
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t2_vehicle_table": (datasets["shift"], "Mức sử dụng phương tiện", "table", {
            "query_mode": "aggregate",
            "groupby": ["vehicle_id", "vehicle_type"],
            "metrics": ["completed_shifts", "trips_per_shift", "revenue_per_shift", "utilization_rate"],
            "order_by_cols": [json.dumps(["utilization_rate", False])],
            "page_length": 15,
        }),

        # Tab 3 Charts (10 charts)
        "c_t3_kpi_anom_trip": (datasets["trip_pickup"], "KPI - Chuyến bất thường", "big_number_total", {"metric": "anomaly_trip_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t3_kpi_anom_trip_rate": (datasets["trip_pickup"], "KPI - Tỷ lệ chuyến bất thường", "big_number_total", {"metric": "anomaly_rate", "y_axis_format": ".2%"}),
        "c_t3_kpi_anom_shf": (datasets["shift"], "KPI - Số ca bất thường", "big_number_total", {"metric": "anomaly_shift_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t3_kpi_dq_issues": (datasets["dq_summary"], "KPI - Tổng số lỗi DQ", "big_number_total", {"metric": "dq_issue_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t3_kpi_dq_quar": (datasets["dq_summary"], "KPI - Số dòng bị cách ly", "big_number_total", {"metric": "quarantine_count", "y_axis_format": "SMART_NUMBER"}),
        "c_t3_dq_trend": (datasets["dq_summary"], "Xu hướng lỗi DQ hàng ngày", "echarts_timeseries_line", {
            "granularity_sqla": "event_date_utc",
            "time_grain_sqla": "P1D",
            "metrics": ["dq_issue_count", "quarantine_count"],
            "x_axis_time_format": "smart_date",
            "y_axis_format": "SMART_NUMBER",
        }),
        "c_t3_dq_source": (datasets["dq_summary"], "Lỗi DQ theo nguồn & Mức độ", "echarts_timeseries_bar", {
            "x_axis": "source_system_code",
            "groupby": ["severity"],
            "metrics": ["dq_issue_count"],
            "bar_stacked": True,
        }),
        "c_t3_dq_rules": (datasets["dq_summary"], "Thống kê lỗi theo Rule DQ", "table", {
            "query_mode": "aggregate",
            "groupby": ["rule_code", "source_entity", "severity"],
            "metrics": ["dq_issue_count", "quarantine_count"],
            "order_by_cols": [json.dumps(["dq_issue_count", False])],
            "page_length": 15,
        }),
        "c_t3_anom_zones": (datasets["trip_pickup"], "Top Zones có Anomaly cao", "echarts_timeseries_bar", {
            "x_axis": "pickup_zone",
            "groupby": [],
            "metrics": ["anomaly_rate"],
            "row_limit": 10,
            "sort_series_type": "sum",
            "order_desc": True,
        }),
        "c_t3_anom_drivers": (datasets["shift"], "Queue tài xế có bất thường ca", "table", {
            "query_mode": "aggregate",
            "groupby": ["driver_name"],
            "metrics": ["anomaly_shift_count"],
            "order_by_cols": [json.dumps(["anomaly_shift_count", False])],
            "page_length": 15,
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
    dashboard.dashboard_title = "NYC Green Taxi - Driver Operations"
    dashboard.description = (
        "Dashboard BQ01-BQ05 organized into 3 operational tabs and provisioned via code."
    )
    dashboard.certified_by = CERTIFIED_BY
    dashboard.certification_details = CERTIFICATION_DETAILS
    dashboard.published = True
    dashboard.owners = [admin]
    dashboard.slices = list(charts.values())
    dashboard.position_json = dashboard_layout(charts)
    dashboard.json_metadata = json.dumps(
        {
            "color_scheme": "supersetColors",
            "refresh_frequency": 0,
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "default_filters": "{}",
            # Superset 6.1.0 sends scalar time ranges to /api/v1/time_range/ in
            # a Rison form rejected by its own backend. Keep the dashboard free
            # of a permanently failing native filter until the image is upgraded.
            "native_filter_configuration": [],
        }
    )
    dashboard.css = """
.dashboard-header { border-bottom: 3px solid #22c55e; }
.dashboard-component-chart-holder { border-radius: 8px; }
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

# -*- coding: utf-8 -*-
"""Streamlit app for Data Pipeline Control Panel.

Provides monitoring and reconciliation views for source databases and warehouse staging.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Import database packages
try:
    import pymysql
except ImportError:
    pymysql = None

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Configure paths and load env
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

# ----------------- CONSTANTS / EXPECTED COUNTS -----------------
# Expected counts for canonical release 'green-taxi-full-v1'
EXPECTED_COUNTS = {
    "green-taxi-full-v1": {
        "mysql_hr": {
            "drivers": 860,
            "driver_changes": 77
        },
        "mongodb_fleet": {
            "vehicles": 860
        },
        "postgres_dispatch": {
            "shifts": 157379,
            "trip_assignments": 2304276,
            "assignment_exceptions": 241
        }
    }
}

STAGING_TABLES = [
    "stg_hr_drivers",
    "stg_hr_driver_changes",
    "stg_fleet_vehicles",
    "stg_dispatch_shifts",
    "stg_dispatch_trip_assignments",
    "stg_tlc_green_trips",
    "stg_lookup_vendor",
    "stg_lookup_taxi_zone"
]

# Set page config
st.set_page_config(
    page_title="Data Pipeline Control Panel",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styles for modern, high-quality aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .card-container {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1E293B;
        margin-bottom: 0.5rem;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 0.25rem;
    }
    .card-body {
        font-size: 0.9rem;
        color: #334155;
    }
    .badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-ok {
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #BCF0DA;
    }
    .badge-warning {
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-error {
        background-color: #FDE8E8;
        color: #9B1C1C;
        border: 1px solid #F8B4B4;
    }
    .badge-gray {
        background-color: #F3F4F6;
        color: #374151;
        border: 1px solid #E5E7EB;
    }
</style>
""", unsafe_allow_html=True)


# Connection Helpers
def get_mysql_config() -> dict[str, any]:
    return {
        "host": os.getenv("MYSQL_HR_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_HR_PORT", "3307")),
        "database": os.getenv("MYSQL_HR_DATABASE", "green_taxi_hr"),
        "user": os.getenv("MYSQL_HR_USER", "green_taxi_hr_app"),
        "password": os.getenv("MYSQL_HR_PASSWORD", "change_me_hr"),
    }


def get_mongo_config() -> dict[str, any]:
    host = os.getenv("MONGODB_FLEET_HOST", "127.0.0.1")
    port = int(os.getenv("MONGODB_FLEET_PORT", "27018"))
    user = os.getenv("MONGODB_FLEET_ROOT_USER", "green_taxi_fleet_admin")
    password = os.getenv("MONGODB_FLEET_ROOT_PASSWORD", "change_me_fleet_root")
    database = os.getenv("MONGODB_FLEET_DATABASE", "green_taxi_fleet")
    
    # Construct mongo uri safely
    uri = f"mongodb://{user}:{password}@{host}:{port}/{database}?authSource=admin"
    return {
        "uri": uri,
        "database": database,
        "host": host,
        "port": port
    }


def get_postgres_dispatch_config() -> dict[str, any]:
    return {
        "host": os.getenv("POSTGRES_DISPATCH_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_DISPATCH_PORT", "5433")),
        "database": os.getenv("POSTGRES_DISPATCH_DATABASE", "green_taxi_dispatch"),
        "user": os.getenv("POSTGRES_DISPATCH_USER", "green_taxi_dispatch_app"),
        "password": os.getenv("POSTGRES_DISPATCH_PASSWORD", "change_me_dispatch"),
    }


def get_postgres_warehouse_config() -> dict[str, any]:
    return {
        "host": os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
        "database": os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
        "user": os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
        "password": os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse"),
    }


def test_mysql_conn() -> tuple[bool, str, any]:
    if pymysql is None:
        return False, "Thư viện `pymysql` chưa được cài đặt", None
    config = get_mysql_config()
    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            connect_timeout=3
        )
        return True, "Kết nối thành công", conn
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}", None


def test_mongo_conn() -> tuple[bool, str, any]:
    if MongoClient is None:
        return False, "Thư viện `pymongo` chưa được cài đặt", None
    config = get_mongo_config()
    try:
        client = MongoClient(config["uri"], serverSelectionTimeoutMS=2000)
        # Force a call to check connection
        client.admin.command('ping')
        return True, "Kết nối thành công", client
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}", None


def test_postgres_dispatch_conn() -> tuple[bool, str, any]:
    if psycopg2 is None:
        return False, "Thư viện `psycopg2` chưa được cài đặt", None
    config = get_postgres_dispatch_config()
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=3
        )
        return True, "Kết nối thành công", conn
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}", None


def test_postgres_warehouse_conn() -> tuple[bool, str, any]:
    if psycopg2 is None:
        return False, "Thư viện `psycopg2` chưa được cài đặt", None
    config = get_postgres_warehouse_config()
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=3
        )
        return True, "Kết nối thành công", conn
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}", None


def safe_query_count(conn: any, db_type: str, target: str) -> tuple[int, str]:
    """Get row/document count safely without crashing."""
    if conn is None:
        return -1, "Chưa kết nối database"
    
    if db_type == "mysql":
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {target}")
                row = cursor.fetchone()
                return row[0] if row else 0, "OK"
        except Exception as e:
            return -1, f"Lỗi: {str(e)}"
            
    elif db_type == "mongodb":
        try:
            config = get_mongo_config()
            db = conn[config["database"]]
            count = db[target].count_documents({})
            return count, "OK"
        except Exception as e:
            return -1, f"Lỗi: {str(e)}"
            
    elif db_type == "postgres":
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {target}")
                row = cursor.fetchone()
                return row[0] if row else 0, "OK"
        except Exception as e:
            # Check if it's an UndefinedTable (error code 42P01)
            conn.rollback() # Reset transaction after error
            if hasattr(e, 'pgcode') and e.pgcode == '42P01':
                return -1, "Bảng chưa được khởi tạo (Table Not Found)"
            return -1, f"Lỗi: {str(e)}"
            
    return -1, "Loại database không hỗ trợ"


# App Title & Layout
st.markdown('<div class="main-header">⚙️ Data Pipeline Control Panel</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Bảng giám sát trạng thái hệ thống dữ liệu nguồn (Sources) và kho dữ liệu Staging (Warehouse)</div>', unsafe_allow_html=True)

# Sidebar configurations
st.sidebar.header("Cấu hình Kết nối & Tham số")
release_id = st.sidebar.text_input("Current Release ID", value="green-taxi-full-v1")
st.sidebar.markdown("---")

# Display connection configs in Sidebar (Read-only representation)
st.sidebar.subheader("Cơ sở dữ liệu nguồn")
st.sidebar.code(f"MySQL HR:\n{get_mysql_config()['host']}:{get_mysql_config()['port']} ({get_mysql_config()['database']})", language="text")
st.sidebar.code(f"MongoDB Fleet:\n{get_mongo_config()['host']}:{get_mongo_config()['port']} ({get_mongo_config()['database']})", language="text")
st.sidebar.code(f"PostgreSQL Dispatch:\n{get_postgres_dispatch_config()['host']}:{get_postgres_dispatch_config()['port']} ({get_postgres_dispatch_config()['database']})", language="text")
st.sidebar.markdown("---")
st.sidebar.subheader("Kho dữ liệu Warehouse")
st.sidebar.code(f"PostgreSQL DWH:\n{get_postgres_warehouse_config()['host']}:{get_postgres_warehouse_config()['port']} ({get_postgres_warehouse_config()['database']})", language="text")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# Establish connections
mysql_ok, mysql_msg, mysql_conn = test_mysql_conn()
mongo_ok, mongo_msg, mongo_client = test_mongo_conn()
dispatch_ok, dispatch_msg, dispatch_conn = test_postgres_dispatch_conn()
warehouse_ok, warehouse_msg, warehouse_conn = test_postgres_warehouse_conn()

# Define tabs
tab_flow, tab_sources, tab_seed, tab_warehouse, tab_commands = st.tabs([
    "📈 Tổng quan & Luồng Dữ liệu",
    "🔌 Trạng thái Nguồn (Sources)",
    "📊 Seed Reconciliation",
    "🏢 Warehouse Staging",
    "💻 Hướng dẫn Lệnh Chạy (Commands)"
])

# ==================== TAB 1: OVERVIEW & DATA FLOW ====================
with tab_flow:
    st.subheader("Tổng quan dự án")
    st.markdown(f"""
    * **Tên dự án:** NYC Green Taxi Driver Operations BI
    * **Mô tả:** Hệ thống tích hợp dữ liệu vận hành từ 4 nguồn hệ thống mô phỏng để xây dựng kho dữ liệu phân tích, phục vụ quản trị hiệu quả hoạt động của tài xế và đội xe.
    * **Phiên bản dữ liệu phân phối (Release ID):** `{release_id}`
    """)
    
    st.markdown("""
    > [!NOTE]
    > **Mục tiêu của Giao diện:** Giao diện này phục vụ mục đích **giám sát kỹ thuật** trạng thái của các tiến trình trích xuất và nạp dữ liệu (ETL/ELT Monitoring). Đây không phải là dashboard phân tích BI dành cho người dùng cuối.
    """)
    
    st.subheader("Sơ đồ luồng dữ liệu nghiệp vụ (Business Data Flow)")
    
    # Render Mermaid chart using components.html
    mermaid_code = """
    graph TD
        %% Source systems
        subgraph Sources ["Simulated Business Sources"]
            HR[("MySQL HR DB<br>(drivers, driver_changes)")]
            Fleet[("MongoDB Fleet DB<br>(vehicles)")]
            Dispatch[("PostgreSQL Dispatch DB<br>(shifts, trip_assignments)")]
            TLC[("TLC & Lookup Files<br>(green_tripdata, zone, vendor)")]
        end

        %% Warehouse Staging
        subgraph DWH ["PostgreSQL Warehouse (Target)"]
            subgraph Staging ["Staging Schema (Extract & Load)"]
                stg_hr_drivers["stg_hr_drivers"]
                stg_hr_changes["stg_hr_driver_changes"]
                stg_fleet["stg_fleet_vehicles"]
                stg_shifts["stg_dispatch_shifts"]
                stg_assigns["stg_dispatch_trip_assignments"]
                stg_trips["stg_tlc_green_trips"]
                stg_vendor["stg_lookup_vendor"]
                stg_zone["stg_lookup_taxi_zone"]
            end

            subgraph Pipelines ["Future Orchestration Layers (Planned)"]
                DQ["DQ / Audit / Quarantine"]
                NDS["Normalized Data Store (NDS)"]
                DDS["Dimensional Data Store (DDS)"]
            end
        end

        %% Flow mapping
        HR -->|load_staging.py| stg_hr_drivers
        HR -->|load_staging.py| stg_hr_changes
        Fleet -->|load_staging.py| stg_fleet
        Dispatch -->|load_staging.py| stg_shifts
        Dispatch -->|load_staging.py| stg_assigns
        TLC -->|load_staging.py| stg_trips
        TLC -->|load_staging.py| stg_vendor
        TLC -->|load_staging.py| stg_zone

        Staging --> DQ
        DQ --> NDS
        NDS --> DDS

        %% Style
        classDef source fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
        classDef staging fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
        classDef planned stroke:#f57c00,stroke-width:2px,stroke-dasharray: 5 5,fill:#fff3e0,color:#e65100;
        class HR,Fleet,Dispatch,TLC source;
        class stg_hr_drivers,stg_hr_changes,stg_fleet,stg_shifts,stg_assigns,stg_trips,stg_vendor,stg_zone staging;
        class DQ,NDS,DDS planned;
    """
    
    html_code = f"""
    <div class="mermaid" style="display: flex; justify-content: center; background-color: white; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0;">
    {mermaid_code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
    """
    # Fallback text-based diagram in case Mermaid CDN fails to load offline
    st.markdown("""
    *(Mẹo: Nếu sơ đồ đồ họa không hiển thị khi offline, hãy xem sơ đồ dạng văn bản bên dưới)*
    """)
    
    components.html(html_code, height=620)
    
    with st.expander("📄 Xem sơ đồ luồng dữ liệu (Dạng Văn Bản/ASCII Fallback)"):
        st.code("""
[Hệ thống nguồn Giả lập / Nguồn Thô]
├── 1. MySQL HR (drivers, driver_changes) ─────────> staging.stg_hr_drivers & stg_hr_driver_changes
├── 2. MongoDB Fleet (vehicles) ──────────────────> staging.stg_fleet_vehicles
├── 3. PostgreSQL Dispatch (shifts, assignments) ──> staging.stg_dispatch_shifts & stg_dispatch_trip_assignments
└── 4. TLC & Lookup Files (Trips, Zones, Vendors) ─> staging.stg_tlc_green_trips & stg_lookup_*

[Tầng xử lý tiếp theo trong Kho Dữ Liệu PostgreSQL Warehouse - Planned]
staging.stg_*  ───>  DQ / Audit / Quarantine  ───>  NDS (Chuẩn 3NF)  ───>  DDS (Star Schema)
        """, language="text")
        
    st.markdown("""
    💡 **Ghi chú thiết kế:** Gói dữ liệu từ Google Drive (`green-taxi-full-v1.zip`) chỉ đóng vai trò phân phối để thiết lập môi trường (setup/reproducibility package), không phải là một nguồn dữ liệu nghiệp vụ (business source system) hoạt động trực tiếp trong luồng runtime.
    """)

# ==================== TAB 2: SOURCE SYSTEMS STATUS ====================
with tab_sources:
    st.subheader("Sức khỏe kết nối các Database nguồn & Target")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # 1. MySQL HR Card
    with col1:
        status_badge = '<span class="badge badge-ok">Connected</span>' if mysql_ok else '<span class="badge badge-error">Disconnected</span>'
        mysql_conf = get_mysql_config()
        st.markdown(f"""
        <div class="card-container">
            <div class="card-title">MySQL HR</div>
            <div class="card-body">
                Trạng thái: {status_badge}<br>
                <b>Host:</b> {mysql_conf['host']}:{mysql_conf['port']}<br>
                <b>DB:</b> {mysql_conf['database']}<br>
                <b>Mô tả:</b> Lưu trữ Driver HR
            </div>
        </div>
        """, unsafe_allow_html=True)
        if mysql_ok:
            c_drivers, _ = safe_query_count(mysql_conn, "mysql", "drivers")
            c_changes, _ = safe_query_count(mysql_conn, "mysql", "driver_changes")
            st.metric("Drivers Rows", f"{c_drivers:,}" if c_drivers >= 0 else "N/A")
            st.metric("Changes Rows", f"{c_changes:,}" if c_changes >= 0 else "N/A")
        else:
            st.warning(f"Chi tiết lỗi: {mysql_msg}")
            
    # 2. MongoDB Fleet Card
    with col2:
        status_badge = '<span class="badge badge-ok">Connected</span>' if mongo_ok else '<span class="badge badge-error">Disconnected</span>'
        mongo_conf = get_mongo_config()
        st.markdown(f"""
        <div class="card-container">
            <div class="card-title">MongoDB Fleet</div>
            <div class="card-body">
                Trạng thái: {status_badge}<br>
                <b>Host:</b> {mongo_conf['host']}:{mongo_conf['port']}<br>
                <b>DB:</b> {mongo_conf['database']}<br>
                <b>Mô tả:</b> Quản lý Fleet & Vehicles
            </div>
        </div>
        """, unsafe_allow_html=True)
        if mongo_ok:
            c_vehicles, _ = safe_query_count(mongo_client, "mongodb", "vehicles")
            st.metric("Vehicles Documents", f"{c_vehicles:,}" if c_vehicles >= 0 else "N/A")
        else:
            st.warning(f"Chi tiết lỗi: {mongo_msg}")

    # 3. PostgreSQL Dispatch Card
    with col3:
        status_badge = '<span class="badge badge-ok">Connected</span>' if dispatch_ok else '<span class="badge badge-error">Disconnected</span>'
        dispatch_conf = get_postgres_dispatch_config()
        st.markdown(f"""
        <div class="card-container">
            <div class="card-title">Postgres Dispatch</div>
            <div class="card-body">
                Trạng thái: {status_badge}<br>
                <b>Host:</b> {dispatch_conf['host']}:{dispatch_conf['port']}<br>
                <b>DB:</b> {dispatch_conf['database']}<br>
                <b>Mô tả:</b> Ca trực & Phân bổ
            </div>
        </div>
        """, unsafe_allow_html=True)
        if dispatch_ok:
            c_shifts, _ = safe_query_count(dispatch_conn, "postgres", "shifts")
            c_assign, _ = safe_query_count(dispatch_conn, "postgres", "trip_assignments")
            c_exceptions, _ = safe_query_count(dispatch_conn, "postgres", "assignment_exceptions")
            st.metric("Shifts Rows", f"{c_shifts:,}" if c_shifts >= 0 else "N/A")
            st.metric("Assignments Rows", f"{c_assign:,}" if c_assign >= 0 else "N/A")
            st.metric("Exceptions Rows", f"{c_exceptions:,}" if c_exceptions >= 0 else "N/A")
        else:
            st.warning(f"Chi tiết lỗi: {dispatch_msg}")
            
    # 4. PostgreSQL Warehouse Card
    with col4:
        status_badge = '<span class="badge badge-ok">Connected</span>' if warehouse_ok else '<span class="badge badge-error">Disconnected</span>'
        warehouse_conf = get_postgres_warehouse_config()
        st.markdown(f"""
        <div class="card-container">
            <div class="card-title">Postgres Warehouse</div>
            <div class="card-body">
                Trạng thái: {status_badge}<br>
                <b>Host:</b> {warehouse_conf['host']}:{warehouse_conf['port']}<br>
                <b>DB:</b> {warehouse_conf['database']}<br>
                <b>Mô tả:</b> Kho dữ liệu Target
            </div>
        </div>
        """, unsafe_allow_html=True)
        if warehouse_ok:
            # Check staging tables count as high level indicator
            cstg, _ = safe_query_count(warehouse_conn, "postgres", "staging.stg_hr_drivers")
            st.metric("Stg Drivers Rows", f"{cstg:,}" if cstg >= 0 else "Not Loaded")
        else:
            st.warning(f"Chi tiết lỗi: {warehouse_msg}")

# ==================== TAB 3: SEED RECONCILIATION ====================
with tab_seed:
    st.subheader("Đối soát Dữ liệu Nguồn sau Seeding (Seed Reconciliation)")
    st.markdown("""
    Bảng dưới đây so sánh số lượng dòng thực tế trích xuất được từ các cơ sở dữ liệu nguồn 
    so với số lượng dòng thiết kế chuẩn của Release package.
    """)
    
    # Get expected counts for the current release id safely
    expected_for_release = EXPECTED_COUNTS.get(release_id, {})
    if not expected_for_release:
        st.warning(f"⚠️ Không tìm thấy định nghĩa expected counts cho Release ID '{release_id}'. Sử dụng mặc định của 'green-taxi-full-v1'.")
        expected_for_release = EXPECTED_COUNTS["green-taxi-full-v1"]
        
    expected_data = [
        {"system": "MySQL HR", "entity": "drivers", "expected": expected_for_release["mysql_hr"]["drivers"], "type": "mysql", "conn": mysql_conn},
        {"system": "MySQL HR", "entity": "driver_changes", "expected": expected_for_release["mysql_hr"]["driver_changes"], "type": "mysql", "conn": mysql_conn},
        {"system": "MongoDB Fleet", "entity": "vehicles", "expected": expected_for_release["mongodb_fleet"]["vehicles"], "type": "mongodb", "conn": mongo_client},
        {"system": "PostgreSQL Dispatch", "entity": "shifts", "expected": expected_for_release["postgres_dispatch"]["shifts"], "type": "postgres", "conn": dispatch_conn},
        {"system": "PostgreSQL Dispatch", "entity": "trip_assignments", "expected": expected_for_release["postgres_dispatch"]["trip_assignments"], "type": "postgres", "conn": dispatch_conn},
        {"system": "PostgreSQL Dispatch", "entity": "assignment_exceptions", "expected": expected_for_release["postgres_dispatch"]["assignment_exceptions"], "type": "postgres", "conn": dispatch_conn},
    ]
    
    recon_rows = []
    for item in expected_data:
        actual_count, err_msg = safe_query_count(item["conn"], item["type"], item["entity"])
        
        if actual_count == -1:
            status = "⚠️ Not Loaded"
            diff = "-"
            actual_str = "N/A"
        elif actual_count == item["expected"]:
            status = "✅ OK"
            diff = 0
            actual_str = f"{actual_count:,}"
        else:
            status = "❌ Mismatch"
            diff = actual_count - item["expected"]
            actual_str = f"{actual_count:,}"
            
        recon_rows.append({
            "Hệ thống nguồn": item["system"],
            "Thực thể": item["entity"],
            "Số dòng dự kiến (Expected)": f"{item['expected']:,}",
            "Số dòng thực tế (Actual)": actual_str,
            "Chênh lệch": diff if isinstance(diff, str) else f"{diff:+,}" if diff != 0 else "0",
            "Trạng thái": status
        })
        
    df_recon = pd.DataFrame(recon_rows)
    st.dataframe(df_recon, use_container_width=True, hide_index=True)
    
    st.markdown("""
    💡 **Quy tắc đối soát:**
    - Nếu **Actual = Expected**: Trạng thái **OK** (Hệ thống đã nạp đầy đủ và chính xác dữ liệu nguồn).
    - Nếu **Actual != Expected**: Trạng thái **Mismatch** (Có lỗi xảy ra hoặc tệp tin nguồn local bị hỏng/lệch phiên bản).
    - Nếu **Actual = N/A**: Trạng thái **Not Loaded** (Database hoặc bảng chưa được cấu hình, chưa seed, hoặc container chưa chạy).
    """)

# ==================== TAB 4: WAREHOUSE STAGING STATUS ====================
with tab_warehouse:
    st.subheader("Trạng thái và Siêu dữ liệu tại PostgreSQL Warehouse")
    
    if not warehouse_ok:
        st.error(f"⚠️ Không thể truy cập PostgreSQL Warehouse. Chi tiết lỗi: {warehouse_msg}")
        st.info("Vui lòng khởi động container `postgres_warehouse` và áp dụng DDL khởi tạo (apply_warehouse_ddl.py) trước khi theo dõi.")
    else:
        try:
            # Row count per staging table
            stg_rows = []
            for tbl in STAGING_TABLES:
                full_tbl_name = f"staging.{tbl}"
                count, status_msg = safe_query_count(warehouse_conn, "postgres", full_tbl_name)
                
                if count == -1:
                    status = "❌ Not Loaded / Missing"
                    count_str = "N/A"
                else:
                    status = "✅ Loaded" if count > 0 else "⚠️ Empty"
                    count_str = f"{count:,}"
                    
                stg_rows.append({
                    "Bảng Staging": full_tbl_name,
                    "Số dòng hiện tại": count_str,
                    "Trạng thái": status,
                    "Ghi chú chi tiết": status_msg if count == -1 else "Sẵn sàng"
                })
                
            df_stg = pd.DataFrame(stg_rows)
            
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.subheader("1. Thống kê bảng Staging (staging schema)")
                st.dataframe(df_stg, use_container_width=True, hide_index=True)
                st.caption("*Lưu ý: assignment_exceptions không được load vào Staging do không thuộc DDS Fact nghiệp vụ.*")
                
            with col_r:
                st.subheader("2. Dữ liệu Lịch sử Batch ETL (audit.metadata_etl_batch)")
                with warehouse_conn.cursor() as cur:
                    try:
                        cur.execute("""
                            SELECT table_name 
                            FROM information_schema.tables 
                            WHERE table_schema = 'audit' AND table_name = 'metadata_etl_batch'
                        """)
                        audit_exists = cur.fetchone()
                        
                        if audit_exists:
                            cur.execute("""
                                SELECT 
                                    batch_id, 
                                    batch_status, 
                                    batch_started_at, 
                                    batch_completed_at, 
                                    row_count_loaded, 
                                    source_system
                                FROM audit.metadata_etl_batch
                                ORDER BY batch_started_at DESC
                                LIMIT 5
                            """)
                            batches = cur.fetchall()
                            if batches:
                                df_batches = pd.DataFrame(batches, columns=[
                                    "Batch ID", "Status", "Bắt đầu", "Kết thúc", "Loaded Rows", "Source System"
                                ])
                                st.dataframe(df_batches, use_container_width=True, hide_index=True)
                            else:
                                st.info("Chưa có lượt chạy ETL nào được ghi nhận trong bảng audit.")
                        else:
                            st.warning("⚠️ Bảng `audit.metadata_etl_batch` chưa tồn tại. Hãy chạy apply_warehouse_ddl.py.")
                    except Exception as ex:
                        warehouse_conn.rollback()
                        st.error(f"Lỗi truy vấn metadata_etl_batch: {str(ex)}")

            st.markdown("---")
            st.subheader("3. Chi tiết trích xuất của Batch gần nhất (audit.metadata_source_extract)")
            with warehouse_conn.cursor() as cur:
                try:
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'audit' AND table_name = 'metadata_source_extract'
                    """)
                    extract_exists = cur.fetchone()
                    
                    if extract_exists:
                        cur.execute("""
                            SELECT 
                                source_system, 
                                source_entity, 
                                rows_extracted, 
                                rows_loaded, 
                                extract_status, 
                                source_extract_at
                            FROM audit.metadata_source_extract
                            WHERE batch_id = (
                                SELECT batch_id 
                                FROM audit.metadata_etl_batch 
                                ORDER BY batch_started_at DESC 
                                LIMIT 1
                            )
                            ORDER BY source_system, source_entity
                        """)
                        extracts = cur.fetchall()
                        if extracts:
                            df_extracts = pd.DataFrame(extracts, columns=[
                                "Source System", "Source Entity", "Rows Extracted", "Rows Loaded", "Status", "Extract At"
                            ])
                            st.dataframe(df_extracts, use_container_width=True, hide_index=True)
                        else:
                            st.info("Chưa có dữ liệu trích xuất chi tiết được ghi nhận cho batch gần nhất.")
                    else:
                        st.warning("⚠️ Bảng `audit.metadata_source_extract` chưa tồn tại.")
                except Exception as ex:
                    warehouse_conn.rollback()
                    st.error(f"Lỗi truy vấn metadata_source_extract: {str(ex)}")
                    
            st.markdown("---")
            st.subheader("📅 Kế hoạch triển khai tầng tiếp theo (Planned Layers)")
            st.markdown("""
            * **Tầng DQ / Audit / Quarantine:** Phát hiện, phân loại và cô lập các dòng dữ liệu không hợp chuẩn (lỗi schema drift, trùng khóa, dữ liệu mâu thuẫn thời gian nghiệp vụ) mà không làm ngắt quãng pipeline.
            * **Normalized Data Store (NDS):** Xây dựng mô hình dữ liệu quan hệ chuẩn hóa 3NF để lưu trữ dữ liệu tập trung toàn vẹn.
            * **Dimensional Data Store (DDS):** Thiết kế Fact và Dimension tables (Mô hình hình sao - Star Schema) tối ưu hóa truy vấn phân tích.
            """)
        except Exception as e:
            st.error(f"Lỗi khi đọc trạng thái Warehouse: {str(e)}")

# ==================== TAB 5: COMMAND GUIDE ====================
with tab_commands:
    st.subheader("Cẩm nang vận hành Pipeline bằng PowerShell")
    st.markdown("""
    Dưới đây là các câu lệnh chuẩn phục vụ quá trình cài đặt, seeding và chạy ETL nạp Staging trên môi trường local.
    Hãy sao chép các lệnh này để chạy trong cửa sổ terminal của bạn.
    """)
    
    st.markdown("### 1. Chuẩn bị môi trường & Docker Containers")
    st.code("""# Cài đặt các thư viện cần thiết
python -m pip install -r requirements.txt

# Tạo tệp môi trường local .env từ tệp cấu hình mẫu
Copy-Item configs\\.env.example .env

# Khởi chạy toàn bộ 4 cơ sở dữ liệu trên Docker
docker compose up -d

# Kiểm tra trạng thái các container đang chạy
docker compose ps""", language="powershell")

    st.markdown("### 2. Nạp dữ liệu giả lập (Source Databases Seeding)")
    st.code("""# Nạp Driver HR giả lập vào MySQL HR
python scripts/seed_mysql_hr.py --release-id green-taxi-full-v1

# Nạp Fleet & Vehicles giả lập vào MongoDB Fleet
python scripts/seed_mongodb_fleet.py --release-id green-taxi-full-v1

# Nạp Ca trực & Assignments giả lập vào PostgreSQL Dispatch
python scripts/seed_postgres_dispatch.py --release-id green-taxi-full-v1""", language="powershell")

    st.markdown("### 3. Cấu trúc và Nạp dữ liệu vào Staging Warehouse")
    st.code("""# Áp dụng DDL baseline (audit, dq, staging schemas) vào Warehouse
python scripts/apply_warehouse_ddl.py --mode docker

# Nạp toàn bộ dữ liệu từ Sources vào Staging Warehouse (Reconciliation ETL)
python scripts/load_staging.py --release-id green-taxi-full-v1 --source all""", language="powershell")

    st.markdown("### 4. Khởi chạy Giao diện điều khiển (Streamlit App)")
    st.code("""# Khởi chạy Control Panel này
streamlit run app/streamlit_app.py""", language="powershell")

    st.markdown("""
    > [!TIP]
    > **Cách test loader Staging nhanh với dữ liệu mẫu (Sample):**
    > Để chạy ETL trích xuất nhanh một lượng nhỏ dữ liệu mà không cần chờ nạp hết 2.3 triệu dòng trip assignments, bạn có thể truyền thêm tham số giới hạn files/rows:
    > `python scripts/load_staging.py --release-id green-taxi-full-v1 --source tlc --limit-files 1 --limit-rows 10000`
    """)

# Close connections to avoid memory/connection leakages
for conn_obj in (mysql_conn, dispatch_conn, warehouse_conn):
    if conn_obj:
        try:
            conn_obj.close()
        except:
            pass
if mongo_client:
    try:
        mongo_client.close()
    except:
        pass

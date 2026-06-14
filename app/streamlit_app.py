# -*- coding: utf-8 -*-
"""Streamlit app for Data Pipeline Control Panel.

Provides monitoring, data exploration, validation, and orchestration controls.
"""

from __future__ import annotations

import os
import sys
import base64
from pathlib import Path
from datetime import datetime
from typing import Any
import pandas as pd
import streamlit as st

# Configure paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.monitoring.repository import (
    MonitoringRepository,
    PipelineLock,
    is_dds_ready,
    sanitize_for_display,
    sanitize_message,
)
from src.orchestration.pipeline_runner import PipelineRunner

# Page Configuration
st.set_page_config(
    page_title="Data Pipeline Control Panel",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
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
    .badge {
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
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
    .db-status-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Repository & Lock
repo = MonitoringRepository(repo_root=REPO_ROOT)
lock = PipelineLock(REPO_ROOT / "data" / ".pipeline.lock")

# Initialize Session State for storing last pipeline execution result
if "last_run_result" not in st.session_state:
    st.session_state.last_run_result = None

# Cache function for DB connections check
@st.cache_data(ttl=30)
def get_cached_db_health(release_id: str) -> dict[str, dict[str, Any]]:
    return repo.test_connections()

# Sidebar
st.sidebar.header("Cấu hình & Phiên bản")
release_id = st.sidebar.text_input("Release ID", value="green-taxi-full-v1")

# Show database status indicators in sidebar
st.sidebar.subheader("Trạng thái Kết nối")
db_health = get_cached_db_health(release_id)
for name, info in db_health.items():
    status_icon = "🟢" if info["connected"] else "🔴"
    st.sidebar.markdown(f"**{status_icon} {name.upper().replace('_', ' ')}**")
    st.sidebar.caption(f"{info['host']}:{info['port']}")

if st.sidebar.button("🔄 Làm mới trạng thái", width="stretch"):
    get_cached_db_health.clear()
    st.rerun()

# Check Lock Status
is_running = lock.is_locked()

# Headers
st.markdown('<div class="main-header">⚙️ Data Pipeline Control Panel</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Hệ thống Giám sát & Điều khiển luồng tích hợp dữ liệu NYC Green Taxi</div>', unsafe_allow_html=True)

# Tabs
tab_overview, tab_explorer, tab_control, tab_progress, tab_warehouse, tab_dq, tab_demo = st.tabs([
    "📈 Tổng quan",
    "🔌 Khám phá Nguồn",
    "⚙️ Điều khiển Step",
    "📊 Tiến độ Chạy",
    "🏢 Trạng thái Kho",
    "🛡️ DQ & Quarantine",
    "🚀 Auto-Demo"
])

# ==============================================================================
# TAB 1: OVERVIEW & ARCHITECTURE
# ==============================================================================
with tab_overview:
    st.subheader("1. Tổng quan Luồng Dữ liệu")

    # Sơ đồ Source -> Staging -> NDS -> DDS
    mermaid_code = """
    graph TD
        subgraph Sources ["Simulated Sources"]
            HR[("MySQL HR DB<br>(drivers, driver_changes)")]
            Fleet[("MongoDB Fleet DB<br>(vehicles)")]
            Dispatch[("PostgreSQL Dispatch DB<br>(shifts, trip_assignments)")]
            TLC[("TLC & Lookup Files<br>(trips, zones, vendors)")]
        end

        subgraph DWH ["PostgreSQL Warehouse"]
            Staging["Staging Schema<br>(staging.stg_*)"]
            NDS["NDS Schema (3NF)<br>(nds.nds_*)"]
            DDS["DDS Schema (Star)<br>(dds.dim_*, dds.fact_*)"]
        end

        HR -->|load_staging| Staging
        Fleet -->|load_staging| Staging
        Dispatch -->|load_staging| Staging
        TLC -->|load_staging| Staging

        Staging -->|load_nds & DQ Gate 1| NDS
        NDS -->|load_dds & DQ Gate 2| DDS

        classDef src fill:#eff6ff,stroke:#1d4ed8,stroke-width:2px;
        classDef dwh fill:#f0fdf4,stroke:#15803d,stroke-width:2px;
        class HR,Fleet,Dispatch,TLC src;
        class Staging,NDS,DDS dwh;
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
    mermaid_src = base64.b64encode(html_code.encode("utf-8")).decode("ascii")
    st.iframe(f"data:text/html;base64,{mermaid_src}", height=380)

    st.markdown("*(Mẹo: Nếu sơ đồ không hiển thị khi offline, hãy xem sơ đồ text trong tài liệu)*")

    st.subheader("2. Chi tiết Kết nối Cơ sở dữ liệu")
    col1, col2, col3, col4 = st.columns(4)

    connections = [
        ("MySQL HR", db_health.get("mysql_hr", {})),
        ("MongoDB Fleet", db_health.get("mongodb_fleet", {})),
        ("Postgres Dispatch", db_health.get("postgres_dispatch", {})),
        ("Postgres Warehouse", db_health.get("postgres_warehouse", {}))
    ]

    for idx, (title, info) in enumerate(connections):
        col = (col1, col2, col3, col4)[idx]
        with col:
            connected = info.get("connected", False)
            badge_class = "badge-ok" if connected else "badge-error"
            badge_text = "Connected" if connected else "Disconnected"

            st.markdown(f"""
            <div class="db-status-card">
                <h4>{title}</h4>
                <p><span class="badge {badge_class}">{badge_text}</span></p>
                <p><b>Host:</b> {info.get('host', 'N/A')}:{info.get('port', 'N/A')}</p>
                <p><b>DB Name:</b> {info.get('database', 'N/A')}</p>
            </div>
            """, unsafe_allow_html=True)
            if not connected and info.get("error"):
                st.caption(f"Lỗi: {sanitize_message(info['error'])}")

    st.caption(f"Thời điểm kiểm tra gần nhất: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==============================================================================
# TAB 2: SOURCE EXPLORER
# ==============================================================================
with tab_explorer:
    st.subheader("Truy cập dữ liệu mẫu từ Nguồn (Source Explorer)")

    col_sys, col_ent, col_lim = st.columns([1, 1, 1])
    with col_sys:
        selected_system = st.selectbox(
            "Hệ thống Nguồn",
            options=["mysql_hr", "mongodb_fleet", "postgres_dispatch"],
            format_func=lambda x: x.upper().replace("_", " ")
        )
    with col_ent:
        entities_map = {
            "mysql_hr": ["drivers", "driver_changes"],
            "mongodb_fleet": ["vehicles"],
            "postgres_dispatch": ["shifts", "trip_assignments"]
        }
        selected_entity = st.selectbox(
            "Thực thể (Bảng/Collection)",
            options=entities_map[selected_system]
        )
    with col_lim:
        selected_limit = st.slider("Giới hạn số dòng", min_value=1, max_value=100, value=10)

    if st.button("🔍 Đọc dữ liệu", width="stretch"):
        try:
            # Check connection first
            if not db_health.get(selected_system, {}).get("connected", False):
                st.warning(f"Database {selected_system} chưa được kết nối.")
            else:
                sample_data = repo.get_source_sample(selected_system, selected_entity, selected_limit)
                if sample_data:
                    df = pd.DataFrame(sample_data)
                    st.dataframe(df, width="stretch")
                else:
                    st.info("Bảng hoặc Collection rỗng.")
        except Exception as e:
            st.error(f"Lỗi không mong muốn: {sanitize_message(e)}")

# ==============================================================================
# TAB 3: PIPELINE CONTROL
# ==============================================================================
with tab_control:
    st.subheader("Điều khiển Chạy Pipeline theo Bước")

    if is_running:
        st.warning("⚠️ Đang có tiến trình pipeline đang chạy. Vui lòng chờ cho đến khi tiến trình hoàn tất.")

    runner = PipelineRunner(release_id=release_id, data_root=REPO_ROOT / "data")

    col_step, col_opts = st.columns([2, 1])
    with col_step:
        # Steps selection
        options_step = ["Tất cả các bước (All Steps)"] + runner.steps
        selected_run_step = st.selectbox("Chọn bước muốn chạy", options_step)

        # Confirmation box for data-writing steps
        data_writing_steps = {"load_staging", "load_nds", "load_dds"}
        is_writing_step = selected_run_step == "Tất cả các bước (All Steps)" or selected_run_step in data_writing_steps

        confirmed = True
        if is_writing_step:
            st.warning("⚠️ Bước này có tác động thay đổi hoặc ghi đè dữ liệu kho.")
            confirmed = st.checkbox("Tôi xác nhận muốn thực thi thao tác ghi dữ liệu này")

    with col_opts:
        dry_run = st.checkbox("Dry Run (Chỉ mô phỏng kết quả)", value=False)
        fail_fast = st.checkbox("Fail Fast (Dừng ngay khi có lỗi)", value=True)

    # Convert select option to parameter
    step_param = None if selected_run_step == "Tất cả các bước (All Steps)" else selected_run_step

    btn_disabled = is_running or (is_writing_step and not confirmed)

    if st.button("🚀 Thực thi Step", disabled=btn_disabled, width="stretch"):
        # Double check lock to avoid race conditions
        if not lock.acquire():
            st.error("Không thể khóa pipeline. Có thể một session khác đã khởi chạy trước.")
        else:
            try:
                st.info("Đang chạy pipeline. Vui lòng không đóng trình duyệt hoặc tải lại trang...")
                run_result = runner.run(
                    step=step_param,
                    dry_run=dry_run,
                    fail_fast=fail_fast
                )
                st.session_state.last_run_result = run_result
                if dry_run:
                    st.info("Dry run hoàn tất; không có dữ liệu nào được nạp.")
                elif run_result.status == "SUCCEEDED":
                    st.success(f"Pipeline chạy thành công! Run ID: {run_result.pipeline_run_id}")
                else:
                    st.error(f"Pipeline chạy thất bại! Xem chi tiết lỗi ở Tab 'Tiến độ Chạy'")
            except Exception as ex:
                st.error(f"Lỗi hệ thống khi chạy pipeline: {sanitize_message(ex)}")
            finally:
                lock.release()

# ==============================================================================
# TAB 4: PIPELINE PROGRESS
# ==============================================================================
with tab_progress:
    st.subheader("Nhật ký & Tiến độ chạy chi tiết")

    res = st.session_state.last_run_result
    if res is None:
        st.info("Chưa có thông tin chạy pipeline trong phiên này. Hãy chạy pipeline tại Tab 'Điều khiển Step' hoặc 'Auto-Demo'.")
    else:
        # Run Summary Card
        status_color = "badge-ok" if res.status == "SUCCEEDED" else ("badge-warning" if res.status == "DRY_RUN" else "badge-error")
        st.markdown(f"""
        <div class="db-status-card">
            <h3>Kết quả Pipeline Run</h3>
            <p><b>Run ID:</b> {res.pipeline_run_id}</p>
            <p><b>Batch ID:</b> {res.batch_id}</p>
            <p><b>Trạng thái:</b> <span class="badge {status_color}">{res.status}</span></p>
            <p><b>Bắt đầu:</b> {res.started_at}</p>
            <p><b>Kết thúc:</b> {res.finished_at}</p>
        </div>
        """, unsafe_allow_html=True)

        # Details table
        st.markdown("### Tiến độ từng Step")
        steps_data = []
        for step in res.steps:
            duration = (datetime.fromisoformat(step.finished_at) - datetime.fromisoformat(step.started_at)).total_seconds() if isinstance(step.finished_at, str) else (step.finished_at - step.started_at).total_seconds()
            steps_data.append({
                "Tên Step": step.step_name,
                "Trạng thái": step.status,
                "Thời gian (s)": f"{duration:.2f}",
                "Dòng đọc": f"{step.rows_read:,}",
                "Dòng nạp": f"{step.loaded:,}",
                "Dòng cách ly (Reject)": f"{step.rejected:,}",
                "Lỗi (Error Code)": step.error_code or "",
                "Thông báo lỗi": sanitize_message(step.error_message or "")
            })

        st.dataframe(pd.DataFrame(steps_data), width="stretch", hide_index=True)

# ==============================================================================
# TAB 5: WAREHOUSE STATUS
# ==============================================================================
with tab_warehouse:
    st.subheader("Trạng thái Kho dữ liệu PostgreSQL")

    if not db_health.get("postgres_warehouse", {}).get("connected", False):
        st.error("Không thể kết nối đến PostgreSQL Warehouse.")
    else:
        # 1. Row Counts Staging/NDS/DDS
        st.markdown("### 1. Số lượng dòng tại các bảng")
        counts = repo.get_warehouse_row_counts()

        col_stg, col_nds, col_dds = st.columns(3)
        with col_stg:
            st.markdown("**Sơ đồ Staging**")
            stg_df = pd.DataFrame([{"Bảng": t, "Số dòng": f"{c:,}" if c >= 0 else "Chưa tạo"} for t, c in counts["staging"].items()])
            st.dataframe(stg_df, width="stretch", hide_index=True)

        with col_nds:
            st.markdown("**Sơ đồ NDS**")
            nds_df = pd.DataFrame([{"Bảng": t, "Số dòng": f"{c:,}" if c >= 0 else "Chưa tạo"} for t, c in counts["nds"].items()])
            st.dataframe(nds_df, width="stretch", hide_index=True)

        with col_dds:
            st.markdown("**Sơ đồ DDS**")
            dds_df = pd.DataFrame([{"Bảng": t, "Số dòng": f"{c:,}" if c >= 0 else "Chưa tạo"} for t, c in counts["dds"].items()])
            st.dataframe(dds_df, width="stretch", hide_index=True)

        # 2. Batch History
        st.markdown("### 2. Lịch sử các Batch chạy gần đây (audit.metadata_etl_batch)")
        batches = repo.get_etl_batches()
        if batches is None:
            st.warning("Không thể đọc lịch sử batch; kiểm tra schema hoặc kết nối warehouse.")
        elif batches:
            st.dataframe(pd.DataFrame(batches), width="stretch", hide_index=True)
        else:
            st.info("Chưa có lượt chạy ETL nào được ghi nhận.")

        # 3. Reconciliation Status
        st.markdown("### 3. Kết quả Đối soát dữ liệu (Reconciliation)")
        recon = repo.get_reconciliation_results(release_id)
        if recon:
            recon_data = []
            for item in recon:
                status = "✅ OK" if item["passed"] else "❌ Mismatch"
                recon_data.append({
                    "Chỉ số đối soát": item["name"],
                    "Thực tế (Actual)": item["actual"],
                    "Kỳ vọng (Expected)": item["expected"],
                    "Trạng thái": status,
                    "Chi tiết lỗi": item.get("error", "")
                })
            st.dataframe(pd.DataFrame(recon_data), width="stretch", hide_index=True)
        else:
            st.info("Chưa có dữ liệu đối soát.")

# ==============================================================================
# TAB 6: DQ & QUARANTINE
# ==============================================================================
with tab_dq:
    st.subheader("Thống kê Chất lượng Dữ liệu (Data Quality) & Bản ghi lỗi")

    if not db_health.get("postgres_warehouse", {}).get("connected", False):
        st.error("Không thể kết nối đến PostgreSQL Warehouse.")
    else:
        col_dq, col_qr = st.columns(2)

        with col_dq:
            st.markdown("### 1. Tổng số lỗi DQ theo Luật (dq.dq_issue)")
            dq_summary = repo.get_dq_issues_summary()
            if dq_summary is None:
                st.warning("Không thể đọc bảng dq.dq_issue.")
            elif dq_summary:
                st.dataframe(pd.DataFrame(dq_summary), width="stretch", hide_index=True)
            else:
                st.success("Không phát hiện lỗi DQ nào!")

        with col_qr:
            st.markdown("### 2. Tổng số dòng bị Cách ly (dq.quarantine_record)")
            qr_summary = repo.get_quarantine_records_summary()
            if qr_summary is None:
                st.warning("Không thể đọc bảng dq.quarantine_record.")
            elif qr_summary:
                st.dataframe(pd.DataFrame(qr_summary), width="stretch", hide_index=True)
            else:
                st.success("Không có bản ghi nào bị cách ly!")

        st.markdown("---")
        st.markdown("### 3. Chi tiết các dòng bị cách ly gần đây (Mẫu an toàn)")
        quarantine_records = repo.get_quarantine_records(limit=10)

        if quarantine_records is None:
            st.warning("Không thể đọc chi tiết quarantine.")
        elif quarantine_records:
            for rec in quarantine_records:
                with st.expander(f"Quarantine ID: {rec['quarantine_id']} | Entity: {rec['source_entity']} | Rule: {rec['error_rule_code']}"):
                    st.write(f"**Batch ID:** {rec['batch_id']}")
                    st.write(f"**Release ID:** {rec['release_id']}")
                    st.write(f"**Thời gian cách ly:** {rec['quarantined_at']}")
                    st.json(sanitize_for_display(rec["raw_payload"]))
        else:
            st.info("Không có bản ghi nào trong Quarantine schema.")

# ==============================================================================
# TAB 7: BASIC DEMO
# ==============================================================================
with tab_demo:
    st.subheader("Kịch bản Demo Tích hợp Tự động (Auto-Demo)")
    st.markdown("""
    Kịch bản này sẽ thực hiện toàn bộ luồng pipeline từ kiểm tra nguồn, nạp Staging, chuẩn hóa NDS,
    mô hình hóa DDS, đối soát dữ liệu (Reconciliation) và đánh dấu sẵn sàng cho BI.
    """)

    if is_running:
        st.warning("⚠️ Đang có tiến trình pipeline đang chạy. Vui lòng chờ...")

    demo_runner = PipelineRunner(
        release_id=release_id,
        data_root=REPO_ROOT / "data",
        demo_config_path=REPO_ROOT / "configs" / "demo" / "basic_demo.yml"
    )

    st.markdown("**Các bước thực thi theo thứ tự:**")
    st.code(" -> ".join(demo_runner.steps), language="text")

    st.warning("⚠️ Thao tác này sẽ ghi đè và đồng bộ lại toàn bộ các bảng trong Kho.")
    demo_confirmed = st.checkbox("Tôi xác nhận chạy quy trình Auto-Demo toàn bộ này", key="demo_confirm")

    demo_dry_run = st.checkbox("Chỉ chạy mô phỏng (Dry Run)", key="demo_dry_run")

    demo_btn_disabled = is_running or not demo_confirmed

    if st.button("🚀 Khởi chạy Auto-Demo", disabled=demo_btn_disabled, width="stretch", type="primary"):
        if not lock.acquire():
            st.error("Không thể khóa pipeline. Có thể một session khác đã chạy trước.")
        else:
            try:
                st.info("Đang chạy Auto-Demo Flow...")
                demo_result = demo_runner.run(dry_run=demo_dry_run, fail_fast=True)
                st.session_state.last_run_result = demo_result

                if is_dds_ready(demo_result, demo_dry_run):
                    st.success("🎉 DDS Ready for BI")
                    st.markdown("""
                    ### 📊 Hướng dẫn kết nối công cụ BI:
                    1. Mở tệp báo cáo Power BI (`deliverables/` hoặc cấu hình riêng).
                    2. Nhấp vào nút **Refresh** trên thanh công cụ để cập nhật dữ liệu.
                    3. Kiểm tra các biểu đồ Driver Performance và Fleet Utilization.
                    """)
                elif demo_dry_run:
                    st.info("ℹ️ Dry run completed - no data was loaded")
                else:
                    st.error("❌ Auto-Demo thất bại. Vui lòng kiểm tra nhật ký chạy ở Tab 'Tiến độ Chạy'")
            except Exception as e:
                st.error(f"Lỗi nghiêm trọng: {sanitize_message(e)}")
            finally:
                lock.release()

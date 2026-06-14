# -*- coding: utf-8 -*-
"""Streamlit app for Data Pipeline Control Panel.

Provides monitoring, data exploration, validation, and orchestration controls.
"""

from __future__ import annotations

import base64
import html
import sys
from datetime import datetime
from pathlib import Path
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

# Custom Styling (Scoped CSS for elements)
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
tab_overview, tab_pipeline, tab_dq, tab_explorer = st.tabs([
    "🏥 Tổng quan Hệ thống",
    "⚙️ Vận hành Pipeline",
    "🛡️ Chất lượng & Đối soát",
    "🔌 Khám phá Nguồn"
])

# ==============================================================================
# TAB 1: OVERVIEW & SYSTEM HEALTH
# ==============================================================================
with tab_overview:
    st.subheader("🏥 Trạng thái Kết nối Hệ thống")

    # Render Status Cards sử dụng HTML/CSS nội bộ
    health_cols = st.columns(4)
    db_names = [
        ("MySQL HR", "mysql_hr"),
        ("MongoDB Fleet", "mongodb_fleet"),
        ("Postgres Dispatch", "postgres_dispatch"),
        ("Postgres Warehouse", "postgres_warehouse")
    ]

    for idx, (title, key) in enumerate(db_names):
        with health_cols[idx]:
            info = db_health.get(key, {})
            connected = info.get("connected", False)
            bg_color = "#DEF7EC" if connected else "#FDE8E8"
            border_color = "#BCF0DA" if connected else "#F8B4B4"
            text_color = "#03543F" if connected else "#9B1C1C"
            status_text = "🟢 Connected" if connected else "🔴 Disconnected"
            safe_title = html.escape(title)
            safe_host = html.escape(str(info.get("host", "N/A")))
            safe_port = html.escape(str(info.get("port", "N/A")))

            st.markdown(f"""
            <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                <h5 style="margin: 0; color: {text_color}; font-size: 1rem;">{safe_title}</h5>
                <p style="margin: 4px 0 0 0; font-weight: bold; color: {text_color}; font-size: 0.9rem;">{status_text}</p>
                <p style="margin: 2px 0 0 0; font-size: 0.75rem; color: {text_color}; opacity: 0.8;">{safe_host}:{safe_port}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. Schema Physical Row Count Metrics
    st.subheader("📊 Số lượng dòng vật lý theo tầng (Physical Rows)")

    counts = repo.get_warehouse_row_counts()
    metric_cols = st.columns(3)

    schemas = [("Staging", "staging"), ("NDS (3NF)", "nds"), ("DDS (Star)", "dds")]
    for idx, (label, schema_key) in enumerate(schemas):
        with metric_cols[idx]:
            schema_counts = counts.get(schema_key, {})
            # Kiểm tra xem có bảng nào lỗi (-1) không
            if not schema_counts or any(c < 0 for c in schema_counts.values()):
                val_display = "Unavailable"
            else:
                total_rows = sum(schema_counts.values())
                val_display = f"{total_rows:,}"

            st.metric(
                label=f"Tổng dòng vật lý {label}",
                value=val_display,
                help=f"Tổng số dòng thực tế ghi nhận trên toàn bộ các bảng thuộc schema {schema_key}. Không đại diện cho số thực thể nghiệp vụ duy nhất."
            )

    st.markdown("---")

    # 3. Mermaid Flowchart
    st.subheader("📐 Sơ đồ Luồng Dữ liệu Kiến trúc")
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
        classDef default color:#0f172a;
    """

    html_code = f"""
    <div class="mermaid" style="display: flex; justify-content: center; background-color: white; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; overflow-x: auto;">
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

    st.markdown("---")

    # 4. Detail Table Counts (Xếp chồng tự nhiên cho cả Desktop & Mobile)
    st.subheader("📋 Chi tiết Bảng dữ liệu theo Schema")

    for label, schema_key in schemas:
        with st.expander(f"Chi tiết bảng thuộc Schema {label}"):
            schema_counts = counts.get(schema_key, {})
            if not schema_counts:
                st.warning(f"Không thể truy vấn thông tin bảng thuộc schema {schema_key}.")
            else:
                table_rows = []
                for table, c in schema_counts.items():
                    status_text = f"{c:,}" if c >= 0 else "Unavailable / Chưa tạo"
                    table_rows.append({"Tên Bảng": table, "Số dòng vật lý": status_text})

                df_counts = pd.DataFrame(table_rows)
                st.dataframe(df_counts, width="stretch", hide_index=True)

# ==============================================================================
# TAB 2: PIPELINE OPERATIONS
# ==============================================================================
with tab_pipeline:
    st.subheader("⚙️ Điều khiển & Vận hành Pipeline")

    if is_running:
        st.warning("⚠️ Đang có tiến trình pipeline đang chạy. Vui lòng chờ cho đến khi tiến trình hoàn tất.")

    runner = PipelineRunner(release_id=release_id, data_root=REPO_ROOT / "data")

    # 1. Pipeline Controls (Khu vực chính)
    col_step, col_opts = st.columns([2, 1])
    with col_step:
        options_step = ["Tất cả các bước (All Steps)"] + runner.steps
        selected_run_step = st.selectbox("Chọn bước muốn chạy", options_step)

        # Confirmation box for data-writing steps
        data_writing_steps = {"load_staging", "load_nds", "load_dds"}
        is_writing_step = selected_run_step == "Tất cả các bước (All Steps)" or selected_run_step in data_writing_steps

        confirmed = True
        if is_writing_step:
            st.warning("⚠️ Bước này có tác động thay đổi hoặc ghi đè dữ liệu kho.")
            confirmed = st.checkbox("Tôi xác nhận muốn thực thi thao tác ghi dữ liệu này", key="confirm_step_run")

    with col_opts:
        dry_run = st.checkbox("Dry Run (Chỉ mô phỏng kết quả)", value=False)
        fail_fast = st.checkbox("Fail Fast (Dừng ngay khi có lỗi)", value=True)

    step_param = None if selected_run_step == "Tất cả các bước (All Steps)" else selected_run_step
    btn_disabled = is_running or (is_writing_step and not confirmed)

    if st.button("🚀 Thực thi Pipeline", disabled=btn_disabled, width="stretch", type="primary"):
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
                    st.error(f"Pipeline chạy thất bại! Xem chi tiết ở phần kết quả bên dưới.")
            except Exception as ex:
                st.error(f"Lỗi hệ thống khi chạy pipeline: {sanitize_message(ex)}")
            finally:
                lock.release()

    # 2. Auto-Demo (Presentation Mode) đặt trong expander
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🚀 Chế độ Demo Thuyết trình (Presentation Mode)"):
        st.markdown("""
        Kịch bản này sẽ tự động thực hiện toàn bộ luồng pipeline từ kiểm tra nguồn, nạp Staging,
        chuẩn hóa NDS, mô hình hóa DDS, đối soát và đánh dấu sẵn sàng cho BI.
        """)
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

        if st.button("🚀 Khởi chạy Auto-Demo", disabled=demo_btn_disabled, width="stretch", key="btn_run_demo"):
            if not lock.acquire():
                st.error("Không thể khóa pipeline. Có thể một session khác đã khởi chạy trước.")
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
                        st.error("❌ Auto-Demo thất bại. Vui lòng kiểm tra nhật ký chạy ở dưới.")
                except Exception as e:
                    st.error(f"Lỗi nghiêm trọng: {sanitize_message(e)}")
                finally:
                    lock.release()

    st.markdown("---")

    # 3. Last Session Result & Batch Audit History
    st.subheader("📋 Nhật ký & Lịch sử Chạy")

    col_session, col_audit = st.columns(2)

    with col_session:
        st.markdown("### Kết quả Session hiện tại")
        res = st.session_state.last_run_result
        if res is None:
            st.info("Chưa có lượt chạy nào trong phiên này.")
        else:
            status_color = "badge-ok" if res.status == "SUCCEEDED" else ("badge-warning" if res.status == "DRY_RUN" else "badge-error")
            safe_run_id = html.escape(str(res.pipeline_run_id))
            safe_batch_id = html.escape(str(res.batch_id))
            safe_status = html.escape(str(res.status))
            safe_started_at = html.escape(str(res.started_at))
            safe_finished_at = html.escape(str(res.finished_at))
            st.markdown(f"""
            <div class="db-status-card">
                <h5>Run ID: {safe_run_id}</h5>
                <p><b>Batch ID:</b> {safe_batch_id}</p>
                <p><b>Trạng thái:</b> <span class="badge {status_color}">{safe_status}</span></p>
                <p><b>Bắt đầu:</b> {safe_started_at}</p>
                <p><b>Kết thúc:</b> {safe_finished_at}</p>
            </div>
            """, unsafe_allow_html=True)

            # Bảng tiến độ step (Chỉ các cột cốt lõi)
            st.markdown("**Chi tiết từng Step**")
            steps_data = []
            errors_data = []
            for step in res.steps:
                duration = (datetime.fromisoformat(step.finished_at) - datetime.fromisoformat(step.started_at)).total_seconds() if isinstance(step.finished_at, str) else (step.finished_at - step.started_at).total_seconds()
                steps_data.append({
                    "Tên Step": step.step_name,
                    "Trạng thái": step.status,
                    "Thời gian (s)": f"{duration:.2f}",
                    "Dòng nạp": f"{step.loaded:,}"
                })
                if step.error_code or step.error_message:
                    errors_data.append({
                        "Step": step.step_name,
                        "Mã lỗi": step.error_code or "N/A",
                        "Nội dung lỗi": sanitize_message(step.error_message or "")
                    })

            st.dataframe(pd.DataFrame(steps_data), width="stretch", hide_index=True)

            # Đưa error detail vào expander riêng bên dưới bảng để giữ layout gọn gàng
            if errors_data:
                with st.expander("⚠️ Chi tiết lỗi xảy ra trong các Step"):
                    st.dataframe(pd.DataFrame(errors_data), width="stretch", hide_index=True)

    with col_audit:
        st.markdown("### Lịch sử Batch (audit.metadata_etl_batch)")
        batches = repo.get_etl_batches(limit=5)
        if batches is None:
            st.warning("Không thể truy cập dữ liệu lịch sử (Database disconnected hoặc bảng chưa được tạo).")
        elif not batches:
            st.info("Chưa có lượt chạy ETL nào được ghi nhận trong cơ sở dữ liệu.")
        else:
            # Chỉ hiển thị các trường cốt lõi trong bảng lịch sử
            batches_df = pd.DataFrame([
                {
                    "Batch ID": b.get("batch_id"),
                    "Trạng thái": b.get("batch_status"),
                    "Source": b.get("source_system"),
                    "Dòng nạp": f"{b.get('row_count_loaded', 0):,}" if b.get('row_count_loaded') is not None else "0",
                    "Bắt đầu": b.get("batch_started_at", "")[:19] # Cắt bớt phần mili giây để hiển thị đẹp
                }
                for b in batches
            ])
            st.dataframe(batches_df, width="stretch", hide_index=True)

            # Expander hiển thị lỗi của các batch cũ
            old_batch_errors = [
                {"Batch ID": b.get("batch_id"), "Lỗi": sanitize_message(b.get("error_message"))}
                for b in batches if b.get("error_message")
            ]
            if old_batch_errors:
                with st.expander("⚠️ Chi tiết lỗi của các Batch lịch sử"):
                    st.dataframe(pd.DataFrame(old_batch_errors), width="stretch", hide_index=True)

# ==============================================================================
# TAB 3: DATA QUALITY & RECONCILIATION
# ==============================================================================
with tab_dq:
    st.subheader("🛡️ Giám sát Chất lượng & Đối soát Dữ liệu")

    if not db_health.get("postgres_warehouse", {}).get("connected", False):
        st.error("Không thể kết nối đến PostgreSQL Warehouse để lấy thông tin DQ.")
    else:
        # 1. Reconciliation (Kết quả Đối soát chéo) - Đưa lên đầu
        st.markdown("### 1. Đối soát Dữ liệu Đầu vào - Đầu ra (Reconciliation)")
        recon = repo.get_reconciliation_results(release_id)
        if not recon:
            st.info("Chưa có kết quả đối soát nào cho phiên bản dữ liệu hiện tại.")
        else:
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

        st.markdown("---")

        # 2. Data Quality & Quarantine Summaries
        col_dq_sum, col_qr_sum = st.columns(2)
        with col_dq_sum:
            st.markdown("### 2. Tổng số lỗi DQ theo Luật (dq.dq_issue)")
            dq_summary = repo.get_dq_issues_summary()
            if dq_summary is None:
                st.warning("Không thể truy vấn bảng dq.dq_issue.")
            elif not dq_summary:
                st.success("Không phát hiện lỗi chất lượng dữ liệu (DQ) nào!")
            else:
                st.dataframe(pd.DataFrame(dq_summary), width="stretch", hide_index=True)

        with col_qr_sum:
            st.markdown("### 3. Số bản ghi bị cách ly (dq.quarantine_record)")
            qr_summary = repo.get_quarantine_records_summary()
            if qr_summary is None:
                st.warning("Không thể truy vấn bảng dq.quarantine_record.")
            elif not qr_summary:
                st.success("Không có bản ghi nào bị đưa vào Quarantine!")
            else:
                st.dataframe(pd.DataFrame(qr_summary), width="stretch", hide_index=True)

        st.markdown("---")

        # 3. Quarantine Details (Bản ghi lỗi chi tiết)
        st.markdown("### 4. Chi tiết các bản ghi bị cách ly gần đây (Mẫu an toàn)")
        quarantine_records = repo.get_quarantine_records(limit=10)

        if quarantine_records is None:
            st.warning("Không thể truy cập dữ liệu quarantine.")
        elif not quarantine_records:
            st.info("Không có bản ghi lỗi nào trong Quarantine schema.")
        else:
            for rec in quarantine_records:
                with st.expander(f"Quarantine ID: {rec['quarantine_id']} | Entity: {rec['source_entity']} | Rule: {rec['error_rule_code']}"):
                    st.write(f"**Batch ID:** {rec['batch_id']}")
                    st.write(f"**Release ID:** {rec['release_id']}")
                    st.write(f"**Thời gian cách ly:** {rec['quarantined_at']}")
                    st.json(sanitize_for_display(rec["raw_payload"]))

# ==============================================================================
# TAB 4: SOURCE EXPLORER
# ==============================================================================
with tab_explorer:
    st.subheader("🔌 Truy cập dữ liệu mẫu từ Nguồn (Source Explorer)")

    col_sys, col_ent, col_lim = st.columns([1, 1, 1])
    with col_sys:
        selected_system = st.selectbox(
            "Hệ thống Nguồn",
            options=["mysql_hr", "mongodb_fleet", "postgres_dispatch"],
            format_func=lambda x: x.upper().replace("_", " "),
            key="explorer_system"
        )
    with col_ent:
        entities_map = {
            "mysql_hr": ["drivers", "driver_changes"],
            "mongodb_fleet": ["vehicles"],
            "postgres_dispatch": ["shifts", "trip_assignments"]
        }
        selected_entity = st.selectbox(
            "Thực thể (Bảng/Collection)",
            options=entities_map[selected_system],
            key="explorer_entity"
        )
    with col_lim:
        selected_limit = st.slider("Giới hạn số dòng", min_value=1, max_value=100, value=10, key="explorer_limit")

    if st.button("🔍 Đọc dữ liệu mẫu", width="stretch", key="btn_explorer_read"):
        try:
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

# Data Pipeline Control Panel

Status: `IMPLEMENTED; FULL WRITE PIPELINE VALIDATION PENDING`

Streamlit Control Panel (`app/streamlit_app.py`) là giao diện vận hành kỹ thuật
cho pipeline, không phải dashboard BI. Power BI hoặc BI tool thay thế chạy độc
lập và không được nhúng vào Streamlit.

Theme sáng Green Taxi được cấu hình tại `.streamlit/config.toml`. Ứng dụng chỉ
dùng widget Streamlit chuẩn và CSS có phạm vi trên các HTML card do dự án tự
render; không phụ thuộc custom component UI bên thứ ba.

## Chạy ứng dụng

```powershell
python -m pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

CLI dùng cùng `PipelineRunner`:

```powershell
python scripts/run_pipeline.py --release-id green-taxi-full-v1 --dry-run
python scripts/run_pipeline.py --release-id green-taxi-full-v1
```

## Bốn tab tiêu chuẩn

1. **Tổng quan Hệ thống:** Hiển thị Database Health (dạng status cards), Schema Metrics (tổng dòng vật lý của Staging/NDS/DDS), sơ đồ luồng dữ liệu Mermaid, và chi tiết số dòng từng bảng (expander tự xếp chồng).
2. **Vận hành Pipeline:** Chứa bộ điều khiển chạy pipeline (từng step hoặc toàn bộ), kết quả lượt chạy hiện tại, lịch sử các Batch chạy gần đây, và chế độ Demo Thuyết trình (Auto-Demo) nằm gọn trong expander.
3. **Chất lượng & Đối soát:** Tổng hợp kết quả đối soát dữ liệu (Reconciliation), tóm tắt lỗi DQ theo luật, và các bản ghi bị cách ly (Quarantine) dạng JSON trong expander.
4. **Khám phá Nguồn:** Cho phép DE truy vấn nhanh dữ liệu thô từ các database nguồn (MySQL, MongoDB, Postgres Dispatch).

Các tổng Staging/NDS/DDS là **số dòng vật lý theo schema**, không phải số thực
thể nghiệp vụ duy nhất. Khi connection hoặc table không khả dụng, UI hiển thị
`Unavailable`/`N/A` thay vì giả thành `0`. Batch history trong tab Vận hành đọc
từ `audit.metadata_etl_batch`, tách biệt với kết quả gần nhất lưu trong
`st.session_state`.

Streamlit không chứa SQL, không gọi subprocess và không sao chép ETL logic.
Database query nằm trong `MonitoringRepository`; orchestration gọi loader hiện
có qua `PipelineRunner`.

## DDS Ready

`DDS Ready for BI` chỉ hiển thị khi đồng thời thỏa:

- không phải dry-run;
- run có status `SUCCEEDED`;
- có step `mark_dds_ready`;
- step đó có status `SUCCEEDED`.

`SKIPPED`, `DRY_RUN`, `FAILED` hoặc thiếu step đều không được coi là ready.
Dry-run có run-level status `DRY_RUN` và hiển thị thông báo riêng rằng không có
dữ liệu được nạp.

## Lock và stale recovery

`data/.pipeline.lock` được tạo bằng exclusive creation và chứa PID, hostname,
created timestamp, owner token. Owner token ngăn session khác release lock.
Lock cùng host có PID còn hoạt động không bị xóa. Lock host khác chỉ stale sau
TTL mặc định 6 giờ. Metadata corrupt còn mới được giữ lại; corrupt lock quá TTL
có thể phục hồi.

Stale recovery dùng file guard độc quyền để hai process không cùng xóa lock.
Sau khi process bình thường kết thúc, `finally` release lock. Process kill hoặc
mất điện không chạy được `finally`; lần acquire sau sẽ kiểm tra và phục hồi
stale lock.

Hai file lock nằm trong `.gitignore`.

## Health cache và lỗi UI

Health check được bọc bằng `st.cache_data(ttl=30)`. Nút refresh chỉ clear cache
health này; connection/client object không được cache. Khi Docker tắt, app hiển
thị trạng thái disconnected thay vì crash.

Mọi exception và payload có khả năng chứa secret phải đi qua API sanitize dùng
chung trong `src.monitoring.repository`. Password, token, API key/secret và
credential trong database URI được che trước khi render. Query lỗi được hiển
thị là không khả dụng, không bị diễn giải thành bảng rỗng hợp lệ.

## Giới hạn hiện tại

- Mermaid tải module từ CDN; khi offline có thể không render.
- Streamlit không có breakpoint server-side ổn định; layout dùng expander và
  khả năng tự xếp chồng của widget thay vì phát hiện viewport.
- File lock phù hợp demo local/shared filesystem, không thay thế distributed lock.
- Control Panel chạy pipeline đồng bộ trong Streamlit process.
- Chưa khẳng định full write pipeline đã pass trên môi trường sạch chỉ dựa vào
  unit tests hoặc UI smoke test.
- Dashboard nghiệp vụ, semantic model và Power BI report vẫn là deliverable riêng.

# Data Pipeline Control Panel

Status: `IMPLEMENTED; FULL WRITE PIPELINE VALIDATION PENDING`

Streamlit Control Panel (`app/streamlit_app.py`) là giao diện vận hành kỹ thuật
cho pipeline, không phải dashboard BI. Power BI hoặc BI tool thay thế chạy độc
lập và không được nhúng vào Streamlit.

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

## Bảy tab hiện có

1. **Tổng quan:** Mermaid data flow và health của bốn database.
2. **Khám phá Nguồn:** đọc entity whitelist, tối đa 100 dòng.
3. **Điều khiển Step:** chạy một step hoặc toàn pipeline, dry-run/fail-fast.
4. **Tiến độ Chạy:** giữ kết quả gần nhất trong `st.session_state`.
5. **Trạng thái Kho:** row count, batch history và reconciliation.
6. **DQ & Quarantine:** summary và payload mẫu đã sanitize.
7. **Auto-Demo:** chạy thứ tự step từ `configs/demo/basic_demo.yml`.

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
Dry-run hiển thị thông báo riêng rằng không có dữ liệu được nạp.

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
- File lock phù hợp demo local/shared filesystem, không thay thế distributed lock.
- Control Panel chạy pipeline đồng bộ trong Streamlit process.
- Chưa khẳng định full write pipeline đã pass trên môi trường sạch chỉ dựa vào
  unit tests hoặc UI smoke test.
- Dashboard nghiệp vụ, semantic model và Power BI report vẫn là deliverable riêng.

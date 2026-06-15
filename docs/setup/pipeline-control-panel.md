# Data Pipeline Control Panel

> Trạng thái: `IMPLEMENTED; FULL WRITE PIPELINE VALIDATED VIA PIPELINERUNNER`

---

## Overview

Streamlit Control Panel ([app/streamlit_app.py](../../app/streamlit_app.py)) là giao diện vận hành kỹ thuật cho pipeline, không phải dashboard BI. Apache Superset hoặc BI client được phê duyệt chạy độc lập và không được nhúng vào Streamlit.

> [!NOTE]
> Giao diện áp dụng Green Taxi Light Theme bằng CSS cục bộ trong `app/streamlit_app.py`. Ứng dụng chỉ sử dụng các thành phần (widgets) nguyên bản của Streamlit và CSS cục bộ (Scoped CSS) được bọc trong các HTML card tự định dạng, nhằm triệt tiêu hoàn toàn rủi ro xung đột dependency từ các custom component UI bên thứ ba.

---

## Running The App

### Streamlit UI
```powershell
# Cài đặt các thư viện liên quan
python -m pip install -r requirements.txt

# Khởi chạy ứng dụng
streamlit run app/streamlit_app.py
```

### PipelineRunner CLI
```powershell
# Chạy mô phỏng (Dry run)
python scripts/run_pipeline.py --release-id green-taxi-full-v1 --dry-run

# Chạy thực tế ghi dữ liệu
python scripts/run_pipeline.py --release-id green-taxi-full-v1
```

---

## Four Standard Tabs

Ứng dụng được tổ chức lại thành 4 tab tiêu chuẩn để tối ưu hóa khả năng tương tác và hiển thị:

1.  **System Overview:** Hiển thị database health, schema metrics, Mermaid data flow và row count theo table.
2.  **Pipeline Operations:** Điều khiển pipeline theo từng step hoặc toàn bộ flow, hiển thị session result, batch audit history và presentation auto-demo.
3.  **DQ & Reconciliation:** Tổng hợp reconciliation input/output, DQ issue summary và quarantine records ở dạng JSON.
4.  **Source Explorer:** Cho phép DE truy vấn nhanh sample records trực tiếp từ source databases: MySQL, MongoDB và PostgreSQL Dispatch.

> [!IMPORTANT]
> **Quy tắc Quản lý Dữ liệu trên UI:**
> *   Các chỉ số đếm dòng tại Staging/NDS/DDS biểu thị **số lượng dòng vật lý ghi nhận thực tế trên schema**, không đại diện cho số thực thể nghiệp vụ duy nhất.
> *   Khi kết nối hoặc bảng không khả dụng, UI bắt buộc hiển thị **`Unavailable`** hoặc **`N/A`**, tuyệt đối không tự động hiển thị mặc định là số `0` gây hiểu nhầm.
> *   Lịch sử batch (Batch history) trong tab Vận hành được đọc trực tiếp từ bảng `audit.metadata_etl_batch`, hoạt động hoàn toàn độc lập với kết quả chạy tạm thời của phiên làm việc lưu trong `st.session_state`.
> *   Streamlit không chứa bất kỳ câu lệnh SQL nghiệp vụ nào, không gọi subprocess và không sao chép logic ETL. Mọi tương tác dữ liệu phải thông qua `MonitoringRepository` và `PipelineRunner`.

---

## DDS Ready for BI

Chỉ số ready cho BI (`DDS Ready for BI`) chỉ hiển thị khi đồng thời thỏa mãn các điều kiện sau:

- [x] Không phải là lượt chạy mô phỏng (`dry_run = False`);
- [x] Phiên chạy có kết quả trạng thái là `SUCCEEDED`;
- [x] Có thực thi step `mark_dds_ready`;
- [x] Step `mark_dds_ready` hoàn thành với trạng thái `SUCCEEDED`.

> [!WARNING]
> Các trạng thái `SKIPPED`, `DRY_RUN`, `FAILED` hoặc thiếu step đánh dấu đều không được coi là ready. Các lượt chạy dry-run sẽ trả về trạng thái chạy `DRY_RUN` và hiển thị thông báo rõ ràng rằng không có dữ liệu nào được ghi đè vào kho.

---

## Locking And Stale Lock Recovery

File lock `data/.pipeline.lock` được tạo theo cơ chế độc quyền (exclusive creation) và chứa siêu dữ liệu: PID, hostname, thời điểm tạo (timestamp) và owner token.
*   **Owner Token:** Giúp ngăn chặn các session khác vô tình giải phóng lock của session hiện tại.
*   **Active Lock:** Lock được tạo cùng host và có PID đang hoạt động sẽ không bị xóa.
*   **Stale Lock:** Lock thuộc host khác chỉ được coi là stale sau thời gian TTL mặc định (6 giờ).
*   **Stale Recovery:** Quá trình khôi phục khóa stale sử dụng file guard độc quyền để tránh xung đột giữa hai process tranh chấp.
*   **Xử lý lỗi đột ngột:**
    *   *Lỗi runtime bình thường:* Lock được tự động giải phóng qua khối lệnh `finally` khi kết thúc luồng.
    *   *Lỗi nghiêm trọng (Process kill / Mất điện):* Khối lệnh `finally` không thể thực thi; lock sẽ tồn tại tạm thời và được tự động dọn dẹp (Stale recovery) ở lượt acquire tiếp theo thông qua kiểm tra timestamp và trạng thái PID.

---

## Connection Cache And Error Handling

*   **Health Cache:** Trạng thái kết nối (Health check) được cache thông qua `@st.cache_data(ttl=30)`. Nút `🔄 Làm mới trạng thái` thực hiện xóa cache này để kiểm tra lại trực tiếp; bản thân connection object không được cache. Khi Docker bị tắt, app sẽ hiển thị trạng thái disconnected thay vì bị crash ứng dụng.
*   **Bảo mật thông tin (Sanitization):** Mọi exception và payload lỗi có nguy cơ rò rỉ thông tin nhạy cảm bắt buộc phải đi qua API che thông tin (`sanitize_message` / `sanitize_for_display`) trong `src.monitoring.repository`. Tất cả mật khẩu, token, API keys và URI database được che bằng ký tự `***` trước khi render lên màn hình.

---

## Current Architecture Limits

*   **Mermaid CDN:** Sơ đồ Mermaid tải thư viện dựng hình từ CDN trực tuyến; nếu chạy offline có thể không hiển thị được sơ đồ trực quan.
*   **Thiết kế Mobile:** Streamlit không cung cấp breakpoint server-side; do đó layout sử dụng cơ chế tự động co giãn (responsive) và expander thay vì cố gắng bắt độ rộng viewport của thiết bị.
*   **Tầm ảnh hưởng của Lock:** Cơ chế file lock cục bộ chỉ phù hợp khi chạy thử nghiệm trên máy local hoặc thư mục chia sẻ (shared filesystem); không thay thế cho các giải pháp khóa phân tán (distributed lock) trên production.
*   **Cadence Vận hành:** Control Panel chạy pipeline ở chế độ đồng bộ (blocking main thread) trong process Streamlit.
*   **Phạm vi BI:** Control Panel chỉ giám sát hạ tầng và kỹ thuật; dashboard nghiệp vụ Superset và analytics contract là thành phần độc lập.

-- Proposal: PostgreSQL Read-Only Role for Apache Superset Connection
-- Dự án: NYC Green Taxi Driver Operations BI
-- Thiết lập quyền truy cập tối thiểu (least privilege) cho công cụ BI/Superset trên tầng DDS.
-- LƯU Ý: Đây chỉ là bản phác thảo đề xuất, KHÔNG thực thi trực tiếp trên database của hệ thống.

-- 1. Tạo role read-only với quyền LOGIN và mật khẩu bảo mật (sử dụng biến môi trường khi triển khai thực tế)
-- Placeholder: SUPERSET_RO_PASSWORD
CREATE ROLE superset_ro WITH LOGIN PASSWORD 'TBD_SUPERSET_RO_PASSWORD';

-- 2. Từ chối mặc định quyền tạo bảng trong schema public (nếu có) để đảm bảo an toàn
REVOKE ALL ON SCHEMA public FROM superset_ro;

-- 3. Cấp quyền kết nối (CONNECT) tới database warehouse
GRANT CONNECT ON DATABASE green_taxi_warehouse TO superset_ro;

-- 4. Cấp quyền sử dụng (USAGE) trên schema dds
GRANT USAGE ON SCHEMA dds TO superset_ro;

-- 5. Cấp quyền đọc (SELECT) trên toàn bộ các bảng hiện có trong schema dds
GRANT SELECT ON ALL TABLES IN SCHEMA dds TO superset_ro;

-- 6. Tự động cấp quyền đọc (SELECT) cho các bảng hoặc views được tạo mới trong tương lai thuộc schema dds
ALTER DEFAULT PRIVILEGES IN SCHEMA dds 
GRANT SELECT ON TABLES TO superset_ro;

-- 7. [ĐỀ XUẤT TƯƠNG LAI] Cấp quyền cho schema analytics (nếu được triển khai ở các workstream sau để chứa views/semantic)
-- GRANT USAGE ON SCHEMA analytics TO superset_ro;
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO superset_ro;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO superset_ro;

-- 8. Xác nhận ngăn chặn các quyền can thiệp dữ liệu (ghi/sửa/xóa)
-- Quyền INSERT, UPDATE, DELETE, TRUNCATE, ALTER, DROP đều bị từ chối mặc định do không được cấp.
-- Không cấp bất kỳ quyền nào trên schema staging và nds để bảo vệ dữ liệu thô và dữ liệu chuẩn hóa 3NF.

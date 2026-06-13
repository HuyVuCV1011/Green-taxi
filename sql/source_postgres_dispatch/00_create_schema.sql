-- 00_create_schema.sql
-- Triển khai schema cho PostgreSQL Dispatch Source System.
-- Vì docker-compose đã tạo sẵn database chuyên biệt 'green_taxi_dispatch',
-- chúng ta sẽ tạo các bảng trong schema 'public' mặc định để đơn giản hóa việc kết nối và truy vấn.

CREATE SCHEMA IF NOT EXISTS public;
COMMENT ON SCHEMA public IS 'Default public schema for green_taxi_dispatch source system';

-- 01_dispatch_tables.sql
-- Định nghĩa cấu trúc bảng cho PostgreSQL Dispatch Source System.
-- DDL này phải idempotent. Không DROP bảng ở đây vì seed script dựa vào
-- public.seed_metadata để bỏ qua file đã seed khi checksum không đổi.

-- 1. Bảng shifts (Ca trực của tài xế và xe)
CREATE TABLE IF NOT EXISTS public.shifts (
    shift_id VARCHAR(50) PRIMARY KEY,
    driver_id VARCHAR(50) NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL,
    vendor_id INT NOT NULL,
    shift_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    shift_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    assigned_start_zone INT NOT NULL,
    actual_end_zone INT NOT NULL,
    trip_count INT NOT NULL DEFAULT 0,
    occupied_minutes DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    idle_minutes DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    shift_status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
    CONSTRAINT chk_shift_times CHECK (shift_end >= shift_start),
    CONSTRAINT chk_trip_count CHECK (trip_count >= 0),
    CONSTRAINT chk_occupied_minutes CHECK (occupied_minutes >= 0),
    CONSTRAINT chk_idle_minutes CHECK (idle_minutes >= 0)
);

-- 2. Bảng trip_assignments (Phân công chuyến xe từ TLC trips)
CREATE TABLE IF NOT EXISTS public.trip_assignments (
    trip_key VARCHAR(24) PRIMARY KEY,
    source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL,
    driver_id VARCHAR(50) NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL,
    shift_id VARCHAR(50) NOT NULL,
    assignment_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    assignment_method VARCHAR(50) NOT NULL,
    CONSTRAINT chk_trip_assignments_source_row_number CHECK (source_row_number >= 2),
    CONSTRAINT chk_trip_assignments_method CHECK (assignment_method IN ('CONTINUITY', 'AVAILABLE_POOL')),
    CONSTRAINT uq_source_file_row UNIQUE (source_file, source_row_number)
);

-- 3. Bảng assignment_exceptions (Ngoại lệ phân công chuyến xe, dùng cho đối soát/audit)
-- Cột vendor_id có thể mang giá trị null đối với các bản ghi INVALID_DURATION
CREATE TABLE IF NOT EXISTS public.assignment_exceptions (
    source_file VARCHAR(255) NOT NULL,
    source_row_number INT NOT NULL,
    reason VARCHAR(100) NOT NULL,
    pickup_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    dropoff_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    vendor_id INT,
    PRIMARY KEY (source_file, source_row_number)
);

-- 4. Bảng seed_metadata (Theo dõi checksum và số dòng đã seed từ data release)
CREATE TABLE IF NOT EXISTS public.seed_metadata (
    release_id VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    row_count BIGINT NOT NULL,
    seeded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (release_id, source_file)
);

-- Thêm index để tối ưu hóa truy vấn đối soát và staging extract
CREATE INDEX IF NOT EXISTS idx_shifts_driver ON public.shifts(driver_id);
CREATE INDEX IF NOT EXISTS idx_shifts_vehicle ON public.shifts(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_trip_assignments_shift ON public.trip_assignments(shift_id);
CREATE INDEX IF NOT EXISTS idx_trip_assignments_source_file ON public.trip_assignments(source_file);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_trip_assignments_source_row_number'
    ) THEN
        ALTER TABLE public.trip_assignments
            ADD CONSTRAINT chk_trip_assignments_source_row_number CHECK (source_row_number >= 2);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_trip_assignments_method'
    ) THEN
        ALTER TABLE public.trip_assignments
            ADD CONSTRAINT chk_trip_assignments_method CHECK (assignment_method IN ('CONTINUITY', 'AVAILABLE_POOL'));
    END IF;
END $$;

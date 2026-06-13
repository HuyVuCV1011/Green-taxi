CREATE TABLE IF NOT EXISTS drivers (
  driver_id VARCHAR(16) NOT NULL,
  vendor_id INT NOT NULL,
  driver_code VARCHAR(32) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  hire_date DATE NOT NULL,
  employment_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  license_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  license_expiry_date DATE NOT NULL,
  experience_years INT NOT NULL DEFAULT 0,
  home_borough VARCHAR(32) NOT NULL,
  source_updated_at DATETIME NOT NULL,
  PRIMARY KEY (driver_id),
  UNIQUE KEY uq_drivers_driver_code (driver_code),
  KEY idx_drivers_vendor_id (vendor_id),
  CONSTRAINT chk_drivers_vendor_id CHECK (vendor_id IN (0, 1, 2)),
  CONSTRAINT chk_drivers_employment_status CHECK (employment_status IN ('ACTIVE', 'LEAVE', 'INACTIVE')),
  CONSTRAINT chk_drivers_license_status CHECK (license_status IN ('ACTIVE', 'EXPIRED', 'SUSPENDED')),
  CONSTRAINT chk_drivers_experience_years CHECK (experience_years >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS driver_changes (
  event_id VARCHAR(24) NOT NULL,
  driver_id VARCHAR(16) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  effective_at DATETIME NOT NULL,
  delivered_at DATETIME NOT NULL,
  changes JSON NOT NULL,
  is_late_arriving BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (event_id),
  KEY idx_driver_changes_driver_delivered (driver_id, delivered_at, event_id),
  KEY idx_driver_changes_effective (effective_at, event_id),
  CONSTRAINT fk_driver_changes_driver
    FOREIGN KEY (driver_id) REFERENCES drivers (driver_id),
  CONSTRAINT chk_driver_changes_temporal CHECK (delivered_at >= effective_at),
  CONSTRAINT chk_driver_changes_payload CHECK (JSON_TYPE(changes) = 'OBJECT' AND JSON_LENGTH(changes) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS seed_release_files (
  release_id VARCHAR(64) NOT NULL,
  source_entity VARCHAR(64) NOT NULL,
  source_file VARCHAR(255) NOT NULL,
  checksum_sha256 CHAR(64) NOT NULL,
  row_count BIGINT NOT NULL,
  seeded_at_utc DATETIME(6) NOT NULL,
  PRIMARY KEY (release_id, source_file),
  KEY idx_seed_release_files_entity (source_entity),
  CONSTRAINT chk_seed_release_files_row_count CHECK (row_count >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

#!/usr/bin/env python3
"""Seed the MongoDB Fleet source from the canonical vehicles release file."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_ID = "green-taxi-full-v1"


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "encoding", None) != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except AttributeError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed MongoDB Fleet from vehicles.jsonl.")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", "data"),
        help="Repository-relative or absolute data root. Default: DATA_ROOT or data.",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    values: dict[str, str] = {}
    pattern = re.compile(r"\$\{([^}:]+)(?::-[^}]*)?\}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        def replace_var(match: re.Match[str]) -> str:
            name = match.group(1)
            return os.environ.get(name, values.get(name, ""))

        value = pattern.sub(replace_var, value)
        values[key] = value
        os.environ.setdefault(key, value)


def resolve_data_root(raw_value: str) -> Path:
    path = Path(raw_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def business_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/New_York"))


def parse_date_to_utc(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(tzinfo=business_timezone()).astimezone(timezone.utc)


def parse_datetime_to_utc(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    dt_str = dt_str.replace("T", " ")
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=business_timezone()).astimezone(timezone.utc)


def get_mongo_client():
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError("Missing dependency pymongo. Run: python -m pip install -r requirements.txt") from exc

    mongo_uri = os.getenv("MONGODB_FLEET_URI")
    if mongo_uri:
        return MongoClient(mongo_uri)

    host = os.getenv("MONGODB_FLEET_HOST", "localhost")
    port = int(os.getenv("MONGODB_FLEET_PORT", "27018"))
    user = os.getenv("MONGODB_FLEET_ROOT_USER", "green_taxi_fleet_admin")
    password = os.getenv("MONGODB_FLEET_ROOT_PASSWORD", "change_me_fleet_root")
    connection_string = f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"
    return MongoClient(connection_string)


def flush_operations(collection, operations: list) -> tuple[int, int, int]:
    if not operations:
        return (0, 0, 0)
    result = collection.bulk_write(operations, ordered=False)
    return (result.matched_count, result.upserted_count, result.modified_count)


def seed_fleet() -> int:
    configure_console()
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero")
    load_env_file(REPO_ROOT / ".env")

    try:
        from pymongo import UpdateOne
    except ImportError as exc:
        raise RuntimeError("Missing dependency pymongo. Run: python -m pip install -r requirements.txt") from exc

    data_root = resolve_data_root(args.data_root)
    source_file_rel = "raw/synthetic/fleet/vehicles.jsonl"
    source_path = data_root / source_file_rel

    print(f"[*] Đang kiểm tra file nguồn: {source_path}")
    if not source_path.exists():
        print(f"[!] LỖI: Không tìm thấy file nguồn vehicles.jsonl tại {source_path}", file=sys.stderr)
        print("[!] Vui lòng tải data release từ Google Drive theo hướng dẫn.", file=sys.stderr)
        return 1

    source_checksum = calculate_sha256(source_path)
    print(f"[*] Checksum file nguồn (SHA-256): {source_checksum}")

    db_name = os.getenv("MONGODB_FLEET_DATABASE", "green_taxi_fleet")
    print(f"[*] Đang kết nối tới MongoDB database '{db_name}'...")
    try:
        client = get_mongo_client()
        db = client[db_name]
        # Kiểm tra kết nối bằng lệnh ping
        db.command("ping")
        print("[+] Kết nối MongoDB thành công!")
    except Exception as e:
        print(f"[!] LỖI: Không thể kết nối tới MongoDB: {e}", file=sys.stderr)
        return 1

    vehicles_col = db["vehicles"]
    vehicles_col.create_index("vehicle_id", unique=True)
    vehicles_col.create_index("plate_token", unique=True)
    metadata_col = db["seed_metadata"]
    metadata_col.create_index([("release_id", 1), ("source_file", 1)], unique=True)

    operations: list = []
    file_row_count = 0
    matched_total = 0
    upserted_total = 0
    modified_total = 0

    print("[*] Đang đọc và xử lý file vehicles.jsonl...")
    with source_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            file_row_count += 1
            record = json.loads(line)
            
            # Kiểm tra các trường bắt buộc
            if "vehicle_id" not in record or not record["vehicle_id"]:
                print(f"[!] Dòng {file_row_count} thiếu 'vehicle_id', bỏ qua.", file=sys.stderr)
                continue
            required_fields = [
                "vendor_id",
                "plate_token",
                "model_year",
                "vehicle_type",
                "service_start_date",
                "vehicle_status",
                "last_inspection_date",
                "source_updated_at",
            ]
            missing = [field for field in required_fields if record.get(field) in (None, "")]
            if missing:
                print(f"[!] Dòng {file_row_count} thiếu field bắt buộc: {', '.join(missing)}", file=sys.stderr)
                continue
            if record["vendor_id"] not in (0, 1, 2):
                print(f"[!] Dòng {file_row_count} có vendor_id không hợp lệ.", file=sys.stderr)
                continue
            if record["vehicle_type"] not in ("SEDAN", "HYBRID", "WAV"):
                print(f"[!] Dòng {file_row_count} có vehicle_type không hợp lệ.", file=sys.stderr)
                continue
            if record["vehicle_status"] not in ("ACTIVE", "MAINTENANCE", "RETIRED"):
                print(f"[!] Dòng {file_row_count} có vehicle_status không hợp lệ.", file=sys.stderr)
                continue

            try:
                record["service_start_date"] = parse_date_to_utc(record.get("service_start_date"))
                record["last_inspection_date"] = parse_date_to_utc(record.get("last_inspection_date"))
                record["source_updated_at"] = parse_datetime_to_utc(record.get("source_updated_at"))
            except Exception as ex:
                print(f"[!] Dòng {file_row_count} lỗi định dạng ngày/thời gian: {ex}", file=sys.stderr)
                continue

            operations.append(
                UpdateOne(
                    {"vehicle_id": record["vehicle_id"]},
                    {"$set": record},
                    upsert=True
                )
            )

            if len(operations) >= args.batch_size:
                matched, upserted, modified = flush_operations(vehicles_col, operations)
                matched_total += matched
                upserted_total += upserted
                modified_total += modified
                operations.clear()

    matched, upserted, modified = flush_operations(vehicles_col, operations)
    matched_total += matched
    upserted_total += upserted
    modified_total += modified

    db_row_count = vehicles_col.count_documents({})
    print(f"[+] Hoàn tất ghi dữ liệu vehicles.")
    print(f"    - Matched: {matched_total}")
    print(f"    - Upserted: {upserted_total}")
    print(f"    - Modified: {modified_total}")

    metadata_doc = {
        "release_id": args.release_id,
        "source_file": source_file_rel,
        "checksum": source_checksum,
        "row_count": file_row_count,
        "seeded_at": datetime.now(timezone.utc)
    }
    metadata_col.update_one(
        {"release_id": args.release_id, "source_file": source_file_rel},
        {"$set": metadata_doc},
        upsert=True
    )
    print(f"[+] Đã ghi seed metadata cho {source_file_rel}.")
    
    # 6. Row Count Reconciliation
    print("\n=== ROW COUNT RECONCILIATION ===")
    print(f"File nguồn: {source_file_rel}")
    print(f"  - Dòng đọc được từ file: {file_row_count}")
    print(f"  - Tổng số documents trong collection 'vehicles': {db_row_count}")
    
    if file_row_count == db_row_count:
        print("[+] ĐỐI SOÁT THÀNH CÔNG: Số dòng trong file khớp hoàn toàn với database.")
    else:
        print("[!] CẢNH BÁO ĐỐI SOÁT: Số dòng trong file và database KHÔNG khớp!")
        print("    (Điều này có thể bình thường nếu database đã chứa dữ liệu từ trước và file nguồn có duplicate vehicle_id)")
    print("=================================\n")

    client.close()
    return 0 if file_row_count == db_row_count else 1

if __name__ == "__main__":
    try:
        raise SystemExit(seed_fleet())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

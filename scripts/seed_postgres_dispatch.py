#!/usr/bin/env python3
"""Seed the PostgreSQL Dispatch source from the canonical data release."""

from __future__ import annotations

import argparse
import os
import re
import sys
import glob
import hashlib
import csv
from pathlib import Path


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
    parser = argparse.ArgumentParser(description="Seed PostgreSQL Dispatch source.")
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", "data"),
        help="Repository-relative or absolute data root. Default: DATA_ROOT or data.",
    )
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


def connect_postgres(**kwargs):
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("Missing dependency psycopg2-binary. Run: python -m pip install -r requirements.txt") from exc
    return psycopg2.connect(**kwargs)

def calculate_sha256(filepath):
    """Tính toán SHA-256 checksum của file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def count_file_rows(filepath, has_header=True):
    """Đếm số dòng dữ liệu thực tế trong file (trừ header)."""
    count = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count - 1 if has_header and count > 0 else count

def get_postgres_connection():
    """Tạo kết nối tới PostgreSQL Dispatch."""
    host = os.getenv("POSTGRES_DISPATCH_HOST", "localhost")
    port = int(os.getenv("POSTGRES_DISPATCH_PORT", "5433"))
    database = os.getenv("POSTGRES_DISPATCH_DATABASE", "green_taxi_dispatch")
    user = os.getenv("POSTGRES_DISPATCH_USER", "green_taxi_dispatch_app")
    password = os.getenv("POSTGRES_DISPATCH_PASSWORD", "change_me_dispatch")
    
    return connect_postgres(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )

def execute_sql_file(cursor, filepath):
    """Đọc và thực thi file SQL DDL."""
    print(f"[*] Đang thực thi DDL: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
        cursor.execute(sql)

def apply_ddls(conn):
    """Apply các file DDL khởi tạo database."""
    ddl_dir = REPO_ROOT / "sql" / "source_postgres_dispatch"
    ddl_files = [
        "00_create_schema.sql",
        "01_dispatch_tables.sql"
    ]
    
    with conn.cursor() as cursor:
        for ddl_file in ddl_files:
            path = ddl_dir / ddl_file
            if path.exists():
                execute_sql_file(cursor, path)
            else:
                print(f"[!] Cảnh báo: Không tìm thấy file DDL {path}")
    conn.commit()
    print("[+] Đã apply các file DDL thành công.")

def get_seeded_file_metadata(cursor, release_id, source_file_rel):
    """Lấy checksum và row_count của file đã seed từ database metadata."""
    cursor.execute(
        """
        SELECT checksum, row_count 
        FROM public.seed_metadata 
        WHERE release_id = %s AND source_file = %s
        """,
        (release_id, source_file_rel)
    )
    return cursor.fetchone()

def update_seed_metadata(cursor, release_id, source_file_rel, checksum, row_count):
    """Cập nhật lịch sử seed metadata."""
    cursor.execute(
        """
        INSERT INTO public.seed_metadata (release_id, source_file, checksum, row_count, seeded_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (release_id, source_file)
        DO UPDATE SET checksum = EXCLUDED.checksum, row_count = EXCLUDED.row_count, seeded_at = CURRENT_TIMESTAMP
        """,
        (release_id, source_file_rel, checksum, row_count)
    )

def seed_file_if_changed(
    conn,
    release_id,
    data_root,
    filepath,
    table_name,
    file_type="csv",
    delete_query=None,
    delete_args=None,
):
    """Seed file vào table sử dụng COPY nếu checksum thay đổi. Hỗ trợ idempotent bằng cách delete trước khi COPY."""
    abs_filepath = os.path.abspath(filepath)
    source_file_rel = os.path.relpath(abs_filepath, data_root)
    source_file_rel = source_file_rel.replace("\\", "/")
    
    # Tính checksum của file
    current_checksum = calculate_sha256(filepath)
    
    with conn.cursor() as cursor:
        # Check metadata xem đã seed chưa và checksum có khớp không
        meta = get_seeded_file_metadata(cursor, release_id, source_file_rel)
        if meta:
            seeded_checksum, seeded_rows = meta
            if seeded_checksum == current_checksum:
                print(f"[~] Bỏ qua file: {source_file_rel} (đã seed và checksum trùng khớp).")
                # Trả về số dòng đã seed trước đó
                return seeded_rows, False
            else:
                print(f"[*] File {source_file_rel} đã thay đổi checksum. Tiến hành seed lại...")
        else:
            print(f"[*] Phát hiện file mới: {source_file_rel}. Tiến hành seed...")
            
        if delete_query:
            print(f"[*] Đang thực thi dọn dẹp dữ liệu cũ trước khi nạp...")
            cursor.execute(delete_query, delete_args)
            
        # 3. Bulk COPY dữ liệu từ file vào database
        row_count = count_file_rows(filepath, has_header=True)
        print(f"[*] Đang nạp {row_count} dòng từ {source_file_rel} vào bảng {table_name}...")
        
        with open(filepath, "r", encoding="utf-8") as f:
            if file_type == "tsv":
                copy_sql = f"COPY {table_name} FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', HEADER true, NULL '')"
            else:
                copy_sql = f"COPY {table_name} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
            cursor.copy_expert(copy_sql, f)
            
        # 4. Ghi nhận seed metadata
        update_seed_metadata(cursor, release_id, source_file_rel, current_checksum, row_count)
        
    conn.commit()
    print(f"[+] Đã seed thành công file {source_file_rel} ({row_count} dòng).")
    return row_count, True

def get_tlc_source_file_from_csv(filepath):
    """Đọc dòng dữ liệu đầu tiên trong file trip assignment CSV để lấy giá trị cột source_file nghiệp vụ."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
        if first_row:
            return first_row.get("source_file")
    return None

def seed_dispatch() -> int:
    configure_console()
    args = parse_args()
    load_env_file(REPO_ROOT / ".env")
    data_root = resolve_data_root(args.data_root)
    
    # 2. Kiểm tra các file nguồn bắt buộc
    shifts_path = data_root / "raw" / "synthetic" / "dispatch" / "shifts.tsv"
    exceptions_path = data_root / "raw" / "synthetic" / "trip_assignment" / "assignment_exceptions.csv"
    assignment_glob = str(data_root / "raw" / "synthetic" / "trip_assignment" / "year=*" / "month=*" / "*.csv")
    
    mandatory_paths = [shifts_path, exceptions_path]
    for p in mandatory_paths:
        if not os.path.exists(p):
            print(f"[!] LỖI: Không tìm thấy file nguồn bắt buộc tại {p}", file=sys.stderr)
            print("[!] Vui lòng tải và giải nén data release từ Google Drive.", file=sys.stderr)
            return 1
            
    assignment_files = glob.glob(assignment_glob)
    if not assignment_files:
        print(f"[!] LỖI: Không tìm thấy file trip assignment CSV nào tại {assignment_glob}", file=sys.stderr)
        return 1
        
    # Sắp xếp các file theo thứ tự thời gian (tên file) để load tuần tự dễ quản lý
    assignment_files.sort()
    
    # 3. Kết nối PostgreSQL Dispatch
    print("[*] Đang kết nối tới PostgreSQL Dispatch database...")
    try:
        conn = get_postgres_connection()
        print("[+] Kết nối PostgreSQL thành công!")
    except Exception as e:
        print(f"[!] LỖI: Không thể kết nối tới PostgreSQL Dispatch: {e}", file=sys.stderr)
        return 1
        
    try:
        # 4. Áp dụng DDL để chắc chắn schema/tables tồn tại
        apply_ddls(conn)
        
        # 5. Seed shifts (Ca trực)
        # Vì shifts là snapshot toàn bộ, idempotent bằng cách TRUNCATE TABLE shifts (do DDL không chứa FK constraint nên truncate an toàn)
        seed_file_if_changed(
            conn,
            release_id=args.release_id,
            data_root=str(data_root),
            filepath=shifts_path,
            table_name="public.shifts",
            file_type="tsv",
            delete_query="TRUNCATE TABLE public.shifts;"
        )
        
        # 6. Seed assignment exceptions (Ngoại lệ phân công)
        # Idempotent bằng cách TRUNCATE TABLE exceptions trước khi load
        seed_file_if_changed(
            conn,
            release_id=args.release_id,
            data_root=str(data_root),
            filepath=exceptions_path,
            table_name="public.assignment_exceptions",
            file_type="csv",
            delete_query="TRUNCATE TABLE public.assignment_exceptions;"
        )
        
        # 7. Seed trip assignments (Phân công chuyến xe - Nguồn dữ liệu lớn)
        print(f"[*] Phát hiện {len(assignment_files)} file trip assignments để xử lý.")
        for filepath in assignment_files:
            # Tìm tlc source_file nghiệp vụ tương ứng trong file CSV này
            tlc_source_file = get_tlc_source_file_from_csv(filepath)
            if not tlc_source_file:
                print(f"[!] Cảnh báo: File {filepath} trống hoặc không đúng định dạng. Bỏ qua.")
                continue
                
            # Idempotent bằng cách xóa các trip assignments có source_file nghiệp vụ tương ứng trước khi nạp
            delete_query = "DELETE FROM public.trip_assignments WHERE source_file = %s;"
            delete_args = (tlc_source_file,)
            
            seed_file_if_changed(
                conn,
                release_id=args.release_id,
                data_root=str(data_root),
                filepath=filepath,
                table_name="public.trip_assignments",
                file_type="csv",
                delete_query=delete_query,
                delete_args=delete_args
            )
            
        # 8. Row Count Reconciliation
        print("\n=== ROW COUNT RECONCILIATION ===")
        with conn.cursor() as cursor:
            # Đếm dòng thực tế trong DB
            cursor.execute("SELECT COUNT(*) FROM public.shifts;")
            db_shifts_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM public.trip_assignments;")
            db_assignments_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM public.assignment_exceptions;")
            db_exceptions_count = cursor.fetchone()[0]
            
        # Tính tổng số dòng từ file nguồn tsv/csv
        file_shifts_count = count_file_rows(shifts_path, has_header=True)
        file_exceptions_count = count_file_rows(exceptions_path, has_header=True)
        
        file_assignments_count = 0
        for fpath in assignment_files:
            file_assignments_count += count_file_rows(fpath, has_header=True)
            
        print(f"1. Ca trực (shifts):")
        print(f"   - File nguồn: {file_shifts_count} dòng")
        print(f"   - Database  : {db_shifts_count} dòng")
        print(f"   - Trạng thái: {'[+] KHỚP' if file_shifts_count == db_shifts_count else '[!] LỆCH'}")
        
        print(f"2. Phân công chuyến xe (trip_assignments):")
        print(f"   - File nguồn: {file_assignments_count} dòng")
        print(f"   - Database  : {db_assignments_count} dòng")
        print(f"   - Trạng thái: {'[+] KHỚP' if file_assignments_count == db_assignments_count else '[!] LỆCH'}")
        
        print(f"3. Ngoại lệ phân công (assignment_exceptions):")
        print(f"   - File nguồn: {file_exceptions_count} dòng")
        print(f"   - Database  : {db_exceptions_count} dòng")
        print(f"   - Trạng thái: {'[+] KHỚP' if file_exceptions_count == db_exceptions_count else '[!] LỆCH'}")
        
        print("=================================\n")
        return 0 if (
            file_shifts_count == db_shifts_count
            and file_assignments_count == db_assignments_count
            and file_exceptions_count == db_exceptions_count
        ) else 1
        
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        raise SystemExit(seed_dispatch())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

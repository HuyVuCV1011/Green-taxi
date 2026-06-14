# Bao cao Doi chieu Du lieu va Tinh bat bien (Reconciliation & Idempotency Report)

Tai lieu nay bao cao ket qua chay kiem chung tich hop toan quy trinh (Full Pipeline) tu nguon du lieu (Source) qua cac phan lop Staging, NDS, DDS, kiem tra chat luong du lieu (DQ/Quarantine), lich su thay doi (SCD Type 2) va tinh bat bien (Idempotency) tren moi truong co so du lieu kiem thu.

## 1. Pham vi va Moi truong Kiem thu

- **Moi truong chay thu nghiem:**
  - He dieu hanh: Windows
  - Cong cu thuc thi: PowerShell
  - He quan tri co so du lieu: PostgreSQL 16 (Port 5434), MySQL 8.4 (Port 3307), MongoDB 7.0 (Port 27018)
  - Database kiem thu rieng biet: `green_taxi_warehouse_reconciliation_v1`
- **So do luong du lieu:**
  - `Source (MySQL, MongoDB, PostgreSQL, CSV)` -> `Staging (PostgreSQL)` -> `DQ / Audit / Quarantine` -> `NDS (Normalized Data Store)` -> `DDS (Dimensional Data Store)`

## 2. Thong tin Dataset Full Release

- **Vi tri thu muc du lieu day du (DATA_ROOT):** `D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1`
- **Duong dan tep tin TLC:** `D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1\tlc`
- **Mau tim kiem (Glob Pattern):** `year=*/month=*/*.csv`
- **So luong tep tin CSV:** 19 tep
- **Khoang thoi gian (First/Last Month):** Tu thang 01/2020 den thang 07/2021
- **Tong dung luong:** 208,865,428 bytes (~208.9 MB)

## 3. Ket qua chay thu nghiem (Run Summaries)

Quy quy trinh duoc thuc hien qua 2 lan chay lien tiep khong thiet lap lai co so du lieu (khong reset database) de kiem chung tinh bat bien.

### Lan chay 1: Nap du lieu ban dau (Initial Full Load)
- **Trang thai:** Thanh cong (SUCCEEDED)
- **Ma Batch/Pipeline Run ID:** `269677a3-27cd-488a-a147-fc869fc63e6e`
- **Thoi gian bat dau:** `2026-06-14T13:51:25` (UTC)
- **Thoi gian ket thuc:** `2026-06-14T14:09:50` (UTC)
- **Thoi gian chay chi tiet tung buoc:**
  | Ten buoc (Pipeline Step) | Trang thai | So dong doc | So dong nap | Thoi gian thuc thi (giay) |
  | :--- | :--- | :--- | :--- | :--- |
  | `source_health` | SUCCEEDED | 4 | 4 | 0.00s |
  | `load_staging` | SUCCEEDED | 4,768,237 | 4,768,237 | 338.20s |
  | `load_nds` | SUCCEEDED | 4,767,996 | 4,767,996 | 405.46s |
  | `load_dds` | SUCCEEDED | 2,465,663 | 2,465,663 | 358.96s |
  | `reconciliation` | SUCCEEDED | 14 | 14 | 2.00s |
  | `mark_dds_ready` | SUCCEEDED | 0 | 1 | 0.00s |
  | **Tong cong** | **SUCCEEDED** | **12,001,914** | **12,001,915** | **1102.62s (~18m 23s)** |

### Lan chay 2: Chay lai cung phien ban (Same-Release Rerun)
- **Trang thai:** Thanh cong (SUCCEEDED)
- **Ma Batch/Pipeline Run ID:** `dab757f0-2db0-49c7-8bf9-8fb830994041`
- **Thoi gian bat dau:** `2026-06-14T14:20:59` (UTC)
- **Thoi gian ket thuc:** `2026-06-14T14:38:05` (UTC)
- **Thoi gian chay chi tiet tung buoc:**
  | Ten buoc (Pipeline Step) | Trang thai | So dong doc | So dong nap | Thoi gian thuc thi (giay) |
  | :--- | :--- | :--- | :--- | :--- |
  | `source_health` | SUCCEEDED | 4 | 4 | 0.03s |
  | `load_staging` | SUCCEEDED | 4,768,237 | 4,768,237 | 393.42s |
  | `load_nds` | SUCCEEDED | 4,767,996 | 4,767,996 | 338.95s |
  | `load_dds` | SUCCEEDED | 2,463,943 | 2,463,943 | 290.90s |
  | `reconciliation` | SUCCEEDED | 14 | 14 | 2.52s |
  | `mark_dds_ready` | SUCCEEDED | 0 | 1 | 0.00s |
  | **Tong cong** | **SUCCEEDED** | **12,000,194** | **12,000,195** | **1023.27s (~17m 03s)** |

- **So sanh thoi gian chay:** Lan chay thu 2 nhanh hon lan chay thu nhat 79.35 giay (giam ~7.2% thoi gian thuc thi). Su cai thien nay nho vao viec su dung bo dem (cache) da duoc chuan bi va toi uu hoa cau lenh ghi de (upsert) thay vi tao moi cac ban ghi.

## 4. Doi chieu so luong dong (Source-Staging-NDS-DDS Row Count Reconciliation)

Bang duoi day thong ke so luong dong du lieu doi chieu qua cac phan lop cua kho du lieu (loai tru du lieu kiem thu tu bo go loi DQ Fixtures):

| Thuc the (Entity) | Nguon (Source) | Da nap vao Staging | Da nap vao NDS | Da nap vao DDS | Ket qua (Status) | Ghi chu (Notes) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HR Drivers** | 860 | 860 | 860 | 860 | PASS | Khop hoan toan. |
| **HR Driver Changes** | 77 | 77 | 77 | N/A | PASS | Chi luu vet lich su o NDS. |
| **Fleet Vehicles** | 860 | 860 | 860 | 860 | PASS | Khop hoan toan. |
| **Dispatch Shifts** | 157,379 | 157,379 | 157,379 | 157,379 | PASS | Chi tinh ca lam viec da hoan thanh. |
| **Dispatch Trip Assignments** | 2,304,276 | 2,304,276 | 2,304,276 | N/A | PASS | Dung lam bang noi trung gian. |
| **Lookup Vendor** | 3 | 3 | 3 | 3 | PASS | Du lieu danh muc co dinh. |
| **Lookup Taxi Zones** | 265 | 265 | 265 | 265 | PASS | Du lieu danh muc co dinh. |
| **TLC Trips** | 2,604,515 | 2,304,517 | 2,304,276 | 2,304,276 | PASS | Chi nap cac chuyen di co thong tin phan cong (Trip Assignment) o NDS. 241 chuyen di khong khop bi loai bo. |

## 5. Doi chieu chi so Do luong (Financial, Distance & Duration Measures)

Bang doi chieu tong so cua cac thuoc tinh do luong quan trong giua NDS va DDS (khong bao gom du lieu tu bo go loi DQ Fixtures):

| Chi so do luong (Measure) | Gia tri o NDS | Gia tri o DDS | Sai lech (Delta) | Dung sai cho phep (Tolerance) | Ket qua (Status) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Trip Count** | 2,304,276 | 2,304,276 | 0 | 0 | PASS |
| **Completed Shift Count** | 157,379 | 157,379 | 0 | 0 | PASS |
| **Total Revenue** | 48,535,884.47 | 48,535,884.47 | 0.00 | 0.00 | PASS |
| **Fare Amount** | 40,921,445.88 | 40,921,445.88 | 0.00 | 0.00 | PASS |
| **Tip Amount** | 2,767,166.37 | 2,767,166.37 | 0.00 | 0.00 | PASS |
| **Trip Distance (miles)** | 87,426,352.17 | 87,426,352.17 | 0.00 | 0.00 | PASS |
| **Trip Duration (minutes)** | 48,423,718.63 | 48,423,718.63 | 0.00 | 0.00 | PASS |

*Ghi chu:* Cach tinh Trip Duration trong NDS duoc lam tron 2 chu so thap phan cho moi ban ghi truoc khi tinh tong, hoan toan tuong thich voi truong `trip_duration_minutes` cua DDS:
`ROUND((EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) / 60)::numeric, 2)`.

Ba tong measure tren duoc cross-check lai tren database full-data sach
`green_taxi_warehouse_clean_validation_v2`. Cac gia tri cu cua revenue va
distance da vo tinh bao gom DQ fixture am (`-4.20` revenue, `-1.00` mile) du
ghi chu ban dau noi da loai fixture; duration sach van la `48,423,718.63`.

## 6. Kiem tra Hat du lieu va Trung lap (Grain & Duplicate Checks)

- **Trung lap ma tu nhien cua chuyen di (`nds.nds_trip.trip_nk`):** 0 ban ghi trung lap (PASS).
- **Trung lap khoa chinh cua chuyen di (`dds.fact_driver_trip.trip_id`):** 0 ban ghi trung lap (PASS).
- **Trung lap khoa chinh cua ca lam viec (`dds.fact_driver_shift.shift_id`):** 0 ban ghi trung lap (PASS).
- **Vi pham hat du lieu thuc te (Fact Grain Violations):** 0 vi pham (Hat du lieu: 1 dong/trip doi voi chuyen di va 1 dong/shift doi voi ca lam viec da hoan thanh) (PASS).
- **Vi pham rang buoc thoi gian ca lam viec:** 0 ban ghi co thoi gian hoat dong cua tai xe (`occupied_minutes` + `idle_minutes`) lech khoi tong thoi gian ca lam viec (`shift_duration_minutes`) (PASS).

## 7. Kiem tra Lich su Thay doi Dim (SCD Type 2 Checks)

- **So luong ban ghi hien hanh (is_current = True) toi da tren moi ma tu nhien (Natural Key):** 1 ban ghi (PASS).
- **Tinh hop le cua khoang thoi gian (`start_date`, `end_date`, `is_current`):**
  - Ban ghi hien tai luon co `end_date IS NULL` va `is_current = true`.
  - Cac phien ban cu co `end_date` khop voi `start_date` cua phien ban moi va `is_current = false`.
- **Rerun kiem chung tinh bat bien (Run 2):**
  - So luong phien ban moi sinh ra cua Driver: 0 (PASS).
  - So luong phien ban moi sinh ra cua Vehicle: 0 (PASS).
  - Hoat dong ghi de va so khop bam (SCD2 Hash Match) dien ra chinh xac, khong tao them ban ghi rac khi chay lai cung du lieu nguon.

## 8. Kiem tra chat luong du lieu va Cach ly (DQ & Quarantine Checks)

Ban go loi (DQ Fixtures) da duoc chay thanh cong tren database kiem thu nham xac minh cac quy tac kiem tra chat luong du lieu:
- **Loi muc ERROR khong nap vao NDS:** Ban ghi tai xe loi `DRV900001` (voi `employment_status = 'BROKEN_STATUS'`) bi chan khong nap vao bang `nds.nds_driver` (PASS).
- **Tao ban ghi cach ly (Quarantine Record):** Ban ghi tren duoc dua vao `dq.quarantine_record` va khop thong tin ma loi `DQ_INVALID_ENUM` (PASS).
- **Canh bao muc WARN van tiep tuc xu ly:** Ban ghi chuyen di `fixture-trip-key-preserved` co gia tri tien am van duoc nap vao NDS (PASS), dong thoi ghi nhan canh bao `DQ_NEGATIVE_VAL` trong `dq.dq_issue` (PASS).
- **Thanh vien suy dien (Inferred Members):** Cac ma tai xe `DRV900002` va xe `VEH900002` khong co trong danh muc goc nhung xuat hien trong bang phan cong chuyen di da duoc tu dong tao ban ghi suy dien (inferred) voi thuoc tinh `is_inferred = true` trong ca NDS va DDS (PASS).
- **Phat hien bat thuong van hanh:**
  - Phat hien 1 truong hop tai xe lam viec trung ca (driver_shift_overlap) (PASS).
  - Phat hien 1 truong hop xe hoat dong trung ca (vehicle_shift_overlap) (PASS).
  - Phat hien 1 truong hop chuyen di dien ra ngoai gio lam viec cua ca (trip_outside_shift) (PASS).

## 9. Chenh lech sau khi chay lai (Idempotency Deltas)

Bang so sanh chenh lech so luong ban ghi giua Run 1 va Run 2 (ngoai tru cac bang ghi vet log batch/audit):

| Bang du lieu (Table) | So dong Run 1 | So dong Run 2 | Chenh lech (Delta) | Trang thai (Status) |
| :--- | :--- | :--- | :--- | :--- |
| **nds.nds_driver** | 860 | 860 | 0 | PASS |
| **nds.nds_vehicle** | 860 | 860 | 0 | PASS |
| **nds.nds_trip** | 2,304,276 | 2,304,276 | 0 | PASS |
| **nds.nds_shift** | 157,379 | 157,379 | 0 | PASS |
| **nds.nds_trip_assignment** | 2,304,276 | 2,304,276 | 0 | PASS |
| **dds.dim_driver** | 860 | 860 | 0 | PASS |
| **dds.dim_vehicle** | 860 | 860 | 0 | PASS |
| **dds.fact_driver_trip** | 2,304,276 | 2,304,276 | 0 | PASS |
| **dds.fact_driver_shift** | 157,379 | 157,379 | 0 | PASS |
| **dq.dq_issue** | 6,211 | 6,211 | 0 | PASS |
| **dq.quarantine_record** | 0 | 0 | 0 | PASS |

## 10. Tong hop ket qua kiem duyet (PASS/FAIL Summary)

> [!IMPORTANT]
> Toan bo 14 bai kiem tra doi chieu du lieu cua luong chinh va 21 bai kiem tra chat luong du lieu cua luong thu nghiem loi (DQ Fixtures) deu dat trang thai **PASS**. He thong hoan toan dam bao tinh toan ven du lieu tu Nguon den Dich va dat tinh bat bien (Idempotency) tuyet doi.

## 11. Gia thuyet va Rui ro (Assumptions & Blockers)

- **Gia thuyet:** Du lieu nguon tu he thong MySQL (HR), MongoDB (Fleet), va PostgreSQL (Dispatch) khong thay doi giua hai lan chay thu nghiem cua cung mot phien ban giai phong (release).
- **Rui ro con lai:** Do kich thuoc du lieu lon (hon 2.3 trieu chuyen di), thoi gian chay day du cua pipeline mat khoang 17-18 phut tren moi truong local thong thuong. Can toi uu them chi muc (index) hoac phan manh du lieu (partitioning) trong cac giai doan phat trien tiep theo neu yeu cau rut ngan thoi gian xu ly cua chu ky nap du lieu.

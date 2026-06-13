# Source-to-Target Plan

## Driver

Physical source: MySQL `drivers` và `driver_changes`.

| Source field | NDS | DDS | Transformation |
|---|---|---|---|
| Driver HR `driver_id` | `nds_driver.driver_nk` | `dim_driver.driver_id` | Trim, uppercase |
| `vendor_id` | FK vendor | `vendor_key` | Lookup vendor |
| HR attributes | Current/history | SCD2 attributes | Effective-date merge |
| Change feed | Driver history | SCD2 new row | Upsert by effective time |

## Vehicle

Physical source: MongoDB collection `vehicles`.

| Source field | NDS | DDS | Transformation |
|---|---|---|---|
| Fleet `vehicle_id` | `nds_vehicle.vehicle_nk` | `dim_vehicle.vehicle_id` | Natural key |
| `vendor_id` | FK vendor | `vendor_key` | Lookup vendor |
| Type/model/status | Vehicle attributes | SCD2 attributes | Effective-date merge |

## Vendor

| Source field | NDS | DDS | Transformation |
|---|---|---|---|
| `vendor_id` | `nds_vendor.vendor_nk` | `dim_vendor.vendor_id` | Load 0, 1, 2 from lookup |
| `vendor_name` | Current attribute | `vendor_name` | SCD1/trim |

Vendor 0 là business member `Legacy / Unknown Pool`, khác với unknown surrogate
member kỹ thuật dùng khi source vendor key không thể map.

## Shift

Physical source: PostgreSQL source table `shifts`.

| Source field | NDS | DDS | Transformation |
|---|---|---|---|
| Dispatch `shift_id` | `nds_shift.shift_nk` | `dim_shift.shift_id` | Natural key |
| Driver/vehicle IDs | Surrogate FKs | Driver/vehicle keys | Effective-time lookup |
| Start/end | Timestamps | Date/time keys | Split date and time |
| Trip/occupied/idle | Validation fields | `fact_driver_shift` | Recomputed from trips |

## Trip and assignment

Physical sources: TLC monthly files và PostgreSQL source table
`trip_assignments`.

| Source field | NDS | DDS | Transformation |
|---|---|---|---|
| TLC source file + row | `nds_trip.source_key` | Degenerate source fields | Traceability |
| Assignment `trip_key` | Business key | `fact_driver_trip.trip_id` | Deduplicate |
| Pickup/dropoff | Timestamps | Date/time keys | Parse and lookup |
| PU/DO LocationID | Location FK | Role-playing location keys | Unknown when missing |
| Driver/vehicle/shift | FKs | Dimension keys | Effective-time lookup |
| Fare/tip/total | Numeric measures | Measures | Cast and DQ flags |
| Duration | Derived | `trip_duration_minutes` | Dropoff - pickup |
| Gap | Derived | `idle_before_trip_minutes` | Pickup - previous dropoff |

Business timestamps được parse theo `America/New_York`. Staging bảo toàn local
wall-clock value; mọi UTC technical timestamp được lưu riêng trong lineage.

## Reconciliation

- Release rows/checksums = seeded source rows/content hashes.
- Extracted source rows = staging accepted + staging rejected.
- Eligible TLC trips = assignments + assignment exceptions.
- Sum of DDS total amount = sum of accepted NDS trips.
- Sum of shift trip count = number of fact driver trips.
- Driver/vehicle overlap count = 0.
- Missing master count must reconcile with inferred-member log.

## Lineage mapping

| Source type | Required staging lineage |
|---|---|
| TLC/lookup file | Release ID, file path, checksum, row number |
| MySQL HR | Release ID, database/table, driver/event key, extract timestamp |
| MongoDB Fleet | Release ID, database/collection, vehicle key, document hash |
| PostgreSQL Dispatch | Release ID, schema/table, shift/trip key, extract timestamp |

`release_id` là bắt buộc trên mọi staging row, kể cả lookup và file sources.

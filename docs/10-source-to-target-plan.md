# Source-to-Target Plan

## Driver

| Source | NDS | DDS | Transformation |
|---|---|---|---|
| Driver HR `driver_id` | `nds_driver.driver_nk` | `dim_driver.driver_id` | Trim, uppercase |
| `vendor_id` | FK vendor | `vendor_key` | Lookup vendor |
| HR attributes | Current/history | SCD2 attributes | Effective-date merge |
| Change feed | Driver history | SCD2 new row | Upsert by effective time |

## Vehicle

| Source | NDS | DDS | Transformation |
|---|---|---|---|
| Fleet `vehicle_id` | `nds_vehicle.vehicle_nk` | `dim_vehicle.vehicle_id` | Natural key |
| `vendor_id` | FK vendor | `vendor_key` | Lookup vendor |
| Type/model/status | Vehicle attributes | SCD2 attributes | Effective-date merge |

## Shift

| Source | NDS | DDS | Transformation |
|---|---|---|---|
| Dispatch `shift_id` | `nds_shift.shift_nk` | `dim_shift.shift_id` | Natural key |
| Driver/vehicle IDs | Surrogate FKs | Driver/vehicle keys | Effective-time lookup |
| Start/end | Timestamps | Date/time keys | Split date and time |
| Trip/occupied/idle | Validation fields | `fact_driver_shift` | Recomputed from trips |

## Trip and assignment

| Source | NDS | DDS | Transformation |
|---|---|---|---|
| TLC source file + row | `nds_trip.source_key` | Degenerate source fields | Traceability |
| Assignment `trip_key` | Business key | `fact_driver_trip.trip_id` | Deduplicate |
| Pickup/dropoff | Timestamps | Date/time keys | Parse and lookup |
| PU/DO LocationID | Location FK | Role-playing location keys | Unknown when missing |
| Driver/vehicle/shift | FKs | Dimension keys | Effective-time lookup |
| Fare/tip/total | Numeric measures | Measures | Cast and DQ flags |
| Duration | Derived | `trip_duration_minutes` | Dropoff - pickup |
| Gap | Derived | `idle_before_trip_minutes` | Pickup - previous dropoff |

## Reconciliation

- Eligible TLC trips = assignments + assignment exceptions.
- Sum of DDS total amount = sum of accepted NDS trips.
- Sum of shift trip count = number of fact driver trips.
- Driver/vehicle overlap count = 0.
- Missing master count must reconcile with inferred-member log.


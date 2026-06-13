# Synthetic Data Generation Report

Generated from the local TLC Green Taxi CSV package using seed `20260613`.
This is the validated source for Google Drive release `green-taxi-full-v1`.

The CSV/JSONL/TSV outputs are canonical release artifacts. In the approved
physical architecture, they seed MySQL HR, MongoDB Fleet and PostgreSQL
Dispatch; TLC/lookup files remain batch file sources.

## Result

| Dataset | Records |
|---|---:|
| Driver HR master | 860 |
| Fleet vehicle master | 860 |
| Driver change events | 77 |
| Dispatch shifts | 157,379 |
| Trip assignments | 2,304,276 |
| Invalid-duration exceptions | 56 |
| Outside-source-period exceptions | 185 |

Assignments by vendor:

| Vendor | Trips |
|---|---:|
| Legacy/Unknown pool (0) | 777,155 |
| Vendor 1 | 263,291 |
| Vendor 2 | 1,263,830 |

## Validation

Full validation passed for:

- Driver and vehicle master references.
- Shift references and declared trip counts.
- Assignment-to-source trip keys.
- Trip containment within shifts.
- Driver trip temporal overlap.
- Vehicle trip temporal overlap.
- Driver shift temporal overlap.
- Vehicle shift temporal overlap.
- Shift occupied/idle time reconciliation.
- Vehicle inspection chronology.
- Vendor consistency.

Machine-readable details:

- `data/metadata/synthetic_generation_manifest.json`
- `data/metadata/synthetic_validation_report.json`

## Interpretation limit

The generated driver, vehicle, shift and assignment records are synthetic.
They demonstrate data integration and analytics techniques but do not describe
real NYC drivers or vehicles.

The generated workload averages approximately 14.6 trips per shift, which is
consistent with the case-study assumption of multi-trip operating shifts.

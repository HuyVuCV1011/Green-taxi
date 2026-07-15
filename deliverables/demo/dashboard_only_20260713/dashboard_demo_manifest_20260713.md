# Dashboard-Only Demo Video Manifest

## File

- Final video: `green_taxi_dashboard_demo_20260713.mp4`
- Duration: `00:01:00`
- Resolution: `1920x1080`
- Frame rate: `30 fps`
- File size: `1,219,004 bytes`
- Audio: none
- Captions: burned-in technical captions

## Scope

This recording covers only the Superset dashboard layer after the clean-slate
dashboard rebuild. It does not re-demo the full pipeline, Streamlit control
panel, source systems, warehouse loading, or full validation workflow.

## Coverage

- Executive pulse
- Demand patterns
- Workforce actions
- Trust & data health
- OLAP lab
- Exploratory models

## QA Notes

- Frames were captured from the live local Superset dashboard at
  `http://localhost:8088/superset/dashboard/green-taxi-driver-operations/`.
- Browser QA confirmed all six dashboard tabs rendered on a light background
  with no `Data error`, no `No results were returned`, and no stuck loading
  state before video assembly.
- Superset smoke test passed with 14 datasets, 109 metric instances, 35 charts
  and `benchmark_is_current = true`.
- Full automated test suite passed: 141 tests.

## Local Artifacts

- Frame list: `dashboard_only_frames.txt`
- Captions: `dashboard_only_captions.srt`
- Source frames: `frames/`
- Contact sheet: `dashboard_only_contact_sheet.jpg`

The final MP4 is intentionally not committed because project rules and
`.gitignore` exclude recording files from Git.

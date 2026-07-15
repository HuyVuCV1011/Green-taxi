# Final Technical Demo Video Manifest

> Historical full-system demo manifest. The Superset segment in this June 2026
> video predates the July 2026 clean-slate dashboard rebuild. Use
> `dashboard_only_20260713/dashboard_demo_manifest_20260713.md` for the current
> dashboard-only recording.

## File

- Final video: `green_taxi_technical_demo_final_20260630.mp4`
- Duration: `00:07:28`
- Resolution: `1920x1080`
- Frame rate: `30 fps`
- Audio: none
- Captions: burned-in Vietnamese technical captions

## Coverage

- Scope and audit evidence for the BI Driver Operations system.
- Source-to-warehouse architecture: TLC files, MySQL HR, MongoDB Fleet, PostgreSQL Dispatch, Staging, NDS 3NF, DDS Star, analytics views, Superset.
- Streamlit Control Panel: connection health, architecture diagram, schema expanders, row counts, pipeline controls, dry run, batch audit metadata, source explorer sample data.
- Superset dashboard: historical June 2026 dashboard segment; superseded by the
  July 2026 dashboard-only demo covering Executive pulse, Demand patterns,
  Workforce actions, Trust & data health, OLAP lab and Exploratory models.
- Final validation: pipeline reconciliation, Superset smoke test, and automated test suite status.

## QA Notes

- Final video was rendered from the combined raw capture with captions burned in through `ffmpeg/libass`.
- Verified by `ffprobe`: duration `448.000000`, resolution `1920x1080`, frame rate `30/1`.
- Review artifacts:
  - `final_captioned_contact_sheet.jpg`
  - `final_review_frames/`

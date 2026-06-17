# Documentation Map

Status: `CURRENT DOCUMENTATION ENTRY POINT`

Tài liệu được tổ chức theo chức năng thay vì theo timeline milestone. Mục tiêu là
giúp reviewer và thành viên mới tìm đúng nguồn sự thật, không phải đọc toàn bộ
lịch sử phát triển.

## Source Of Truth

| Chủ đề | Nguồn sự thật hiện hành |
|---|---|
| Setup end-to-end | [setup/local-reproducibility.md](setup/local-reproducibility.md) |
| Pipeline Control Panel | [setup/pipeline-control-panel.md](setup/pipeline-control-panel.md) |
| Kiến trúc runtime | [architecture/system-architecture.md](architecture/system-architecture.md) và [decisions/](decisions/) |
| Phạm vi nghiệp vụ | [context/scope.md](context/scope.md) |
| Source contracts | [contracts/source-data-contracts.md](contracts/source-data-contracts.md) |
| Source-to-target mapping | [contracts/source-to-target-mapping.md](contracts/source-to-target-mapping.md) |
| DQ rule execution | [warehouse/data-quality-etl-spec.md](warehouse/data-quality-etl-spec.md) |
| Warehouse physical model | [warehouse/physical-model.md](warehouse/physical-model.md) và `../sql/warehouse/` |
| DDS dictionary | [warehouse/dds-data-dictionary.md](warehouse/dds-data-dictionary.md) |
| Business questions | [analytics/business-questions.md](analytics/business-questions.md) |
| Semantic model | [analytics/semantic-contract.md](analytics/semantic-contract.md) |
| Metric formulas | [analytics/metric-catalog.md](analytics/metric-catalog.md) |
| OLAP plan | [analytics/olap-plan.md](analytics/olap-plan.md) |
| Data Mining plan | [analytics/data-mining-plan.md](analytics/data-mining-plan.md) |
| Superset operation | [analytics/superset-local-demo-runbook.md](analytics/superset-local-demo-runbook.md) |
| Full-release evidence | [evidence/full-release-reconciliation.md](evidence/full-release-reconciliation.md) và [evidence/integration-review.md](evidence/integration-review.md) |

Khi có mâu thuẫn, ưu tiên code/SQL/tests/runtime artifacts hiện tại, sau đó tới
source-of-truth table ở trên, ADR, evidence mới nhất, và cuối cùng là tài liệu
historical/archive.

## Reader Journeys

| Người đọc | Thứ tự đọc khuyến nghị |
|---|---|
| Thành viên mới | `setup/local-reproducibility` -> `architecture/system-architecture` -> `contracts/source-data-contracts` -> `analytics/superset-local-demo-runbook` |
| Data engineer | `architecture/system-architecture` -> `contracts/source-data-contracts` -> `contracts/source-to-target-mapping` -> `warehouse/physical-model` -> `warehouse/data-quality-etl-spec` -> `evidence/full-release-reconciliation` |
| BI/Analytics engineer | `context/scope` -> `analytics/business-questions` -> `analytics/semantic-contract` -> `analytics/metric-catalog` -> `analytics/olap-plan` -> `analytics/data-mining-plan` -> `analytics/superset-local-demo-runbook` |
| Reviewer/giảng viên | `README.md` ở root -> `context/project-context` -> `context/scope` -> `architecture/system-architecture` -> `evidence/integration-review` -> `analytics/superset-local-demo-runbook` |

## Current Structure

```text
docs/
|-- README.md
|-- setup/          # Local reproducibility, pipeline operation
|-- context/        # Project context, scope, feedback
|-- architecture/   # System architecture
|-- contracts/      # Source inventory, contracts, DQ overview, S2T mapping
|-- warehouse/      # Physical model, staging, DQ/ETL, NDS/DDS, DDS dictionary
|-- analytics/      # Business questions, semantic model, metrics, OLAP, Data Mining, Superset
|-- evidence/       # Validation and integration evidence
|-- planning/       # Implementation plan and work breakdown
|-- decisions/      # Accepted Architecture Decision Records
`-- meetings/       # Meeting notes placeholder
```

## Operational Documentation

| Tài liệu | Vai trò |
|---|---|
| [setup/local-reproducibility.md](setup/local-reproducibility.md) | Nguồn setup chính từ clone đến pipeline, Superset, smoke test và login |
| [setup/pipeline-control-panel.md](setup/pipeline-control-panel.md) | Vận hành PipelineRunner và Streamlit Control Panel |
| [analytics/superset-local-demo-runbook.md](analytics/superset-local-demo-runbook.md) | Superset setup, operation, backup, reset và demo |
| [../scripts/README.md](../scripts/README.md) | Tham chiếu CLI chi tiết cho từng script |

README ở root chỉ là landing page và Quick Start. Không thêm hướng dẫn vận hành
chi tiết mới vào README nếu nội dung đó thuộc setup/runbook.

## Architecture And Contracts

| Nhóm | Tài liệu |
|---|---|
| Context | [context/project-context.md](context/project-context.md), [context/scope.md](context/scope.md), [context/teacher-feedback.md](context/teacher-feedback.md) |
| Architecture | [architecture/system-architecture.md](architecture/system-architecture.md), [decisions/](decisions/) |
| Sources/contracts | [contracts/data-sources.md](contracts/data-sources.md), [contracts/source-data-contracts.md](contracts/source-data-contracts.md), [contracts/source-to-target-mapping.md](contracts/source-to-target-mapping.md) |
| Warehouse/DQ | [contracts/data-quality-overview.md](contracts/data-quality-overview.md), [warehouse/physical-model.md](warehouse/physical-model.md), [warehouse/staging-load.md](warehouse/staging-load.md), [warehouse/data-quality-etl-spec.md](warehouse/data-quality-etl-spec.md), [warehouse/nds-dds-implementation.md](warehouse/nds-dds-implementation.md), [warehouse/dds-data-dictionary.md](warehouse/dds-data-dictionary.md) |
| Analytics | [analytics/business-questions.md](analytics/business-questions.md), [analytics/semantic-contract.md](analytics/semantic-contract.md), [analytics/metric-catalog.md](analytics/metric-catalog.md), [analytics/requirements-traceability.md](analytics/requirements-traceability.md), [analytics/olap-plan.md](analytics/olap-plan.md), [analytics/data-mining-plan.md](analytics/data-mining-plan.md), [analytics/superset-local-demo-runbook.md](analytics/superset-local-demo-runbook.md) |

## Evidence And Planning

| Nhóm | Tài liệu |
|---|---|
| Evidence | [evidence/synthetic-generation-report.md](evidence/synthetic-generation-report.md), [evidence/full-release-reconciliation.md](evidence/full-release-reconciliation.md), [evidence/integration-review.md](evidence/integration-review.md) |
| Historical evidence | [evidence/superseded-tlc-missing-validation.md](evidence/superseded-tlc-missing-validation.md) |
| Planning/status | [planning/implementation-plan.md](planning/implementation-plan.md), [planning/work-breakdown.md](planning/work-breakdown.md) |

## Historical And Superseded Material

Proposal Superset/OLAP cũ đã được loại khỏi `docs/drafts/` để tránh bị dùng nhầm.
Tên artifact, phát hiện kỹ thuật còn giá trị và replacement links được giữ tại
[../archive/superset-and-olap-proposals.md](../archive/superset-and-olap-proposals.md).
Nội dung chi tiết còn trong Git history khi cần audit.

## Naming Rules

- File hiện hành dùng tên chức năng rõ nghĩa, dạng `kebab-case.md`, trong thư mục
  theo domain.
- Không thêm file mới dạng `NN-title.md` vào `docs/`; số thứ tự cũ chỉ còn trong
  Git history.
- Proposal, draft hoặc nội dung đã thay thế phải vào `archive/`, Git history hoặc
  có banner `SUPERSEDED`; không đặt cạnh operational docs như nguồn hiện hành.
- Mỗi chủ đề chỉ có một canonical source. File khác phải link sang thay vì copy
  công thức, command hoặc số liệu dài.
- Evidence phải ghi rõ date, environment, input, command/result và limitation.
- Runbook phải có prerequisites, steps, expected result và reset/troubleshooting.

## Terminology Rules

- Giữ nguyên thuật ngữ kỹ thuật chuẩn bằng tiếng Anh khi đó là tên khái niệm hoặc
  contract: `staging`, `source system`, `data contract`, `lineage`,
  `reconciliation`, `quarantine`, `metric`, `semantic model`, `runbook`,
  `dashboard`, `dataset`, `source-to-target mapping`, `idempotency`, `SCD Type 2`.
- Có thể giải thích tiếng Việt ngay sau thuật ngữ ở lần xuất hiện đầu tiên, ví dụ
  `reconciliation (đối soát số liệu)`.
- Không dịch schema, table, column, script, command, service, file path hoặc Docker
  service name.
- Dùng tiếng Việt cho bối cảnh nghiệp vụ, giải thích quyết định và kết luận báo
  cáo. Dùng tiếng Anh cho tên artifact kỹ thuật và heading của runbook/spec khi
  heading đó là thuật ngữ chuẩn.

## Documentation Quality Gate

Static checks cho Markdown nằm trong `tests/test_markdown_docs.py` và được chạy
cùng full suite:

```powershell
python -m unittest discover -s tests -v
```

Các checks này bảo vệ link tương đối, script references, stale numbered docs,
canonical-source conflicts và secret patterns trong tài liệu.

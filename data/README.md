# CS-2 Paper Benchmark

Current R2C development: [project documents](docs/project/README_项目文档总览.md) and [three-repository handoff](docs/DEVELOPMENT_HANDOFF.zh-CN.md). The 50-paper release and AI-authoritative policy below apply to the legacy five-dimension benchmark. New credibility cases are separate; paper_002 is not a completed human Gold case.

**中文用户请从这里开始：[`README.zh-CN.md`](README.zh-CN.md)（中文目录导航与阅读顺序）。**

Data-team workspace for building a small, evidence-backed benchmark for the
CS-2 Research Due Diligence project.

## Quickstart

Python 3.9+ and the packages in `requirements.txt` are required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make validate             # offline cross-file acceptance gates
make sql                  # regenerate sql/020_seed_all_structured_papers.sql
createdb cs2pilot && make db
```

`make pipeline` downloads and parses the manifest while preserving released scores.
It requires network access; model calls occur only with explicit `make score` or `--score`.
`make validate` is offline and does not require an API key.

## Current milestone

The 50-paper dataset is structured, AI-scored and exported to PostgreSQL. It
contains a balanced 30-paper ICLR 2024 calibration split and a temporal holdout
of 15 ICLR 2026 plus 5 ICLR 2025 proceedings papers. Under the current project
policy, evidence-bound AI assessments are authoritative; they are not admission
predictions and do not claim experimental reproduction. See
`data/manifests/release.json` for release status.

## Legacy five-dimension benchmark workflow

1. Select a public ICLR/OpenReview paper and record why it is useful.
2. Record stable identifiers and source URLs in `data/manifests/papers.csv`.
3. Preserve the exact paper version and its checksum; raw PDFs are not committed.
4. Parse the paper into metadata, sections, text chunks and paper elements.
5. AI assesses it using the locked five dimensions and paper-internal evidence.
6. Validate evidence links, scores, structure and database constraints.
7. Export the approved record for backend ingestion.

See `docs/workflow.md` for responsibilities and status definitions.

## Repository map

- `docs/`: data sources, workflow and field definitions
- `rubrics/`: versioned scoring rules and anchors
- `schemas/`: machine-readable JSON validation schemas
- `data/manifests/`: canonical paper and dataset membership lists
- `data/annotations/`: independent and adjudicated annotations
- `scripts/`: collection, validation and backend-export utilities
- `sql/`: database migrations and import views (added after the pilot format is stable)

The current design drafts are `docs/paper_structuring_spec.md`,
`rubrics/v0.1/scoring_guide.md` and `sql/001_initial_schema.sql`.

## Round-two credibility extension

The independent round-two contract, adapter and PostgreSQL extension are now
included. Start with `docs/第二轮_可信度核查接入与运行说明.md`. A real one-claim
vertical slice for `paper_001_v3` is committed; its scope is explicitly
incomplete and the draft rubric intentionally emits no official score until
weights and thresholds are approved.

## Privacy and storage

Do not commit user-uploaded PDFs, API keys or private material. Public-paper
PDFs are referenced by URL, version and SHA-256 checksum and should be stored
outside Git when downloaded.

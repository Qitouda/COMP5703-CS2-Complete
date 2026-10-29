# CS-2 Backend

**v1.0 Standard Edition** — application version `1.0.0`, release tag `v1.0`. API schema and rubric versions remain independent of the application release. See the [frontend integration guide](docs/FRONTEND_API.zh-CN.md).

Development entry point: `main`, including the merged history and PDF-evidence improvements. [Current handoff](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/main/docs/DEVELOPMENT_HANDOFF.zh-CN.md) and [project documents](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/main/docs/project/README_%E9%A1%B9%E7%9B%AE%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md). The fixed `r2c-sync-2026-10-01` tag preserves the original snapshot. The legacy five-dimension Assessment v0.4 remains available. The independent `/v1/credibility/assessments` API now generates live claims, comparison evidence and judgments with a selected real model; see [live claim analysis](docs/credibility/live-claims.md). The API now supports deterministic trial scores with `rubric_version="0.2-provisional-complete"`; explicit `0.1-draft` requests stay unscored. See [provisional scoring](docs/credibility/provisional-scoring.md).

**中文用户请从这里开始：[`README.zh-CN.md`](README.zh-CN.md)（中文说明与导航）。**

The local BE-07 implementation adds durable credibility tasks, checkpoints, evidence snapshots,
isolated checks and bounded model tool use. See [recovery and offline replay](docs/credibility/durable-evidence.md)
and [external evidence tools](docs/credibility/external-tools.md). Request
`schema_version="credibility-0.5.0-draft"` (also the default when omitted) for coverage,
execution, external review and `reference_verification_summary`: the verification rate
among extracted references and linked unresolved reasons. The code branch now preserves
cited commits/subdirectories, records source-bound implementation/setup evidence, and
collects implementation/discussions after a model confirms a candidate repository.
See [code evidence and usability checks](docs/credibility/code-usability.md) for
the historical `code-checks-2.3-implementation-shells` / `credibility-external-code-1.7` acceptance: placeholder
package files are excluded, real modules are sampled, and incomplete payloads retain partial status.
The latest historical six runs completed their bounded plans, selecting five original 1.7 runs and one
independent LoRA retry; both earlier six-paper batches retain their 5/6 completion histories.
See the manual for partial discussion coverage and the remaining execution/follow-up gaps.
The current 0.5 implementation adds bounded [external code discovery](docs/credibility/code-discovery.md)
with checker 2.5, review Prompt 1.12, discovery 1.5 and provider adapter 1.2.
The latest ten-paper fresh run has six completed and four partial results; all ten source audits passed.
Object-Centric now has verified implementation evidence (trial code score 7); its extra page truncation and candidate cap remain partial.
CoT's registered-span citations validate (score 4), while a candidate Fetch provider 404 retains partial status.
LoRA retains partial after two 16,000-token output truncations; Limits retains partial at the shared reading cap.
DataMIL's official implementation and follow-up discussion checks completed (score 7).
Automated regressions and Ruff passed; the manual records the full validation history and remaining coverage gaps.
Earlier runs and failures remain archived.
The new `code_discovery` summary keeps search candidates separate from verified repository evidence.
A completed bounded plan can still have `scope_complete=false`; no repository code is executed.
Reference checks supplement Crossref with bounded arXiv and official publication lookups;
see [automatic reference verification](docs/credibility/reference-auto.md).
Scoring remains the selected trial rubric; live technical acceptance and human review
are tracked separately from implementation tests.

| Explicit credibility API version | Response |
|---|---|
| `credibility-0.1.0-draft` | Original shape; no coverage/execution/external review/reference summary |
| `credibility-0.2.0-draft` | Coverage/execution/external review; no reference summary |
| `credibility-0.3.0-draft` | Adds the reference verification summary |
| `credibility-0.4.0-draft` | Same public fields as 0.3; bounded code-plan completion and follow-up semantics |
| `credibility-0.5.0-draft` (default) | Adds `code_discovery` with search candidates, provenance and bounded discovery status |

These transport versions do not change `0.2-provisional-complete` numerical scoring.

FastAPI + Pydantic backend for the CS-2 Research Due Diligence product. It takes
an arXiv link or an uploaded PDF and returns a report that conforms to the
Unified Field Contract v0.4. Delivery uses GPT by default; offline tests use the built-in fixture model.
The model transport is separate from evidence validation and scoring.

## Real-model quick start

Put a valid `OPENAI_API_KEY` in the existing local `.env`, select
`OPENAI_MODEL=gpt-6.1-sol` and `OPENAI_REASONING_EFFORT=medium`, then run:

```bash
make run-openai
```

The service uses `openai` with the generic parser and incurs real model usage.
Verify `/health` and `/v1/models` before submitting a paper. Claude and Gemini
use their configured compatible endpoints and remain unavailable until their
sample validation is explicitly enabled. Fixture mode remains available offline.

The checked-in [environment template](.env.example) mirrors the local runtime as
of 2026-10-30: generic parsing, a 300-second model timeout, one credibility worker,
Claude/Gemini SSE, and Gemini 3.1 Flash-Lite with minimal reasoning and zero
thinking headroom. Keys are empty and storage paths are relative to `backend/`.
See [runtime configuration](docs/RUNTIME_CONFIGURATION.md) for endpoints,
the capacity-aware launcher and storage migration.

## Fixture quick start

```bash
pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
LLM_PROVIDER=fixture PARSER_PROVIDER=stub python3 -m uvicorn app.main:app --reload --port 8000
```

The explicit environment overrides select the no-cost fixture/stub demo.
`make run` selects GPT with generic parsing and requires a real key. Never
overwrite an existing `.env`, because it may contain the local API key.
Open http://localhost:8000/docs.
Virtualenv details and verification steps:
[`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md) (Chinese).

## Commands

```bash
make run         # dev server (SQLite + in-process background tasks)
make run-real    # force GPT + paper_001 benchmark
make run-openai  # generic parser + OpenAI GPT
make test        # test suite
make lint        # ruff
make smoke       # end-to-end run that asserts the contract's hard rules
make docker-up   # full stack (Postgres / Redis / Celery / GROBID)
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, current schema / rubric versions and providers |
| GET | `/v1/venues` | venue options |
| GET | `/v1/models` | model options |
| POST | `/v1/uploads` | PDF upload, returns `upload_id` |
| POST | `/v1/assessments` | create an assessment, returns `assessment_id` (202) |
| GET | `/v1/assessments` | search and sort locally saved reviews |
| GET | `/v1/assessments/{id}` | poll status and result |
| POST | `/v1/credibility/assessments` | create a live claim-analysis job (202) |
| GET | `/v1/credibility/assessments/{id}` | poll independent credibility checks |
| POST | `/internal/validate-report` | internal tool: validate one model output |

Scoring is a long-running job: creation returns immediately and the frontend
polls for status. Do not expect a synchronous report.

## Run modes

Four switches, all in `.env`, no code changes:

- `LLM_PROVIDER`: default frontend selection: `fixture`, `openai`, `anthropic`, or `google`
- `PARSER_PROVIDER`: `stub`, `benchmark` (paper_001 only), `generic`, or `grobid`
- `TASK_RUNNER`: `inline` (FastAPI background tasks) or `celery`
- `CREDIBILITY_PARSE_SOURCE`: `live` (default; credibility checks parse the input with the backend parser, like the five-dimension flow) or `benchmark` (prefer the data team's `data/data/parsed`, for regression and historical replays only)

## Code map

- `app/schemas/`: Pydantic types and constraints for Field Contract v0.4.
- `app/validation/`: evidence verification, dimension degradation,
  reproducibility cross-checks, overall-score calculation.
- `app/llm/`: model-client interface, retry policy and repair pass.
- `app/parsing/`: parsed-document structures, the location-anchor convention,
  and the loader for the data team's benchmark output.
- `app/pipeline/orchestrator.py`: end-to-end flow from input to report.
- `app/storage/`, `app/tracking/`: tables and model-call run logs.
- `docs/OPEN_QUESTIONS.md`: cross-team items the contract does not settle yet.

The data team's parsed output plugs in directly — no GROBID needed:
`load_parsed_document(".../data/parsed/paper_001/v3").build_index()` feeds
straight into `validate_report_payload(source_index=...)`. Shapes follow their
`paper_structuring_spec.md` v0.1; if they change a shape,
`tests/test_parsing_benchmark.py` turns red first.

## Running the real model

GPT is the delivery default. Set `OPENAI_API_KEY` in `.env`, keep
`LLM_PROVIDER=openai`, and run `make run-openai`
(or `make run`, which also selects GPT with the generic parser).
The current model is `gpt-6.1-sol` with `OPENAI_REASONING_EFFORT=medium`.
The legacy provider is disabled and is not required for any current workflow.

`OPENAI_BASE_URL` defaults to the official API. An authorized compatible relay
can be configured with its own `/v1` base URL and credential. JSON reports,
function calls and reasoning state use the Responses API; compatible relays must
support those features. Every report records the actual returned model version.

Claude and Gemini use `ANTHROPIC_*` and `GEMINI_*` settings through
`app/llm/compatible.py`. Configure their keys and endpoints, verify a minimal
sample, and only then set `CLAUDE_ENABLED=true` or `GEMINI_ENABLED=true`.
Their search queries use the configured OpenAI search transport; public pages
are fetched directly. Freeze or record this shared search configuration when
comparing reasoning models.

The code review agent requests 16,000 output tokens by default. Set
`CREDIBILITY_CODE_MAX_OUTPUT_TOKENS` between 1,000 and 65,536 to change the
application budget. Generated output, reasoning and tool usage must all be
included when estimating the provider's actual charges.

### Locked 50-paper benchmark

The runner defaults to GPT and retains the locked full structured text and the
common validation, repair and scoring pipeline. Reference scores remain outside
all model prompts. A preflight without `--execute` performs no model requests:

```bash
.venv/bin/python scripts/run_full_benchmark.py --provider openai \
  --model gpt-6.1-sol --reasoning-effort medium --output /absolute/new-run-directory
```

Add `--papers paper_001 paper_002 --execute --workers 2` for a fresh two-paper
pilot, then run the same directory without `--papers` to finish all 50 papers.
Only completed checkpoints from that same configuration can be resumed. Model
outputs from other run directories cannot be replayed. Authentication and billing
quota failures stop the whole batch without retrying the rejected request;
ordinary rate limits retain bounded retries and stop the batch if those retries
are exhausted. At most `--workers` papers are active, unstarted papers stay
pending, and `run_record.json` records `stopped_reason` (exit status 2). `--provider anthropic`
and `--provider google` use the corresponding configured compatible clients.

Each request attempt records usage, including usage returned with invalid or
truncated output. `comparison.json`, two CSVs and `run_record.json` include the
provider, precise model, reasoning setting, endpoint, attempts and token totals.
Relay token prices are recorded in `platform_unit`, not assumed to be RMB or USD;
use `--price-*` overrides with the verified price source for other models/routes.

## Conventions

Overall Score, rating and `is_provisional` are always recomputed by the backend
per contract §10.5; model-returned values are discarded. `dimensions` always has
5 entries and `reproducibility_checklist` always has 6; gaps are filled with
`uncertain` / `unable_to_verify`.

Every evidence location must be traceable: body text cites `chunk_id`s, tables
and figures cite parsed element labels. Anything that fails the lookup gets its
confidence lowered, out-of-range page numbers become `null`, and the parser's
own `location_confidence` is a ceiling. No invented page numbers or quotes.

Field changes go to the Unified Field Contract first (with a version bump),
then to `app/schemas/`.

## Related repositories

- Frontend: `Qitouda/COMP5703-CS2-Frontend`
- Data-team benchmark: `eden-eden-new/cs2-paper-benchmark`
- Backend (this repo): `kanekogaido/cs2-capstone--backend`

## Privacy

Never commit `.env`, API keys, paper PDFs or any user-uploaded content. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the collaboration rules.

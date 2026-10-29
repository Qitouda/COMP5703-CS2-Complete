> Current response fixtures are the fresh GPT-6.1 Sol / medium B cases documented in [GPT fixture provenance](GPT_TEST_FIXTURES.md). The earlier captured-fixture paths and dated prototype behaviours below are historical; the original captures are preserved in their experiment output directories. The current report distinguishes completed checks with unresolved evidence from execution failures.

# Credibility frontend prototype

The prototype implements an independent frontend flow against the `credibility-0.5.0-draft` contract (backend v1.0, rubric `0.2-provisional-complete`). Since the v1.3 interface reset it is the app's home at `/#check` (`/#credibility` still works); **Paper scoring** and **Reports** are the other two sections of the same top bar.

Visual direction: retain the existing warm paper, ink typography and teal actions; use three check rows and a source inspector instead of another scoring dashboard. Content moves from paper input to check progress, overall status and alerts, then item evidence and coverage. Progress, tab changes and the evidence drawer provide restrained feedback, with reduced-motion support.

Run from the frontend repository:

```sh
npm ci
VITE_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

With `VITE_API_MODE=mock`, open `http://127.0.0.1:5174/#credibility`. This mode uses explicit synthetic fixtures and performs no network analysis, PDF upload, parsing or model call. The selected scenario determines the result. It does not advertise availability of the proposed backend endpoints or fall back to a synthetic report after a live failure.

## Live backend

With `VITE_API_MODE=http` (the default), `/#credibility` uses `httpCredibilityApi` against the backend `POST/GET /v1/credibility/assessments` endpoints. Since backend v1.0 (2026-10-21) the request carries `credibility-0.5.0-draft`, rubric `0.2-provisional-complete` (trial scores) and a real `model_id` from `/v1/models`; `not_called` is accepted only by a fixture backend. The paragraph below describes the 0.1 behaviour and is kept for history. The scenario selector is hidden, PDFs are uploaded through `/v1/uploads`, and the original-PDF link is built from the returned `paper.arxiv_id`. The page shows whatever the backend returns: for arXiv `2310.01798v1` that is one prepared claim with both ends located on physical pages 1 and 5, human review pending, and an empty overall score under the draft rubric. Reference verification now queries Crossref for numbered reference lists; the References tab shows extracted, checked, matched, metadata-conflict, unverified and not-checked counts as returned. paper_002 uses author-year references, so its reference check reports an extraction failure; arXiv `2312.00752v1` (paper_004) exercises the live lookup. The code check (backend branch `haichen-stage2`, not yet in `main`) queries GitHub without a token, so each run spends up to 40 of the 60 hourly requests; arXiv `2307.08122v3` (paper_001) finds a confirmed repository and one shared-repository discussion. The repository card links the GitHub page derived from the queried API URL, and discussions show relevance, resolution, independence and whether they count toward the score. `src/test/fixtures/credibility-paper-001-code.json` is that captured response. `src/test/fixtures/credibility-paper-002.json` is a captured backend response used by the adapter and workspace tests.

```sh
VITE_API_MODE=http npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

## Review scenarios

| Scenario | Product behavior to review |
|---|---|
| First claim | Prepared paper_002 candidate; real source pages 1 and 5, AI-assisted confirmation, incomplete scope, no Gold or overall score |
| Core contradiction | Synthetic critical finding with both evidence ends; 0/10/9 aggregate 6.3 retains major alerts |
| External lookup failure | Synthetic failed source; confirmed findings and other scores retained, overall score/category empty |
| Code not applicable | Evidence explains the exclusion; not confused with failed or unchecked code |
| Parse failure | Task error with no paper risk category or fabricated score |

PDF selection previews only the input path. No file bytes leave the browser. The prepared first case accepts only the locked `2310.01798v1` arXiv source; other inputs use synthetic scenarios and are never presented as their parsed contents. External `example.invalid` sources are explicitly unavailable example links. Paper-only evidence can open the genuine locked PDF at its physical page.

## Backend handoff

- `src/types/credibility.ts` defines separate request, job, report, source, evidence and check types.
- `CredibilityApi` separates create and get operations. `mockCredibilityApi` advances job snapshots through the contract stages.
- The UI reads server-provided scores, categories, alerts and calculation membership; it does not recompute missing scores or remove failed dimensions.
- Main contract invariants and fixture cross-references are exercised in tests; that validates prototype behavior and does not measure an Agent's accuracy.
- Next integration requires the implemented backend schema/validator and API, real model availability and PDF-upload IDs, real polling/error handling, source verification and the old-flow regression. Mock runs cannot satisfy R2C-FE-03.

This prototype is included in the development `main` alongside the merged history flow. It was developed on `feat/credibility-prototype` after the fixed `r2c-sync-2026-10-01` handoff; that tag still preserves the original snapshot. Contract/Rubric approval, independent case review and real backend integration remain pending.

## Current validation and next step

The frontend suite passes 55 tests, with lint and the TypeScript/production build passing. Browser review covers desktop (1280 px), narrow screens (375 px), first-case progress and null overall, the physical-page-5 evidence drawer, and critical alerts beside the 6.3 synthetic aggregate. Creation locks its inputs while pending; cancellation discards late responses.

Product review should confirm the input/progress/report flow, the difference between unchecked, failed and not applicable, and whether evidence plus its conditions are easy to find. Then frontend and backend should confirm the draft fields and implement the real adapter. Data work can continue with more candidate cases and recorded reviews in parallel. This advances R2C-FE-01/02 prototype work; R2C-FE-03 real integration remains pending.

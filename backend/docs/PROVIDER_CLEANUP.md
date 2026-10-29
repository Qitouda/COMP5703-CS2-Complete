# Provider cleanup and validation provenance

This cleanup is isolated from the experiment checkout. The A/B/C results retain
backend `5a7772c` and frontend `7ba8d32`; tests on this cleanup revision do not
represent a rerun of those model assessments. No credentials or local `.env`
are copied into this worktree, and no model requests are required for validation.

## Runtime changes

- The retired client, configuration fields, product model option and routing
  branch are removed. Fixture mode remains the offline test default; delivery
  startup uses GPT. Claude/Gemini keep their existing explicit enablement gates.
- Typed, content-free protocol diagnostics are shared by the compatible clients.
  Bounded discovery uses a provider-neutral base with no implicit credential or
  endpoints. OpenAI supplies web search and SSRF-checked public page reads.
- The actual retired host remains in `config/network-denylist.json`, including
  package builds. Generic transport code checks that file; no split or concealed
  hostname is used to evade the source scan. Initial model endpoints, discovery
  targets and redirect hops are checked before transport.
- Snapshots and observers receive recursive audit copies with opaque reasoning,
  signatures and encrypted content removed. The in-memory assistant/tool history
  stays complete for the next provider request. Numeric token usage is retained.
- The fresh code verifier and offline auditor use current model identities,
  OpenAI web-search POSTs and direct page GETs. A non-wire request extension marks
  discovery fetches for audit accounting; model payloads and scoring are unchanged.

## Test migration

The previous suite had 2,232 cases. Seven retired-provider-only cases were removed:
four thinking/temperature payload combinations, its one truncated-JSON client
case, and two provider-specific 65,536/25,000 claim-budget cases. Truncation,
malformed envelopes, tool-call rejection, failed-attempt usage, SSRF, redirects,
quote/source closure, checkpoint recovery and report contracts remain covered
through GPT, compatible clients or explicit offline fixtures.

Fifteen cases were added in total, including the review fixes: a two-turn nested tool-signature audit/round-trip check,
a fresh-verifier forbidden-redirect check, and two configured model-endpoint
checks against the real denylist, and acceptance of a nullable empty tool list
in a valid compatible final response. Review regressions cover seven legitimate/unsafe GET URL cases,
two-round reference-agent signature redaction, and two offline wire-audit refusals.
The resulting suite has 2,240 cases.

Full validation may set `CS2_TEST_WORKSPACE_ROOT` to the original workspace for
read-only access to the frozen external provenance assets. The sibling data tree
is still checked independently and every recorded hash must match; an existing
but changed artifact cannot be skipped. This is offline fixture verification,
not reuse of historical model conclusions in a new assessment.

Seven historical documents only receive a status header, with their original
body bytes preserved. Current guides are updated; dated result sections retain
their original model identities, counts and failure records.

## Independent review corrections

Normal GitHub and OpenReview GET query strings pass the production URL/credential
rules; model/search POSTs still require an exact configured endpoint with no query
or credentials. The offline auditor applies the same fetch URL rules and checks
search POSTs against the runner's recorded allowed endpoints. Redirect denylist
checks remain unchanged. Reference-agent snapshots now use the same recursive
projection as code agents, with actual two-round tool-history preservation tested.

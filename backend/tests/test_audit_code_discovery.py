"""Real serialization/hashing with synthetic HTTP doubles; never live sources."""
from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from app.config import get_settings
from app.credibility.code_checks import check_code
from app.credibility.context import CheckContext
from app.credibility.models import (
    CredibilityCodeDiscovery,
    CredibilityEvidence,
    CredibilityExternalSource,
    CredibilityModelCall,
)
from app.credibility.rubric import load_credibility_rubric
from app.credibility.snapshots import SnapshotStore, capture_snapshot
from app.parsing.grobid import StubParser
from scripts import audit_code_discovery as auditor
from scripts import verify_code_usability as verifier

CHAT = "https://model.example/v1/chat/completions"
SEARCH_ENDPOINT = "https://model.example/v1/responses"
FETCH_ENDPOINT = "https://openreview.net/forum?id=offline-paper"
URL = "https://github.com/example/reading-list"
TEXT = "Reading list\n- Offline discovery paper (2503.12345)."


@pytest.mark.parametrize("method,url,expected", [
    ("POST", CHAT, "openai"),
    ("POST", SEARCH_ENDPOINT, "openai_search"),
    ("GET", FETCH_ENDPOINT, "openai_fetch"),
    ("POST", SEARCH_ENDPOINT + "?query=unapproved", None),
    ("POST", FETCH_ENDPOINT + "/other", None),
    ("POST", "https://model.example.evil.test/v1/responses", None),
    ("POST", "https://user:secret@model.example/v1/responses", None),
    ("POST", "http://model.example/v1/responses", None),
    ("POST", "https://example.org/", None),
    ("GET", "https://api.github.com/repos/example/paper", "github_api"),
    ("GET", "https://api.github.com/repos/example/paper/issues?state=all", "github_api"),
    ("GET", "https://api.github.com/repos/example/paper/git/trees/HEAD?recursive=1", "github_api"),
    ("GET", "https://openreview.net/forum?id=offline-paper", "public_page"),
    ("GET", "https://openreview.net/forum?id=offline-paper&access_token=secret", None),
    ("GET", "https://api.github.com/repos/example/paper/issues?state=all&api_key=secret", None),
    ("GET", "https://openreview.net/forum?id=offline-paper&redirect=https%3A%2F%2Fx.org%2F%3Ftoken%3Dsecret", None),
    ("GET", "https://127.0.0.1/issues?state=all", None),
])
def test_verifier_only_adds_exact_search_fetch_posts(method, url, expected):
    request = httpx.Request(method, url, json={"tools": [{"type": "web_search"}]},
                            extensions={"code_discovery_operation": "fetch"} if expected == "openai_fetch" else {})
    assert verifier._allowed_provider(request, CHAT, search_endpoint=SEARCH_ENDPOINT) == expected


def _observed_result(ctx):
    result = check_code(ctx)
    values = [
        ("qsource1", "metadata", SEARCH_ENDPOINT, {
            "operation": "search", "query": "exact title", "hits": [{"url": URL, "title": "Reading list"}],
        }),
        ("qsource2", "metadata", SEARCH_ENDPOINT, {"operation": "search", "query": "paper id", "hits": []}),
        ("page", "project_page", URL, {"operation": "fetch", "url": URL, "body": TEXT, "text": TEXT}),
    ]
    for sid, kind, url, data in values:
        ref = capture_snapshot(kind=kind, normalized_json=data, requested_url=url,
            fetch_status="ok", http_status=200, retrieved_at=ctx.generated_at,
            metadata={"source_id": sid, "source_url": url})
        result.sources.append(CredibilityExternalSource(source_id=sid, kind=kind, url=url,
            fetch_status="ok", http_status=200, retrieved_at=ctx.generated_at, observed_at=ctx.generated_at,
            is_cached=False, snapshot_ref=ref, association_reason="Synthetic acceptance fixture."))
    result.evidence.append(CredibilityEvidence(evidence_id="page_quote", origin="external", mode="quote",
        excerpt=TEXT, source_id="page", paper_locator=None, location_confidence="high"))
    result.discovery = CredibilityCodeDiscovery.model_validate({
        "status": "completed", "reason": "Two bounded searches; actual resource is a reading list.",
        "queries": [
            {"query_id": "q1", "provider": "openai", "query": "exact title", "status": "completed",
             "result_count": 1, "source_ids": ["qsource1"]},
            {"query_id": "q2", "provider": "openai", "query": "paper id", "status": "completed",
             "result_count": 0, "source_ids": ["qsource2"]},
        ],
        "candidates": [{"candidate_id": "candidate1", "url": URL, "resource_kind": "reading_list",
            "status": "rejected", "query_ids": ["q1"], "source_ids": ["qsource1", "page"],
            "evidence_ids": ["page_quote"], "reason": "No implementation claim."}],
        "budget": {"max_queries": 3, "queries_used": 2, "max_candidates": 20, "candidates_inspected": 1,
            "max_source_reads": 7, "source_reads_used": 3, "max_model_rounds": 4, "model_rounds_used": 1,
            "max_tool_calls": 8, "tool_calls_used": 3},
    })
    input_ref = capture_snapshot(kind="code_discovery_model_input", normalized_json={"messages": []})
    attempt = {"round": 1, "input_snapshot_ref": input_ref, "status": "started"}
    attempt["attempt_snapshot_ref"] = capture_snapshot(kind="code_discovery_model_attempt",
        normalized_json=attempt, metadata={"assessment_id": ctx.assessment_id})
    attempt["status"] = "returned"
    attempt["result_snapshot_ref"] = capture_snapshot(kind="code_discovery_model_attempt_result",
        normalized_json=attempt, parent_ref=attempt["attempt_snapshot_ref"])
    output = {"candidates": [{"candidate_id": "candidate1", "resource_kind": "reading_list",
        "reason": "The fetched text is a bibliography.", "citations": [{"source_id": "page", "excerpt": TEXT}]}],
        "reason": "Bounded discovery."}
    calls = [
        {"call_id": "t1", "name": "search_paper_code", "query_id": "q1", "source_id": "qsource1"},
        {"call_id": "t2", "name": "search_paper_code", "query_id": "q2", "source_id": "qsource2"},
        {"call_id": "t3", "name": "fetch_discovery_page", "candidate_id": "candidate1", "source_id": "page"},
    ]
    audit = {"status": "completed", "attempt_count": 1, "attempts": [attempt], "model_call_count": 1,
        "tool_call_count": 3, "tool_calls": calls, "external_request_count": 3,
        "budget": result.discovery.budget.model_dump(), "candidate_origins": {"candidate1": ["page"]},
        "output_snapshot_ref": capture_snapshot(kind="code_discovery_model_output", normalized_text=json.dumps(output))}
    result.discovery.audit_ref = capture_snapshot(kind="code_discovery_audit", normalized_json=audit)
    merged = {**audit, "passes": [], "discovery_audit_ref": result.discovery.audit_ref}
    result.external_review = {"status": "completed", "mode": "native_tools",
                             "audit_ref": capture_snapshot(kind="external_review_audit", normalized_json=merged)}
    result.external_request_count = 3
    result.model_calls = [CredibilityModelCall(purpose="external_code_discovery_native_tools",
                                              provider="openai", model_version="fixture")]
    # Real guard and event recording run against MockTransport, not the network.
    with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={}))) as client:
        for endpoint in (SEARCH_ENDPOINT, SEARCH_ENDPOINT):
            client.post(endpoint, json={"tools": [{"type": "web_search"}]})
        client.get(FETCH_ENDPOINT, extensions={"code_discovery_operation": "fetch"})
        client.post(CHAT, json={})
    return result


@pytest.fixture
def artifact_run(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(get_settings, "cache_clear", lambda: None)
    monkeypatch.setattr(settings, "openai_api_key", "synthetic-fixture-key")
    monkeypatch.setattr(settings, "openai_base_url", "https://model.example/v1")
    monkeypatch.setattr(settings, "credibility_code_model_enabled", False)
    monkeypatch.setattr(settings, "credibility_code_tool_mode", "prefetch")
    monkeypatch.setenv("CREDIBILITY_ARTIFACT_DIR", str(tmp_path / "before-run"))
    pdf = tmp_path / "pinned.pdf"
    pdf.write_bytes(b"%PDF synthetic acceptance fixture, not a real paper")
    pdf_sha = verifier._sha(pdf)
    ctx = CheckContext(source={"type": "arxiv", "arxiv_id": "2503.12345v1", "upload_id": None},
        repo_root=tmp_path, generated_at="2026-10-19T00:00:00Z", ref=None, unresolved_reason=None,
        doc=StubParser._fake(paper_id="fixture", title="Offline discovery paper"))
    ctx.doc.source_sha256 = pdf_sha
    sample = {"sample_id": "fixture", "pdf_path": str(pdf), "pdf_sha256": pdf_sha,
              "title": "Offline discovery paper", "assessment_id": "original-parsing-fixture"}
    selection = {"is_human_gold": False, "samples": [sample], "input_db": str(tmp_path / "fixture.db"),
                 "input_artifacts": str(tmp_path / "input-artifacts"),
                 "rubric_sha256": load_credibility_rubric().content_sha256}
    selection["selection_sha256"] = hashlib.sha256(json.dumps(selection, ensure_ascii=False, sort_keys=True,
                                                            separators=(",", ":")).encode()).hexdigest()
    selection_path = tmp_path / "selection.json"
    selection_path.write_text(json.dumps(selection))
    monkeypatch.setattr(verifier.lineage, "_load_parsing_context", lambda *_args: (ctx, {"fixture": True}))
    monkeypatch.setattr(verifier.lineage, "_fresh_parse_context", lambda *_args: {
        "mode": "fresh_pdf_parse", "reused_parsed_blocks": False, "pdf_sha256": pdf_sha})
    monkeypatch.setattr("app.credibility.execution.check_code_with_model", _observed_result)
    output = tmp_path / "run"
    assert verifier.run(selection_path, "fixture", output, "native_tools") == 0
    summary = json.loads((output / "summary.json").read_text())
    freeze = tmp_path / "frozen"
    for relative, digest in summary["implementation_sha256"].items():
        copied = freeze / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((verifier.REPO / relative).read_bytes())
        assert verifier._sha(copied) == digest
    (freeze / "manifest.json").write_text(json.dumps(summary["implementation_sha256"]))
    return output, selection_path, freeze


def test_full_offline_audit_accepts_archived_search_fetch_model_and_score(artifact_run, tmp_path, monkeypatch):
    output, selection, freeze = artifact_run

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Audit cannot call HTTP or a model")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr("app.pipeline.orchestrator.build_llm_client", forbidden)
    report = tmp_path / "audit.json"
    assert auditor.main([str(output), "--samples", str(selection), "--implementation-root", str(freeze),
                         "--output", str(report)]) == 0
    run = json.loads(report.read_text())["runs"][0]
    assert run["execution_complete"] is True and run["discovery_candidates_verified"] == 1
    assert run["discovery_attempts_verified"] == 1 and run["discovery_quotes_verified"] == 1
    assert run["wire_http_counts"] == {"openai_search": 2, "openai_fetch": 1, "openai": 1}
    assert run["scoring_eligible_discussions"] == 0


def test_audit_rejects_tampered_source_blob(artifact_run, tmp_path):
    output, selection, freeze = artifact_run
    result = json.loads((output / "code-result.json").read_text())
    saved = SnapshotStore(output / "artifacts").read(result["sources"][0]["snapshot_ref"])
    digest = saved.manifest["blobs"]["normalized_json"]["sha256"]
    blob = output / "artifacts/objects/sha256" / digest[:2] / digest
    blob.write_bytes(b"tampered")
    report = tmp_path / "rejected.json"
    assert auditor.main([str(output), "--samples", str(selection), "--implementation-root", str(freeze),
                         "--output", str(report)]) == 1
    assert json.loads(report.read_text())["status"] == "failed"


def test_audit_never_skips_frozen_implementation_hashes(artifact_run, tmp_path):
    output, selection, freeze = artifact_run
    (freeze / "app/credibility/code_discovery.py").write_text("# Modified after the recorded run\n")
    report = tmp_path / "implementation-rejected.json"
    assert auditor.main([str(output), "--samples", str(selection), "--implementation-root", str(freeze),
                         "--output", str(report)]) == 1
    saved = json.loads(report.read_text())
    assert saved["status"] == "failed" and "frozen implementation" in saved["runs"][0]["error"]


@pytest.mark.parametrize("mutation", ["missing_source", "fake_verified"])
def test_result_link_guard_rejects_missing_sources_and_fake_verified(artifact_run, mutation):
    from app.credibility.models import CodeCheckResult

    output, _, _ = artifact_run
    result = CodeCheckResult.model_validate_json((output / "code-result.json").read_text())
    if mutation == "missing_source":
        result.discovery.queries[0].source_ids = ["does_not_exist"]
    else:
        result.discovery.candidates[0].status = "verified"
    with pytest.raises(ValueError, match="Unclosed|actual confirmed repository proof"):
        auditor.assert_code_result_links(result)


def test_derived_rendered_project_page_quote_keeps_and_verifies_provider_parent(tmp_path):
    store = SnapshotStore(tmp_path / "artifacts")
    provider_text = r"Official implementation of Offline discovery paper 2503\.12345\."
    rendered = "Official implementation of Offline discovery paper 2503.12345."
    parent = store.record(kind="code_discovery_fetch", normalized_json={"operation": "fetch", "text": provider_text},
                          normalized_text=provider_text, requested_url=URL, fetch_status="ok", http_status=200)
    helpers = auditor.implementation_helpers(verifier.REPO)
    version = helpers["code_discovery"].PAGE_TEXT_VERSION
    child = store.derive(parent, kind="project_page", normalized_text=rendered,
                         metadata={"normalization_version": version})
    saved = store.read(child)
    source = CredibilityExternalSource(source_id="page", kind="project_page", url=URL, fetch_status="ok",
        http_status=200, retrieved_at="2026-10-19T00:00:00Z", observed_at="2026-10-19T00:00:00Z",
        is_cached=False, snapshot_ref=child, association_reason="Rendered text derived from archived provider content.")
    auditor.check_quote(source, saved, rendered, "derived-page", helpers)
    assert auditor.discovery_page_text(saved, store, helpers) == (rendered, True)
    assert saved.manifest["parent_ref"] == parent
    assert store.read(parent).normalized_text == provider_text
    assert saved.normalized_json["text"] == provider_text
    parent_saved = store.read(parent)
    blob = parent_saved.manifest["blobs"]["normalized_text"]["sha256"]
    (store.root / "objects/sha256" / blob[:2] / blob).write_text("tampered parent")
    with pytest.raises(ValueError, match="integrity"):
        store.read(child)


def test_normalized_page_rejects_forgery_and_supplies_rendered_hyperlinks(tmp_path):
    store = SnapshotStore(tmp_path / "artifacts")
    helpers = auditor.implementation_helpers(verifier.REPO)
    original = r"[Code](https://github.com/example/new\-repo)\nMath: \(x\_1\)."
    parent = store.record(kind="code_discovery_fetch", normalized_json={"operation": "fetch", "text": original},
                          normalized_text=original)
    rendered = helpers["code_discovery"].normalize_discovery_page_text(original)
    version = helpers["code_discovery"].PAGE_TEXT_VERSION
    child = store.derive(parent, kind="project_page", normalized_text=rendered,
                         metadata={"normalization_version": version})
    text, _ = auditor.discovery_page_text(store.read(child), store, helpers)
    assert "https://github.com/example/new-repo" in text
    assert r"\(x\_1\)" in text
    forged = store.derive(parent, kind="project_page", normalized_text=rendered.replace(r"\(x\_1\)", "(x_1)"),
                          metadata={"normalization_version": version})
    with pytest.raises(ValueError, match="not a normalized provider-text prefix"):
        auditor.discovery_page_text(store.read(forged), store, helpers)


def test_fresh_verifier_blocks_a_forbidden_redirect_before_second_transport(artifact_run, tmp_path, monkeypatch):
    from app.llm.network import load_denied_hosts
    _, selection, _ = artifact_run
    seen = []
    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": f"https://api.{load_denied_hosts()[0]}/v1/models"})
    def check_with_redirect(_ctx):
        with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
            client.post(CHAT, json={})
        raise AssertionError("Forbidden redirect must never return")
    monkeypatch.setattr("app.credibility.execution.check_code_with_model", check_with_redirect)
    output = tmp_path / "redirect-run"
    assert verifier.run(selection, "fixture", output, "native_tools") == 2
    assert seen == ["model.example"]
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "failed"


@pytest.mark.parametrize("provider,url", [
    ("openai_fetch", "https://openreview.net/forum?id=offline-paper&api_key=offline-secret"),
    ("openai_search", "https://unapproved.example/v1/responses"),
])
def test_offline_audit_rejects_credential_fetch_queries_and_unregistered_model_posts(
        artifact_run, tmp_path, provider, url):
    output, selection, freeze = artifact_run
    path = output / "http-audit.json"
    wire = json.loads(path.read_text())
    next(row for row in wire["http_calls"] if row["provider"] == provider)["url"] = url
    path.write_text(json.dumps(wire))
    report = tmp_path / "unsafe-wire.json"
    assert auditor.main([str(output), "--samples", str(selection), "--implementation-root", str(freeze),
                         "--output", str(report)]) == 1
    assert json.loads(report.read_text())["status"] == "failed"

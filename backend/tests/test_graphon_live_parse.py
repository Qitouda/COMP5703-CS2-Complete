"""Fresh-PDF regression for the local Graphon sample; never calls a model."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.credibility.claim_model import _BODY_FORBIDDEN_ROLES
from app.credibility.reference_extraction import extract_reference_entries
from app.parsing.generic import GenericPdfParser


def test_graphon_pdf_restores_body_evidence_and_reference_boundaries(tmp_path):
    pdf = (Path(__file__).resolve().parents[2] / "代码与复现人工测试样本_交接包" / "01_正式样本"
           / "S05_论文仅有伪代码_GraphonCrossValidation" / "论文" / "GraphonCrossValidation_ICLR2026.pdf")
    if not pdf.is_file():
        pytest.skip("Private source PDF is not installed; synthetic regressions run independently")
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == (
        "4b8c8f8c2ec373a0f37e149ee1f93be7546bf2b038fe7a98d2e36e07f5471bdb"
    )
    doc = GenericPdfParser(arxiv_cache_dir=tmp_path, max_download_bytes=30_000_000, max_pages=120).parse_pdf(str(pdf))
    assert len(doc.paper.abstract or "") < 1200
    assert {block.page_start for block in doc.blocks if block.section_role == "abstract"} == {1}
    assert sum(len(block.text) for block in doc.blocks if block.section_role not in _BODY_FORBIDDEN_ROLES) > 20_000
    methods = next(block for block in doc.blocks if "2M ODEL SETUP" in block.text)
    assert methods.section_role not in _BODY_FORBIDDEN_ROLES
    references = [block for block in doc.blocks if block.section_role == "references"]
    entries, total, gaps = extract_reference_entries(references)
    assert len(entries) == total == 22 and not gaps
    originals = {block.chunk_id: block.text for block in references}
    assert all(fragment.text in originals[fragment.chunk_id] for entry in entries for fragment in entry.fragments)

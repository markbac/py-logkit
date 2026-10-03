"""Tests that keep the architecture document present, linked and valid."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHITECTURE = ROOT / "docs" / "architecture.md"


def test_architecture_document_is_linked_from_the_readme():
    """Contributors must be able to find it."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/architecture.md" in readme
    assert ARCHITECTURE.is_file()


def test_mermaid_diagrams_are_present_and_avoid_semicolons():
    """Semicolons break Mermaid labels, so they are not allowed inside the diagrams."""
    blocks = re.findall(r"```mermaid\n(.*?)```", ARCHITECTURE.read_text(encoding="utf-8"), re.S)

    assert len(blocks) >= 3
    assert all(";" not in block for block in blocks)


def test_architecture_names_the_public_api():
    """Every exported name is mentioned, so new exports force a documentation update."""
    import pylogkit

    text = ARCHITECTURE.read_text(encoding="utf-8")

    missing = [name for name in pylogkit.__all__ if name not in text]
    assert not missing, missing


def test_relative_links_resolve():
    """Links to other documents in the repository must point at real files."""
    text = ARCHITECTURE.read_text(encoding="utf-8")

    for target in re.findall(r"\]\((?!https?:)([^)#]+)", text):
        assert (ARCHITECTURE.parent / target).resolve().exists(), target

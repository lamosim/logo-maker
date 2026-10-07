"""Markdown helpers the document tests share (tests/test_knowledge.py, tests/test_skill_docs.py): a document's sections by
heading, fence-aware, with one rule for matching a heading."""
from __future__ import annotations

import re


def heading_is(found: str, required: str) -> bool:
    """Whether heading `found` is `required`, alone or followed by punctuation (": ...", " (...)"), never by more words:
    "Use carefully" is not "Use"."""
    return re.fullmatch(rf"{re.escape(required)}(?:\s*[^\w\s].*)?", found) is not None


def sections(text: str, level: int = 2) -> list[tuple[str, str]]:
    """Each section headed at `level` (2 for "## ", 3 for "### ") as (heading, body). A line inside a fenced code block
    never starts a section."""
    marker = "#" * level + " "
    out: list[tuple[str, str]] = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith(marker):
            out.append((line[len(marker):].strip(), ""))
        elif out:
            out[-1] = (out[-1][0], out[-1][1] + line)
    return out


def headings(text: str) -> list[str]:
    return [heading for heading, _ in sections(text)]


def section(text: str, heading: str, level: int = 2) -> str:
    """The body of the first section at `level` whose heading is `heading` (heading_is)."""
    bodies = [body for found, body in sections(text, level) if heading_is(found, heading)]
    assert bodies, f"no section {heading!r}"
    return bodies[0]

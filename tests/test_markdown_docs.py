"""Static quality gates for Markdown documentation."""

from __future__ import annotations

from pathlib import Path
import re
import unittest
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    )


class MarkdownDocumentationTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        broken: list[str] = []

        for md_path in markdown_files():
            text = md_path.read_text(encoding="utf-8")
            for match in link_pattern.finditer(text):
                target = match.group(1).split()[0].strip("<>")
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue

                parsed = urllib.parse.urlparse(target)
                relative_path = urllib.parse.unquote(parsed.path)
                if not relative_path:
                    continue

                resolved = (md_path.parent / relative_path).resolve()
                if not str(resolved).startswith(str(ROOT)) or not resolved.exists():
                    broken.append(f"{md_path.relative_to(ROOT)} -> {target}")

        self.assertEqual([], broken)

    def test_markdown_script_references_exist(self) -> None:
        patterns = (
            re.compile(r"python\s+scripts[/\\]([A-Za-z0-9_]+\.py)"),
            re.compile(r"python\s+-m\s+scripts\.([A-Za-z0-9_]+)"),
        )
        missing: list[str] = []

        for md_path in markdown_files():
            text = md_path.read_text(encoding="utf-8")
            for match in patterns[0].finditer(text):
                script = ROOT / "scripts" / match.group(1)
                if not script.exists():
                    missing.append(f"{md_path.relative_to(ROOT)} -> scripts/{match.group(1)}")
            for match in patterns[1].finditer(text):
                script = ROOT / "scripts" / f"{match.group(1)}.py"
                if not script.exists():
                    missing.append(f"{md_path.relative_to(ROOT)} -> scripts/{match.group(1)}.py")

        self.assertEqual([], missing)

    def test_numbered_timeline_docs_are_not_current_docs(self) -> None:
        numbered_docs = [path.name for path in (ROOT / "docs").glob("[0-9][0-9]-*.md")]
        self.assertEqual([], numbered_docs)

    def test_no_stale_primary_doc_references(self) -> None:
        stale_patterns = (
            "00-team-onboarding-and-data-setup.md",
            "05-architecture.md",
            "08-data-contracts.md",
            "14-warehouse-ddl.md",
            "20-reconciliation-idempotency-report.md",
            "22-analytics-semantic-contract.md",
            "23-metric-catalog.md",
            "26-superset-local-demo-runbook.md",
        )
        offenders: list[str] = []

        for md_path in markdown_files():
            if "archive" in md_path.parts:
                continue
            text = md_path.read_text(encoding="utf-8")
            for stale in stale_patterns:
                if stale in text:
                    offenders.append(f"{md_path.relative_to(ROOT)} contains {stale}")

        self.assertEqual([], offenders)

    def test_markdown_does_not_contain_obvious_secrets(self) -> None:
        secret_patterns = (
            re.compile(r"(?:postgresql|mysql|mongodb)://[^\s`<]+:[^\s`<]+@", re.IGNORECASE),
            re.compile(r"password\s*=\s*(?!\*\*\*|<|CHANGE_ME|change_me)[^\s`]+", re.IGNORECASE),
            re.compile(r"(?:secret|api[_-]?key)\s*=\s*(?!<|CHANGE_ME|change_me)[^\s`]+", re.IGNORECASE),
        )
        offenders: list[str] = []

        for md_path in markdown_files():
            text = md_path.read_text(encoding="utf-8")
            for pattern in secret_patterns:
                if pattern.search(text):
                    offenders.append(str(md_path.relative_to(ROOT)))
                    break

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()

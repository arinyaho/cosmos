#!/usr/bin/env python3
"""
Create a single Markdown bundle of a GitHub PR for reviewing.

Requires:
  - GitHub CLI: https://cli.github.com/ (command: `gh`)
  - Authentication: `gh auth status`

Examples:
  python3 scripts/reviewpack.py 123 > /tmp/pr-123.md
  python3 scripts/reviewpack.py https://github.com/org/repo/pull/123 --out /tmp/pr.md
  python3 scripts/reviewpack.py 123 -R org/repo --out /tmp/pr.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr)
        raise SystemExit(exc.returncode) from exc


def _gh(base_args: list[str], repo: str | None) -> str:
    cmd = ["gh", *base_args]
    if repo:
        cmd.extend(["-R", repo])
    return _run(cmd)


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _has_any(body: str, patterns: list[str]) -> bool:
    if not body:
        return False
    lower = body.lower()
    return any(re.search(p, lower) for p in patterns)

def _is_docs_path(path: str) -> bool:
    lower = path.lower()
    if lower.startswith(("docs/", "doc/", "documentation/")):
        return True
    if lower.startswith("spec/"):
        return True
    return lower.endswith((".md", ".mdx", ".rst", ".adoc", ".txt"))


def _is_test_path(path: str) -> bool:
    lower = path.lower()
    filename = lower.split("/")[-1]

    # Common test directories
    if any(token in lower for token in ("/__tests__/", "/tests/", "/test/", "/src/test/")):
        return True
    if lower.startswith(("__tests__/", "tests/", "test/", "src/test/")):
        return True

    # Common test file patterns across ecosystems
    if filename.endswith("_test.go"):
        return True
    if filename.endswith(("_test.py", "_test.rb", "_test.php")):
        return True
    if filename.startswith("test_") and filename.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
        return True
    if ".test." in filename or ".spec." in filename:
        return True
    return False


def _why_what_how_status(body: str) -> dict[str, bool]:
    # Accept either Markdown headings or simple labels like "Why:".
    return {
        "why": _has_any(body, [r"(^|\n)\s*#+\s*why\b", r"(^|\n)\s*why\s*:\s*\S", r"\bmotivation\b", r"\bbackground\b"]),
        "what": _has_any(body, [r"(^|\n)\s*#+\s*what\b", r"(^|\n)\s*what\s*:\s*\S", r"\bchanges?\b", r"\buser[- ]visible\b"]),
        "how": _has_any(body, [r"(^|\n)\s*#+\s*how\b", r"(^|\n)\s*how\s*:\s*\S", r"\bapproach\b", r"\bimplementation\b"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Markdown review bundle for a GitHub PR.")
    parser.add_argument("pr", nargs="?", default="", help="PR number, URL, or branch. Defaults to current branch PR.")
    parser.add_argument("-R", "--repo", default=None, help="Override repo in OWNER/REPO form.")
    parser.add_argument("--out", default="-", help="Output file path, or '-' for stdout (default).")
    parser.add_argument("--no-patch", action="store_true", help="Omit the patch diff (useful for huge PRs).")
    args = parser.parse_args()

    pr = args.pr
    repo = args.repo

    pr_json_raw = _gh(
        [
            "pr",
            "view",
            pr,
            "--json",
            "number,title,url,author,baseRefName,headRefName,headRefOid,body,files,labels,isDraft,reviewDecision,statusCheckRollup",
        ],
        repo,
    )
    pr_json = json.loads(pr_json_raw)

    changed_files = _gh(["pr", "diff", pr, "--name-only"], repo).strip()
    changed_file_list = [line.strip() for line in changed_files.splitlines() if line.strip()]
    test_files = [path for path in changed_file_list if _is_test_path(path)]
    non_doc_files = [path for path in changed_file_list if not _is_docs_path(path)]
    maybe_missing_tests = bool(non_doc_files) and not test_files

    checks_json_raw = _gh(["pr", "checks", pr, "--json", "bucket,name,state,link,workflow,event"], repo)
    checks_json = json.loads(checks_json_raw) if checks_json_raw.strip() else []

    patch = ""
    if not args.no_patch:
        patch = _gh(["pr", "diff", pr, "--patch"], repo)

    body = pr_json.get("body") or ""
    wwh = _why_what_how_status(body)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_lines: list[str] = []
    out_lines.append(f"# PR Review Pack")
    out_lines.append("")
    out_lines.append(f"- Generated: {now} (UTC)")
    out_lines.append(f"- PR: {pr_json.get('url')}")
    out_lines.append("")
    out_lines.append("## Metadata")
    out_lines.append("```json")
    out_lines.append(_json({k: pr_json.get(k) for k in ["number", "title", "url", "author", "baseRefName", "headRefName", "headRefOid", "isDraft", "reviewDecision", "labels"]}))
    out_lines.append("```")
    out_lines.append("")
    out_lines.append("## PR Description (raw)")
    out_lines.append(body if body.strip() else "_(empty)_")
    out_lines.append("")
    out_lines.append("## Gate: Why / What / How (heuristic)")
    out_lines.append(f"- why: {'ok' if wwh['why'] else 'missing'}")
    out_lines.append(f"- what: {'ok' if wwh['what'] else 'missing'}")
    out_lines.append(f"- how: {'ok' if wwh['how'] else 'missing'}")
    out_lines.append("")
    out_lines.append("## Gate: Tests (heuristic)")
    out_lines.append(f"- test_files_changed: {'yes' if test_files else 'no'} ({len(test_files)})")
    out_lines.append(f"- non_doc_files_changed: {'yes' if non_doc_files else 'no'} ({len(non_doc_files)})")
    out_lines.append(f"- potential_missing_tests: {'yes' if maybe_missing_tests else 'no'}")
    if test_files:
        out_lines.append("")
        out_lines.append("Matched test files:")
        out_lines.append("```")
        out_lines.extend(test_files)
        out_lines.append("```")
    out_lines.append("")
    out_lines.append("## Changed Files")
    out_lines.append("```")
    out_lines.append(changed_files)
    out_lines.append("```")
    out_lines.append("")
    out_lines.append("## Checks")
    out_lines.append("```json")
    out_lines.append(_json(checks_json))
    out_lines.append("```")

    if patch:
        out_lines.append("")
        out_lines.append("## Patch")
        out_lines.append("```diff")
        out_lines.append(patch.rstrip("\n"))
        out_lines.append("```")

    out_text = "\n".join(out_lines) + "\n"

    if args.out == "-":
        sys.stdout.write(out_text)
        return

    Path(args.out).write_text(out_text, encoding="utf-8")


if __name__ == "__main__":
    main()

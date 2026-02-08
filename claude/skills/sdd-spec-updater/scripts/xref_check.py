#!/usr/bin/env python3
"""Cross-reference checker for SDD spec documents.

Validates:
1. Relative markdown links (broken links)
2. GAP ID references to non-existent GAPs
3. Terminology consistency (optional dictionary)

Usage:
    python3 xref_check.py [--docs-root <path>] [--changed-files f1.md f2.md] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

GAP_PATTERN = re.compile(r"\bGAP-(\d{3,})\b")
MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
# Match only relative links (not http/https/mailto/# anchors)
RELATIVE_LINK = re.compile(r"^(?!https?://|mailto:|#)(.+\.md)(#.*)?$")
# Fenced code block markers: ``` or ~~~ (CommonMark)
FENCE_PATTERN = re.compile(r"^(`{3,}|~{3,})")


def _fence_token(line: str) -> tuple[str, int] | None:
    """Extract fence token (char, length) if line is a code fence delimiter.

    Returns (char, length) tuple or None.  Per CommonMark, a closing fence
    must use the same character and be at least as long as the opener.
    """
    m = FENCE_PATTERN.match(line.strip())
    if m:
        token = m.group(1)
        return (token[0], len(token))
    return None


def find_md_files(docs_root: Path, changed_files: list[str] | None) -> list[Path]:
    """Get list of markdown files to check."""
    if changed_files:
        return [Path(f) for f in changed_files if f.endswith(".md") and Path(f).exists()]
    return sorted(docs_root.rglob("*.md"))


def check_broken_links(files: list[Path], docs_root: Path) -> list[dict]:
    """Check for broken relative markdown links."""
    issues = []
    for md_file in files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = content.splitlines()
        # Track fenced code block state (opener char + length per CommonMark)
        fence_opener: tuple[str, int] | None = None
        for line_num, line in enumerate(lines, start=1):
            ft = _fence_token(line)
            if ft is not None:
                if fence_opener is None:
                    fence_opener = ft
                elif ft[0] == fence_opener[0] and ft[1] >= fence_opener[1]:
                    fence_opener = None
                continue
            if fence_opener is not None:
                continue
            for match in MD_LINK_PATTERN.finditer(line):
                link_text = match.group(1)
                link_target = match.group(2)

                rel_match = RELATIVE_LINK.match(link_target)
                if not rel_match:
                    continue

                target_path = rel_match.group(1)
                resolved = (md_file.parent / target_path).resolve()

                if not resolved.exists():
                    issues.append(
                        {
                            "type": "broken_link",
                            "file": str(md_file),
                            "line": line_num,
                            "link_text": link_text,
                            "target": target_path,
                            "resolved": str(resolved),
                        }
                    )

    return issues


def check_gap_references(files: list[Path], docs_root: Path) -> list[dict]:
    """Check for GAP ID references to non-existent GAPs.

    A GAP is 'defined' if it appears in a table row as the first cell
    in any file under docs_root. References are all other mentions.
    """
    # First pass: collect all defined GAP IDs from ALL docs
    defined_gaps: set[int] = set()
    all_files = sorted(docs_root.rglob("*.md"))

    for md_file in all_files:
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        # Track fenced code block state — skip definitions inside code examples
        fence_opener: tuple[str, int] | None = None
        for line in lines:
            ft = _fence_token(line)
            if ft is not None:
                if fence_opener is None:
                    fence_opener = ft
                elif ft[0] == fence_opener[0] and ft[1] >= fence_opener[1]:
                    fence_opener = None
                continue
            if fence_opener is not None:
                continue
            # Table row or header starting with GAP ID counts as definition
            # Header pattern: GAP must be the first word after # (e.g., "## GAP-001: ...")
            # Not incidental mentions like "# Related Work on GAP-999"
            if re.match(r"^\|\s*\*?\*?GAP-\d{3,}", line) or re.match(r"^#+\s+\*?\*?GAP-\d{3,}", line):
                for m in GAP_PATTERN.finditer(line):
                    defined_gaps.add(int(m.group(1)))

    # Second pass: check references in target files
    issues = []
    for md_file in files:
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        # Track fenced code block state (opener char + length per CommonMark)
        fence_opener: tuple[str, int] | None = None
        for line_num, line in enumerate(lines, start=1):
            ft = _fence_token(line)
            if ft is not None:
                if fence_opener is None:
                    fence_opener = ft
                elif ft[0] == fence_opener[0] and ft[1] >= fence_opener[1]:
                    fence_opener = None
                continue
            if fence_opener is not None:
                continue
            for match in GAP_PATTERN.finditer(line):
                gap_num = int(match.group(1))
                if gap_num not in defined_gaps:
                    issues.append(
                        {
                            "type": "undefined_gap",
                            "file": str(md_file),
                            "line": line_num,
                            "gap_id": f"GAP-{gap_num:03d}",
                            "text": line.strip()[:120],
                        }
                    )

    return issues


def check_terminology(
    files: list[Path], terminology_path: Path | None
) -> list[dict]:
    """Check for terminology inconsistencies using a dictionary file."""
    if not terminology_path or not terminology_path.exists():
        return []

    try:
        with open(terminology_path) as f:
            terms = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    # terms format: {"canonical": "Secret Key", "variants": ["SecKey", "sec_key", "secretkey"]}
    issues = []
    for md_file in files:
        try:
            content = md_file.read_text(encoding="utf-8")
            lines = content.splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        # Track fenced code block state (opener char + length per CommonMark)
        fence_opener: tuple[str, int] | None = None
        skip_lines: set[int] = set()
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            ft = _fence_token(line)
            if ft is not None:
                if fence_opener is None:
                    fence_opener = ft
                elif ft[0] == fence_opener[0] and ft[1] >= fence_opener[1]:
                    fence_opener = None
                skip_lines.add(line_num)
                continue
            if fence_opener is not None or stripped.startswith("`"):
                skip_lines.add(line_num)

        for term_entry in terms:
            canonical = term_entry.get("canonical", "")
            variants = term_entry.get("variants", [])

            for variant in variants:
                pattern = re.compile(r"\b" + re.escape(variant) + r"\b", re.IGNORECASE)
                for line_num, line in enumerate(lines, start=1):
                    if line_num in skip_lines:
                        continue
                    if pattern.search(line):
                        issues.append(
                            {
                                "type": "terminology",
                                "file": str(md_file),
                                "line": line_num,
                                "found": variant,
                                "canonical": canonical,
                                "text": line.strip()[:120],
                            }
                        )

    return issues


def main():
    parser = argparse.ArgumentParser(description="Cross-reference checker for SDD docs")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Root directory to scan (default: docs/)",
    )
    parser.add_argument(
        "--changed-files",
        nargs="*",
        help="Only check these files (for PR scope)",
    )
    parser.add_argument(
        "--terminology",
        type=Path,
        default=None,
        help="Path to terminology.json dictionary",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.docs_root.is_dir() and not args.changed_files:
        print(f"Error: {args.docs_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Auto-detect terminology file
    terminology_path = args.terminology
    if not terminology_path:
        default_term = Path(__file__).parent.parent / "references" / "terminology.json"
        if default_term.exists():
            terminology_path = default_term

    files = find_md_files(args.docs_root, args.changed_files)

    broken_links = check_broken_links(files, args.docs_root)
    undefined_gaps = check_gap_references(files, args.docs_root)
    term_issues = check_terminology(files, terminology_path)

    all_issues = broken_links + undefined_gaps + term_issues

    if args.json:
        output = {
            "files_checked": len(files),
            "issues": all_issues,
            "summary": {
                "broken_links": len(broken_links),
                "undefined_gaps": len(undefined_gaps),
                "terminology": len(term_issues),
                "total": len(all_issues),
            },
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        if all_issues:
            sys.exit(1)
    else:
        print(f"Checked {len(files)} files under {args.docs_root}")
        print()

        if broken_links:
            print(f"Broken links ({len(broken_links)}):")
            for issue in broken_links:
                print(f"  {issue['file']}:{issue['line']}  [{issue['link_text']}]({issue['target']})")
            print()

        if undefined_gaps:
            print(f"Undefined GAP references ({len(undefined_gaps)}):")
            for issue in undefined_gaps:
                print(f"  {issue['file']}:{issue['line']}  {issue['gap_id']}")
            print()

        if term_issues:
            print(f"Terminology issues ({len(term_issues)}):")
            for issue in term_issues:
                print(f"  {issue['file']}:{issue['line']}  '{issue['found']}' -> '{issue['canonical']}'")
            print()

        if not all_issues:
            print("No issues found.")
        else:
            print(f"Total: {len(all_issues)} issues")
            sys.exit(1)


if __name__ == "__main__":
    main()

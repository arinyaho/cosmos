#!/usr/bin/env python3
"""GAP ID scanner and auto-assigner for SDD spec documents.

Scans markdown files for GAP-NNN patterns, detects duplicates,
and returns the next available GAP ID.

Usage:
    python3 gap_id.py [--docs-root <path>] [--check-only] [--json]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

GAP_PATTERN = re.compile(r"\bGAP-(\d{3,})\b")
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


def scan_gap_ids(docs_root: Path) -> dict[int, list[dict]]:
    """Scan all .md files for GAP-NNN patterns.

    Returns: {gap_number: [{file, line, text}, ...]}
    """
    results: dict[int, list[dict]] = defaultdict(list)

    for md_file in sorted(docs_root.rglob("*.md")):
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        # Track fenced code block state — skip examples in code blocks
        fence_opener: tuple[str, int] | None = None
        for line_num, line_text in enumerate(lines, start=1):
            ft = _fence_token(line_text)
            if ft is not None:
                if fence_opener is None:
                    fence_opener = ft
                elif ft[0] == fence_opener[0] and ft[1] >= fence_opener[1]:
                    fence_opener = None
                continue
            if fence_opener is not None:
                continue
            for match in GAP_PATTERN.finditer(line_text):
                gap_num = int(match.group(1))
                results[gap_num].append(
                    {
                        "file": str(md_file.relative_to(docs_root)),
                        "line": line_num,
                        "text": line_text.strip()[:120],
                    }
                )

    return dict(results)


def find_definitions(gap_ids: dict[int, list[dict]]) -> dict[int, list[dict]]:
    """Filter to GAP IDs that appear in definition contexts (tables, headers)."""
    definition_patterns = [
        re.compile(r"^\|\s*\*?\*?GAP-\d{3,}"),  # table row starting with GAP
        re.compile(r"^#+\s+\*?\*?GAP-\d{3,}"),  # header starting with GAP
        re.compile(r"^\|\s*GAP-\d{3,}\s*\|"),  # table cell with GAP
    ]
    definitions: dict[int, list[dict]] = defaultdict(list)

    for gap_num, occurrences in gap_ids.items():
        for occ in occurrences:
            if any(p.search(occ["text"]) for p in definition_patterns):
                definitions[gap_num].append(occ)

    return dict(definitions)


def main():
    parser = argparse.ArgumentParser(description="GAP ID scanner and auto-assigner")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs"),
        help="Root directory to scan (default: docs/)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for duplicates, don't suggest next ID",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    args = parser.parse_args()

    if not args.docs_root.is_dir():
        print(f"Error: {args.docs_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    all_ids = scan_gap_ids(args.docs_root)
    definitions = find_definitions(all_ids)

    # Detect duplicates: same GAP ID defined in DIFFERENT files
    # Same-file multiple occurrences (summary + detail) are expected
    duplicates = {}
    for gap_num, defs in definitions.items():
        unique_files = {d["file"] for d in defs}
        if len(unique_files) > 1:
            duplicates[gap_num] = defs

    # Find next available ID (from definitions only, not all mentions)
    max_id = max(definitions.keys()) if definitions else 0
    next_id = max_id + 1

    if args.json:
        output = {
            "all_ids": {f"GAP-{k:03d}": v for k, v in sorted(all_ids.items())},
            "definitions": {f"GAP-{k:03d}": v for k, v in sorted(definitions.items())},
            "duplicates": {f"GAP-{k:03d}": v for k, v in sorted(duplicates.items())},
            "max_id": f"GAP-{max_id:03d}" if max_id > 0 else None,
            "next_id": f"GAP-{next_id:03d}",
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Scanned: {args.docs_root}")
        print(f"Found {len(all_ids)} unique GAP IDs")
        print()

        if definitions:
            print("Defined GAP IDs:")
            for gap_num in sorted(definitions.keys()):
                defs = definitions[gap_num]
                for d in defs:
                    print(f"  GAP-{gap_num:03d}  {d['file']}:{d['line']}")
            print()

        if duplicates:
            print("INFO: Cross-file definitions (review if intentional):")
            for gap_num in sorted(duplicates.keys()):
                defs = duplicates[gap_num]
                unique_files = sorted({d["file"] for d in defs})
                print(f"  GAP-{gap_num:03d} in: {', '.join(unique_files)}")
            print()

        if not args.check_only:
            print(f"Next available ID: GAP-{next_id:03d}")


if __name__ == "__main__":
    main()

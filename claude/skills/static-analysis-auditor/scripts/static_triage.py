#!/usr/bin/env python3
"""
Triage helper for static scan reports.
Consumes the markdown report from static_scan.py and produces a condensed summary
with per-section top files and cross-signal hotspots.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

SECTION_RE = re.compile(r"^###\s+(.*)$")
LINE_RE = re.compile(r"`([^`]+)`")
PATH_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):")


SECTION_KEYS = [
    "Error handling",
    "Silent continue",
    "Status success",
    "Status fail",
    "Status APIs",
    "Storage I/O",
    "Retry/backoff",
    "Shard mapping/searchable invariants",
]


def parse_report(path: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = defaultdict(list)
    current = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = SECTION_RE.match(line)
            if m:
                name = m.group(1).strip()
                current = name
                continue
            if current is None:
                continue
            if line.startswith("- `"):
                mm = LINE_RE.search(line)
                if not mm:
                    continue
                sections[current].append(mm.group(1))
    return sections


def summarize_sections(sections: Dict[str, List[str]], top_n: int) -> Tuple[List[str], Dict[str, Counter]]:
    summary_lines: List[str] = []
    per_section_counts: Dict[str, Counter] = {}
    for key in SECTION_KEYS:
        entries = sections.get(key, [])
        counts = Counter()
        for item in entries:
            pm = PATH_RE.match(item)
            if not pm:
                continue
            counts[pm.group("path")] += 1
        per_section_counts[key] = counts
        summary_lines.append(f"- {key}: {len(entries)} matches, {len(counts)} files")
    return summary_lines, per_section_counts


def render_top_files(per_section_counts: Dict[str, Counter], top_n: int) -> List[str]:
    lines: List[str] = []
    for key in SECTION_KEYS:
        counts = per_section_counts.get(key, Counter())
        lines.append(f"### Top files: {key}")
        if not counts:
            lines.append("(none)")
            continue
        for path, cnt in counts.most_common(top_n):
            lines.append(f"- {path} ({cnt})")
    return lines


def render_hotspots(per_section_counts: Dict[str, Counter], min_sections: int, top_n: int) -> List[str]:
    # Files appearing across multiple sections
    file_sections: Dict[str, set] = defaultdict(set)
    for key, counts in per_section_counts.items():
        for path in counts.keys():
            file_sections[path].add(key)

    hotspots = [
        (path, len(secs), sorted(secs))
        for path, secs in file_sections.items()
        if len(secs) >= min_sections
    ]
    hotspots.sort(key=lambda x: (-x[1], x[0]))

    lines: List[str] = ["### Cross-signal hotspots"]
    if not hotspots:
        lines.append("(none)")
        return lines
    for path, count, secs in hotspots[:top_n]:
        lines.append(f"- {path} ({count} sections): {', '.join(secs)}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage static scan markdown output.")
    parser.add_argument("report", help="Path to static scan markdown report")
    parser.add_argument("--top-n", type=int, default=10, help="Top N files per section")
    parser.add_argument("--min-sections", type=int, default=3, help="Min sections for hotspot")
    parser.add_argument("--output", help="Write report to file instead of stdout")
    args = parser.parse_args()

    if not os.path.exists(args.report):
        print(f"Report not found: {args.report}", file=sys.stderr)
        return 2

    sections = parse_report(args.report)
    summary_lines, per_section_counts = summarize_sections(sections, args.top_n)
    top_files = render_top_files(per_section_counts, args.top_n)
    hotspots = render_hotspots(per_section_counts, args.min_sections, args.top_n)

    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = "\n".join(
        [
            "# Static Scan Triage",
            f"Generated: {timestamp}",
            f"Source: {os.path.abspath(args.report)}",
            "",
            "## Summary",
            *summary_lines,
            "",
            "## Top Files by Section",
            *top_files,
            "",
            "## Hotspots",
            *hotspots,
            "",
            "## Notes",
            "- Heuristic triage only; manual review required.",
        ]
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

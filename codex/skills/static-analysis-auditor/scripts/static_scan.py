#!/usr/bin/env python3
"""
Static scan helper for async pipeline audits.
Collects candidate risk points using ripgrep (or grep fallback) and writes a markdown report.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
import sys
from typing import Iterable, List, Tuple

PATTERNS: List[Tuple[str, str]] = [
    ("Error handling", r"(err|error|failed|failure)"),
    ("Silent continue", r"continue"),
    ("Status success", r"Status.*Success|JobStatusSuccess|JOB_STATUS_SUCCESS"),
    ("Status fail", r"Status.*Fail|JobStatusFailed|JOB_STATUS_FAIL"),
    ("Status APIs", r"Get.*Status|JobStatus|OperationStatus"),
    ("Storage I/O", r"Upload|Download|PutObject|GetObject"),
    ("Retry/backoff", r"retry|backoff|attempt"),
    # Useful for IVF_VCT/VCT split drift bugs: shard remains searchable after mapping deletion.
    ("Shard mapping/searchable invariants", r"shardnodemap|_shardnodemap|_shard_map|DeleteRowInShardNodeMap|UpdateShardSearchable|DeactivatedNodes"),
]

DEFAULT_PATHS = [
    "services/internal",
    "services/cmd",
    "services/test",
]

DEFAULT_EXCLUDES = [
    "**/external/**",
    "**/third_party/**",
    "**/vendor/**",
    "**/.git/**",
    "**/node_modules/**",
]


def _run_cmd(cmd: List[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def _rg_available() -> bool:
    return shutil.which("rg") is not None


def _build_rg_cmd(pattern: str, paths: Iterable[str], excludes: Iterable[str]) -> List[str]:
    cmd = ["rg", "-n", "--no-heading", "--color", "never", "--ignore-case", pattern]
    for ex in excludes:
        cmd.extend(["--glob", f"!{ex}"])
    cmd.extend(paths)
    return cmd


def _build_grep_cmd(pattern: str, paths: Iterable[str], excludes: Iterable[str]) -> List[str]:
    # grep fallback: approximate exclusions by pruning common dirs
    cmd = ["grep", "-R", "-n", "-E", "-i", pattern]
    for ex in excludes:
        if ex.startswith("**/") and ex.endswith("/**"):
            cmd.extend(["--exclude-dir", ex[3:-3]])
    cmd.extend(paths)
    return cmd


def _scan(pattern: str, cwd: str, paths: Iterable[str], excludes: Iterable[str]) -> List[str]:
    if _rg_available():
        cmd = _build_rg_cmd(pattern, paths, excludes)
    else:
        cmd = _build_grep_cmd(pattern, paths, excludes)
    proc = _run_cmd(cmd, cwd)
    if proc.returncode not in (0, 1):
        return [f"[scan error] {proc.stderr.strip() or 'unknown error'}"]
    out = proc.stdout.strip()
    return out.splitlines() if out else []


def _render_section(title: str, lines: List[str], max_lines: int) -> str:
    count = len(lines)
    header = [f"### {title}", f"- Matches: {count}"]
    if count == 0:
        return "\n".join(header + ["(none)"])
    trimmed = lines[:max_lines]
    body = "\n".join(f"- `{line}`" for line in trimmed)
    if count > max_lines:
        body += f"\n- … truncated ({count - max_lines} more)"
    return "\n".join(header + [body])


def _write_report(out_path: str | None, content: str) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        print(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Static scan for async pipeline risk points.")
    parser.add_argument("--root", default=os.getcwd(), help="Repository root (default: cwd)")
    parser.add_argument("--paths", nargs="*", default=DEFAULT_PATHS, help="Paths to scan")
    parser.add_argument("--max-lines", type=int, default=200, help="Max lines per section")
    parser.add_argument("--output", help="Write report to file instead of stdout")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    paths = [p for p in args.paths if os.path.exists(os.path.join(root, p))]
    if not paths:
        print("No valid paths to scan.", file=sys.stderr)
        return 2

    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    summary = []
    for title, pattern in PATTERNS:
        lines = _scan(pattern, root, paths, DEFAULT_EXCLUDES)
        sections.append(_render_section(title, lines, args.max_lines))
        summary.append(f"- {title}: {len(lines)} matches")

    report = "\n".join(
        [
            "# Static Scan Report",
            f"Generated: {timestamp}",
            f"Root: {root}",
            f"Paths: {', '.join(paths)}",
            "",
            "## Summary",
            *summary,
            "",
            "## Details",
            "",
            *sections,
            "",
            "## Notes",
            "- Heuristic scan only; manual review required to confirm defects.",
        ]
    )

    _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

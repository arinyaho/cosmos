#!/usr/bin/env python3
"""
Post PR comments (global + inline) to GitHub.

This script is intentionally strict: it validates inputs and supports a dry-run
mode by default. Use --apply to actually post.

Input JSON shape (read from --input, default "-"):
{
  "global_comment": "markdown string (optional)",
  "inline_comments": [
    { "path": "path/to/file.ts", "line": 123, "body": "comment markdown", "side": "RIGHT" }
  ]
}

Examples:
  cat review.json | python3 scripts/post_pr_comments.py 123 --apply
  python3 scripts/post_pr_comments.py https://github.com/org/repo/pull/123 -R org/repo --input review.json --apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse


Side = Literal["RIGHT", "LEFT"]


def _run(cmd: list[str], *, stdin: str | None = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr)
        raise SystemExit(exc.returncode) from exc


def _gh(base_args: list[str], repo: str | None, *, stdin: str | None = None) -> str:
    cmd = ["gh", *base_args]
    if repo:
        cmd.extend(["-R", repo])
    return _run(cmd, stdin=stdin)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"[ERROR] {msg}")


def _parse_pr_url(url: str) -> tuple[str, str, str, int]:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 4 and parts[2] == "pull":
        owner = parts[0]
        repo = parts[1]
        try:
            number = int(parts[3])
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"[ERROR] Could not parse PR number from url: {url!r}") from exc
        return host, owner, repo, number
    raise SystemExit(f"[ERROR] Could not parse GitHub PR url: {url!r}")


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    body: str
    side: Side = "RIGHT"

    @staticmethod
    def from_obj(obj: dict[str, Any]) -> "InlineComment":
        path = (obj.get("path") or "").strip()
        body = (obj.get("body") or "").strip()
        side_raw = (obj.get("side") or "RIGHT").strip().upper()
        _require(side_raw in ("RIGHT", "LEFT"), f"inline_comments.side must be RIGHT or LEFT (got {side_raw!r})")
        try:
            line = int(obj.get("line"))
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"[ERROR] inline_comments.line must be an integer (got {obj.get('line')!r})") from exc
        _require(path != "", "inline_comments.path is required")
        _require(body != "", "inline_comments.body is required")
        _require(line > 0, "inline_comments.line must be > 0")
        return InlineComment(path=path, line=line, body=body, side=side_raw)  # type: ignore[arg-type]


def main() -> None:
    parser = argparse.ArgumentParser(description="Post PR comments to GitHub (global + inline).")
    parser.add_argument("pr", help="PR number, URL, or branch.")
    parser.add_argument("-R", "--repo", default=None, help="Override repo in OWNER/REPO form.")
    parser.add_argument("--input", default="-", help="JSON input file path, or '-' for stdin (default).")
    parser.add_argument("--apply", action="store_true", help="Actually post comments (default: dry-run).")
    args = parser.parse_args()

    raw = _read_input(args.input).strip()
    _require(raw != "", "input JSON is empty")
    payload = json.loads(raw)

    global_comment = (payload.get("global_comment") or "").strip()
    inline_raw = payload.get("inline_comments") or []
    _require(isinstance(inline_raw, list), "inline_comments must be a list")
    inline_comments = [InlineComment.from_obj(item) for item in inline_raw]

    pr_view_raw = _gh(
        [
            "pr",
            "view",
            args.pr,
            "--json",
            "number,headRefOid,headRepository,headRepositoryOwner,url",
        ],
        args.repo,
    )
    pr_view = json.loads(pr_view_raw)
    pr_number = pr_view["number"]
    head_sha = pr_view["headRefOid"]
    pr_url = str(pr_view.get("url") or "")
    _require(pr_url != "", "Could not read PR url from gh pr view output")
    host, owner, repo_name, url_number = _parse_pr_url(pr_url)
    if url_number != int(pr_number):
        raise SystemExit(f"[ERROR] PR url number ({url_number}) does not match gh number ({pr_number})")

    if global_comment:
        cmd = ["gh", "pr", "comment", args.pr, "--body-file", "-"]
        if args.repo:
            cmd.extend(["-R", args.repo])
        if args.apply:
            _run(cmd, stdin=global_comment)
        else:
            sys.stdout.write("[DRY-RUN] Would run:\n")
            sys.stdout.write(" ".join(cmd) + "\n\n")
            sys.stdout.write(global_comment + "\n\n")

    for comment in inline_comments:
        cmd = [
            "gh",
            "api",
            *([] if not host or host == "github.com" else ["--hostname", host]),
            "-X",
            "POST",
            f"repos/{owner}/{repo_name}/pulls/{pr_number}/comments",
            "-f",
            f"body={comment.body}",
            "-f",
            f"commit_id={head_sha}",
            "-f",
            f"path={comment.path}",
            "-F",
            f"line={comment.line}",
            "-f",
            f"side={comment.side}",
        ]

        if args.apply:
            _run(cmd)
        else:
            sys.stdout.write("[DRY-RUN] Would run:\n")
            sys.stdout.write(" ".join(cmd) + "\n\n")


if __name__ == "__main__":
    main()

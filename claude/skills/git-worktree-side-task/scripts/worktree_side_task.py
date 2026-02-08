#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result


def _repo_root(cwd: Path) -> Path:
    out = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd).stdout.strip()
    return Path(out).resolve()


def _default_start_point(repo_root: Path) -> str:
    result = _run_git(
        ["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"],
        cwd=repo_root,
        check=False,
    )
    candidate = result.stdout.strip()
    return candidate if candidate else "HEAD"


def _default_worktrees_dir(repo_root: Path) -> Path:
    return repo_root.parent / f"{repo_root.name}-worktrees"


def _sanitize_path_fragment(value: str) -> str:
    s = value.strip().replace("/", "__")
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "worktree"


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch_ref: Optional[str]

    @property
    def branch(self) -> Optional[str]:
        if not self.branch_ref:
            return None
        if self.branch_ref.startswith("refs/heads/"):
            return self.branch_ref.removeprefix("refs/heads/")
        return self.branch_ref


def _list_worktrees(repo_root: Path) -> list[WorktreeInfo]:
    out = _run_git(["worktree", "list", "--porcelain"], cwd=repo_root).stdout
    blocks = out.strip().split("\n\n") if out.strip() else []
    result: list[WorktreeInfo] = []
    for block in blocks:
        wt_path: Optional[Path] = None
        branch_ref: Optional[str] = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                wt_path = Path(line.split(" ", 1)[1]).resolve()
            elif line.startswith("branch "):
                branch_ref = line.split(" ", 1)[1].strip()
        if wt_path is not None:
            result.append(WorktreeInfo(path=wt_path, branch_ref=branch_ref))
    return result


def _find_worktree_by_branch(repo_root: Path, branch: str) -> Optional[WorktreeInfo]:
    target_ref = f"refs/heads/{branch}"
    for wt in _list_worktrees(repo_root):
        if wt.branch_ref == target_ref:
            return wt
    return None


def _is_branch_local(repo_root: Path, branch: str) -> bool:
    result = _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_root, check=False)
    return result.returncode == 0


def cmd_list(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    repo_root = _repo_root(cwd)
    for wt in _list_worktrees(repo_root):
        branch = wt.branch or "(detached)"
        print(f"{wt.path}\t{branch}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    repo_root = _repo_root(cwd)

    branch = args.branch.strip()
    if not branch:
        raise ValueError("branch is required")

    existing = _find_worktree_by_branch(repo_root, branch)
    if existing is not None:
        if args.reuse:
            print(str(existing.path))
            return 0
        raise RuntimeError(f"branch already has a worktree: {existing.path}")

    worktrees_dir = Path(args.worktrees_dir).expanduser().resolve() if args.worktrees_dir else _default_worktrees_dir(repo_root)
    start_point = args.from_rev or _default_start_point(repo_root)

    dest = Path(args.path).expanduser().resolve() if args.path else (worktrees_dir / _sanitize_path_fragment(branch))
    if dest.exists():
        raise RuntimeError(f"destination already exists: {dest}")

    worktrees_dir.mkdir(parents=True, exist_ok=True)

    if _is_branch_local(repo_root, branch):
        _run_git(["worktree", "add", str(dest), branch], cwd=repo_root)
    else:
        _run_git(["worktree", "add", "-b", branch, str(dest), start_point], cwd=repo_root)

    print(str(dest))
    return 0


def _is_dirty(worktree_path: Path) -> bool:
    result = _run_git(["status", "--porcelain"], cwd=worktree_path, check=True)
    return bool(result.stdout.strip())


def cmd_cleanup(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    current_root = _repo_root(cwd)

    branch = (args.branch or "").strip() or None
    path = Path(args.path).expanduser().resolve() if args.path else None

    if branch is None and path is None:
        raise ValueError("cleanup requires --branch or --path")

    repo_root = current_root
    target: Optional[WorktreeInfo] = None
    if branch is not None:
        target = _find_worktree_by_branch(repo_root, branch)
        if target is None:
            raise RuntimeError(f"no worktree found for branch: {branch}")
    else:
        assert path is not None
        for wt in _list_worktrees(repo_root):
            if wt.path == path:
                target = wt
                break
        if target is None:
            raise RuntimeError(f"path is not a known worktree of this repo: {path}")

    assert target is not None

    if current_root == target.path:
        raise RuntimeError("cannot remove the current worktree; run cleanup from another worktree of the repo")

    if _is_dirty(target.path) and not args.force:
        raise RuntimeError(f"worktree has uncommitted changes: {target.path} (re-run with --force to remove anyway)")

    remove_args = ["worktree", "remove", str(target.path)]
    if args.force:
        remove_args.insert(2, "--force")
    _run_git(remove_args, cwd=repo_root)
    _run_git(["worktree", "prune"], cwd=repo_root, check=False)

    print(f"removed {target.path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/cleanup side-task worktrees for the current git repo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List worktrees for the current repo")
    p_list.set_defaults(func=cmd_list)

    p_create = sub.add_parser("create", help="Create a new worktree for a side-task branch")
    p_create.add_argument("--branch", required=True, help="Branch name for the side task")
    p_create.add_argument("--reuse", action="store_true", help="If the branch already has a worktree, print its path and exit")
    p_create.add_argument("--from", dest="from_rev", help="Start point for creating a new branch (default: origin/HEAD or HEAD)")
    p_create.add_argument("--worktrees-dir", help="Directory to place worktrees (default: sibling REPO_NAME-worktrees)")
    p_create.add_argument("--path", help="Explicit worktree path (overrides --worktrees-dir)")
    p_create.set_defaults(func=cmd_create)

    p_cleanup = sub.add_parser("cleanup", help="Remove a worktree created for a side task")
    group = p_cleanup.add_mutually_exclusive_group(required=True)
    group.add_argument("--branch", help="Branch name to remove worktree for")
    group.add_argument("--path", help="Worktree path to remove")
    p_cleanup.add_argument("--force", action="store_true", help="Remove even if worktree has uncommitted changes (destructive)")
    p_cleanup.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

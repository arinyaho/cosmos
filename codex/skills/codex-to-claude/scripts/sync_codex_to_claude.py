#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _normalize_name(raw_name: str) -> str:
    name = raw_name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name


def _sanitize_description(raw_description: str) -> str:
    description = raw_description.strip()
    description = re.sub(r"<[^>]*>", "", description)
    description = description.replace("<", "").replace(">", "")
    description = " ".join(description.split())
    return description[:1024].strip()


def _split_frontmatter(markdown: str) -> tuple[Optional[str], str]:
    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, markdown
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter = "".join(lines[1:i])
            body = "".join(lines[i + 1 :])
            return frontmatter, body
    return None, markdown


def _parse_yaml_frontmatter(frontmatter_text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            parsed = yaml.safe_load(frontmatter_text)  # type: ignore[attr-defined]
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    result: dict[str, Any] = {}
    for line in frontmatter_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue
        if raw_value.startswith('"'):
            try:
                result[key] = json.loads(raw_value)
                continue
            except Exception:
                pass
        if raw_value.startswith("'") and raw_value.endswith("'") and len(raw_value) >= 2:
            result[key] = raw_value[1:-1]
        else:
            result[key] = raw_value
    return result


def _derive_description_from_markdown_body(body: str) -> str:
    lines = [ln.rstrip() for ln in body.splitlines()]
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("#"):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1

    paragraph: list[str] = []
    while i < len(lines) and lines[i].strip():
        paragraph.append(lines[i].strip())
        i += 1

    return _sanitize_description(" ".join(paragraph)) or "Exported from ~/.codex/skills"


def _agent_frontmatter(name: str, description: str, model: str) -> str:
    safe_description = _sanitize_description(description)
    safe_description = safe_description.replace("\\", "\\\\").replace('"', '\\"')
    safe_model = model.strip() or "opus"
    return f"---\nname: {name}\ndescription: \"{safe_description}\"\nmodel: {safe_model}\n---\n"


def _rewrite_paths_for_claude(markdown: str) -> str:
    # Claude teammates may not have ~/.codex. Rewrite common SSOT paths to the Claude install path.
    return markdown.replace("~/.codex/skills/", "~/.claude/skills/").replace("~/.codex/skills", "~/.claude/skills")


def _parse_mapping(raw: str) -> tuple[str, str]:
    if "=" in raw:
        left, right = raw.split("=", 1)
    elif ":" in raw:
        left, right = raw.split(":", 1)
    else:
        raise ValueError("mapping must look like src=dst (or src:dst)")
    src = _normalize_name(left)
    dst = _normalize_name(right)
    if not src or not dst:
        raise ValueError("mapping names must include at least one letter or digit")
    return src, dst


@dataclass(frozen=True)
class PlannedWrite:
    kind: str
    src: Optional[Path]
    dst: Path
    note: str


def _remove_tree(path: Path, *, apply: bool) -> None:
    if not apply:
        return
    shutil.rmtree(path)


def _copy_tree(src: Path, dst: Path, *, apply: bool) -> None:
    if not apply:
        return
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".DS_Store",
            ".git",
            ".venv",
            ".pytest_cache",
            "*.pyc",
            "export_to_claude.py",
        ),
    )


def _write_text(path: Path, text: str, *, apply: bool) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_plan(
    src_codex_skills: Path,
    dst_claude: Path,
    *,
    apply: bool,
    overwrite: bool,
    only: str,
    model: str,
    skills_filter: set[str] | None,
    mapping: dict[str, str],
) -> list[PlannedWrite]:
    plan: list[PlannedWrite] = []

    agents_dir = dst_claude / "agents"
    skills_dir = dst_claude / "skills"

    for skill_dir in sorted(p for p in src_codex_skills.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if skill_dir.name == ".system":
            continue

        src_dir_name = _normalize_name(skill_dir.name)
        if skills_filter is not None and src_dir_name not in skills_filter:
            continue

        src_skill_md = skill_dir / "SKILL.md"
        if not src_skill_md.exists():
            plan.append(PlannedWrite("skip", src_skill_md, src_skill_md, "missing SKILL.md"))
            continue

        text = src_skill_md.read_text(encoding="utf-8")
        fm_text, body = _split_frontmatter(text)
        fm = _parse_yaml_frontmatter(fm_text or "")

        raw_name = str(fm.get("name") or src_dir_name or skill_dir.name)
        src_name = _normalize_name(raw_name) or src_dir_name
        if not src_name:
            plan.append(PlannedWrite("skip", src_skill_md, src_skill_md, "could not determine skill name"))
            continue

        dst_name = mapping.get(src_name, src_name)
        dst_name = _normalize_name(dst_name)
        if not dst_name:
            plan.append(PlannedWrite("skip", src_skill_md, src_skill_md, "could not determine destination name"))
            continue

        raw_description = str(fm.get("description") or "")
        description = _sanitize_description(raw_description) or _derive_description_from_markdown_body(body)

        # Claude agent
        if only in ("all", "agent"):
            agent_path = agents_dir / f"{dst_name}.md"
            if agent_path.exists() and not overwrite:
                plan.append(PlannedWrite("skip", src_skill_md, agent_path, "destination exists"))
            else:
                if agent_path.exists() and overwrite:
                    plan.append(PlannedWrite("overwrite-file", src_skill_md, agent_path, "destination exists; will replace"))
                plan.append(PlannedWrite("write-agent", src_skill_md, agent_path, f"skill {src_name} → agent {dst_name} ({model})"))

        # Claude skill dir
        if only in ("all", "skill"):
            dest_skill_dir = skills_dir / dst_name
            dest_skill_md = dest_skill_dir / "SKILL.md"
            if dest_skill_dir.exists() and not overwrite:
                plan.append(PlannedWrite("skip", skill_dir, dest_skill_dir, "destination exists"))
            else:
                if dest_skill_dir.exists() and overwrite:
                    plan.append(PlannedWrite("overwrite-dir", skill_dir, dest_skill_dir, "destination exists; will replace"))
                plan.append(PlannedWrite("copy-dir", skill_dir, dest_skill_dir, f"skill {src_name} → skill dir {dst_name}"))
                plan.append(PlannedWrite("write-skill-md", src_skill_md, dest_skill_md, "strip codex frontmatter"))

        # Store context needed for apply-phase writes in note? Instead, re-parse on apply.
        # Plan is deterministic enough; apply-phase will re-read from src paths.

    if apply:
        agents_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

    return plan


def _apply_plan(plan: list[PlannedWrite], *, apply: bool, overwrite: bool, model: str, mapping: dict[str, str]) -> None:
    for item in plan:
        if item.kind == "skip":
            continue

        if item.kind == "overwrite-dir":
            if overwrite and item.dst.exists():
                _remove_tree(item.dst, apply=apply)
            continue

        if item.kind == "overwrite-file":
            if overwrite and item.dst.exists():
                if apply:
                    item.dst.unlink()
            continue

        if item.kind == "copy-dir" and item.src is not None:
            _copy_tree(item.src, item.dst, apply=apply)
            continue

        if item.kind == "write-skill-md":
            if item.src is None:
                continue
            text = item.src.read_text(encoding="utf-8")
            _, body = _split_frontmatter(text)
            out = _rewrite_paths_for_claude(body.lstrip())
            _write_text(item.dst, out, apply=apply)
            continue

        if item.kind == "write-agent":
            if item.src is None:
                continue
            src_skill_md = item.src
            text = src_skill_md.read_text(encoding="utf-8")
            fm_text, body = _split_frontmatter(text)
            fm = _parse_yaml_frontmatter(fm_text or "")

            raw_name = str(fm.get("name") or src_skill_md.parent.name)
            src_name = _normalize_name(raw_name) or _normalize_name(src_skill_md.parent.name)
            dst_name = mapping.get(src_name, src_name)
            dst_name = _normalize_name(dst_name)

            raw_description = str(fm.get("description") or "")
            description = _sanitize_description(raw_description) or _derive_description_from_markdown_body(body)

            out = _agent_frontmatter(dst_name, description, model) + _rewrite_paths_for_claude(body.lstrip())
            _write_text(item.dst, out, apply=apply)
            continue


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ~/.codex/skills into ~/.claude (agents + skills).")
    parser.add_argument("--src", default="~/.codex/skills", help="Source Codex skills directory (default: ~/.codex/skills).")
    parser.add_argument("--dst", default="~/.claude", help="Destination Claude directory (default: ~/.claude).")
    parser.add_argument("--only", choices=["all", "agent", "skill"], default="all", help="Export only a subset (default: all).")
    parser.add_argument("--skill", action="append", default=[], help="Export only this skill name (repeatable).")
    parser.add_argument("--map", action="append", default=[], help="Name mapping: src=dst (repeatable). Example: pr-reviewer=review.")
    parser.add_argument("--model", default="opus", help="Claude agent model value (default: opus).")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing (default unless --apply).")
    parser.add_argument("--apply", action="store_true", help="Apply changes to destination.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination if it already exists.")
    args = parser.parse_args()

    apply = bool(args.apply) and not bool(args.dry_run)
    src_codex_skills = Path(args.src).expanduser().resolve()
    dst_claude = Path(args.dst).expanduser().resolve()

    if not src_codex_skills.exists():
        _eprint(f"[error] Source not found: {src_codex_skills}")
        return 2
    if apply:
        dst_claude.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, str] = {}
    try:
        for raw in args.map:
            src, dst = _parse_mapping(str(raw))
            mapping[src] = dst
    except ValueError as exc:
        _eprint(f"[error] Invalid --map value: {exc}")
        return 2

    skills_filter: set[str] | None = None
    if args.skill:
        skills_filter = {_normalize_name(s) for s in args.skill if _normalize_name(s)}

    plan = _build_plan(
        src_codex_skills,
        dst_claude,
        apply=apply,
        overwrite=bool(args.overwrite),
        only=str(args.only),
        model=str(args.model),
        skills_filter=skills_filter,
        mapping=mapping,
    )

    creates = [p for p in plan if p.kind in ("copy-dir", "write-agent", "write-skill-md")]
    overwrites = [p for p in plan if p.kind in ("overwrite-dir", "overwrite-file")]
    skips = [p for p in plan if p.kind == "skip"]

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] src={src_codex_skills} dst={dst_claude} only={args.only} model={args.model}")

    for item in plan:
        if item.kind == "skip":
            print(f"- skip: {item.dst} ({item.note})")
        elif item.kind in ("overwrite-dir", "overwrite-file"):
            print(f"- {item.kind}: {item.dst} ({item.note})")
        else:
            src = str(item.src) if item.src is not None else "-"
            print(f"- {item.kind}: {src} -> {item.dst} ({item.note})")

    if not apply:
        print("\nTip: re-run with --apply to write changes.")
        return 0

    if overwrites and not args.overwrite:
        _eprint("[error] internal: overwrite planned without --overwrite")
        return 2

    _apply_plan(plan, apply=apply, overwrite=bool(args.overwrite), model=str(args.model), mapping=mapping)

    print("\nDone:", f"writes={len(creates)}", f"skipped={len(skips)}", f"overwritten={len(overwrites)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

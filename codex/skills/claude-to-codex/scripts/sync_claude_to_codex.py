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


def _format_imported_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        expanded = expanded.resolve()
        home = home.resolve()
    except Exception:
        pass

    if expanded.is_absolute():
        try:
            rel = expanded.relative_to(home)
        except Exception:
            pass
        else:
            rel_text = rel.as_posix()
            if rel_text in ("", "."):
                return "~"
            return f"~/{rel_text}"

    return expanded.as_posix()


def _normalize_skill_name(raw_name: str) -> str:
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


def _frontmatter(name: str, description: str) -> str:
    safe_description = _sanitize_description(description)
    safe_description = safe_description.replace("\\", "\\\\").replace('"', '\\"')
    return f"---\nname: {name}\ndescription: \"{safe_description}\"\n---\n"


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

    return _sanitize_description(" ".join(paragraph)) or "Imported from ~/.claude"


def _agent_description_to_skill_description(agent_description: str) -> str:
    description = agent_description.strip()
    if not description:
        return "Imported Claude agent from ~/.claude/agents into ~/.codex/skills."

    for token in ("Examples:", "Examples", "example:", "<example"):
        idx = description.find(token)
        if idx != -1:
            description = description[:idx]
            break

    description = _sanitize_description(description)
    if description:
        return description
    return "Imported Claude agent from ~/.claude/agents into ~/.codex/skills."


@dataclass(frozen=True)
class PlannedWrite:
    kind: str
    src: Optional[Path]
    dst: Path
    note: str


def _ensure_parent_dir(path: Path, *, apply: bool) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str, *, apply: bool) -> None:
    _ensure_parent_dir(path, apply=apply)
    if not apply:
        return
    path.write_text(text, encoding="utf-8")


def _remove_tree(path: Path, *, apply: bool) -> None:
    if not apply:
        return
    shutil.rmtree(path)


def _copy_tree(src: Path, dst: Path, *, apply: bool) -> None:
    if not apply:
        return
    shutil.copytree(src, dst)


def _index_existing_skills(dst_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not dst_root.exists():
        return index

    for skill_dir in sorted(p for p in dst_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        skill_md = skill_dir / "SKILL.md"
        name = _normalize_skill_name(skill_dir.name)

        if skill_md.exists():
            try:
                text = skill_md.read_text(encoding="utf-8")
            except Exception:
                text = ""
            frontmatter_text, _ = _split_frontmatter(text)
            fm = _parse_yaml_frontmatter(frontmatter_text or "")
            raw_name = str(fm.get("name") or "").strip()
            if raw_name:
                normalized = _normalize_skill_name(raw_name)
                if normalized:
                    name = normalized

        if name:
            index.setdefault(name, skill_dir)

    return index


def _convert_agent_file(
    agent_md: Path,
    dst_root: Path,
    *,
    apply: bool,
    overwrite: bool,
    existing_skills: dict[str, Path],
) -> list[PlannedWrite]:
    text = agent_md.read_text(encoding="utf-8")
    frontmatter_text, body = _split_frontmatter(text)
    fm = _parse_yaml_frontmatter(frontmatter_text or "")

    raw_name = str(fm.get("name") or agent_md.stem)
    raw_description = str(fm.get("description") or "")

    name = _normalize_skill_name(raw_name)
    if not name:
        raise ValueError(f"Could not determine skill name from {agent_md}")

    description = _agent_description_to_skill_description(raw_description)

    dest_dir = existing_skills.get(name, dst_root / name)
    dest_skill_md = dest_dir / "SKILL.md"

    if dest_dir.exists():
        if not overwrite:
            return [PlannedWrite("skip", agent_md, dest_skill_md, "destination exists")]
        return [
            PlannedWrite("overwrite", agent_md, dest_dir, "destination exists; will replace"),
            PlannedWrite("create", agent_md, dest_skill_md, "agent → skill"),
        ]

    return [PlannedWrite("create", agent_md, dest_skill_md, "agent → skill")]


def _convert_skill_dir(
    skill_dir: Path,
    dst_root: Path,
    *,
    apply: bool,
    overwrite: bool,
    existing_skills: dict[str, Path],
) -> list[PlannedWrite]:
    raw_name = skill_dir.name
    name = _normalize_skill_name(raw_name)
    if not name:
        raise ValueError(f"Invalid skill directory name: {skill_dir}")

    src_skill_md = skill_dir / "SKILL.md"
    if not src_skill_md.exists():
        return [PlannedWrite("skip", skill_dir, dst_root / name, "missing SKILL.md")]

    dest_dir = existing_skills.get(name, dst_root / name)
    dest_skill_md = dest_dir / "SKILL.md"

    if dest_dir.exists():
        if not overwrite:
            return [PlannedWrite("skip", skill_dir, dest_dir, "destination exists")]
        return [
            PlannedWrite("overwrite", skill_dir, dest_dir, "destination exists; will replace"),
            PlannedWrite("create", skill_dir, dest_dir, "skill dir → skill dir"),
            PlannedWrite("write", src_skill_md, dest_skill_md, "normalize SKILL.md frontmatter"),
        ]

    src_text = src_skill_md.read_text(encoding="utf-8")
    existing_frontmatter, body = _split_frontmatter(src_text)
    fm = _parse_yaml_frontmatter(existing_frontmatter or "")

    raw_description = str(fm.get("description") or "") or _derive_description_from_markdown_body(body)
    description = _sanitize_description(raw_description) or "Imported from ~/.claude/skills"

    normalized_skill_md = _frontmatter(name, description) + body.lstrip()

    planned = [
        PlannedWrite("create", skill_dir, dest_dir, "skill dir → skill dir"),
        PlannedWrite("write", src_skill_md, dest_skill_md, "normalize SKILL.md frontmatter"),
    ]
    return planned


def _apply_plan(plan: list[PlannedWrite], *, apply: bool, overwrite: bool) -> None:
    for item in plan:
        if item.kind == "skip":
            continue

        if item.kind == "overwrite":
            if overwrite and item.dst.exists():
                _remove_tree(item.dst, apply=apply)
            continue

        if item.kind == "create" and item.src is not None and item.src.is_dir():
            _copy_tree(item.src, item.dst, apply=apply)
            continue

        if item.kind in ("create", "write") and item.dst.name == "SKILL.md":
            if item.src is None:
                continue
            source_text = item.src.read_text(encoding="utf-8") if item.src.is_file() else ""
            if item.note.startswith("agent"):
                frontmatter_text, body = _split_frontmatter(source_text)
                fm = _parse_yaml_frontmatter(frontmatter_text or "")
                raw_name = str(fm.get("name") or item.src.stem)
                raw_description = str(fm.get("description") or "")
                name = _normalize_skill_name(raw_name)
                description = _agent_description_to_skill_description(raw_description)
                header = _frontmatter(name, description)
                imported_note = f"<!-- Imported from {_format_imported_path(item.src)} -->\n\n"
                out = header + imported_note + body.lstrip()
            else:
                existing_frontmatter, body = _split_frontmatter(source_text)
                fm = _parse_yaml_frontmatter(existing_frontmatter or "")
                raw_description = str(fm.get("description") or "") or _derive_description_from_markdown_body(body)
                name = _normalize_skill_name(item.dst.parent.name)
                description = _sanitize_description(raw_description) or "Imported from ~/.claude/skills"
                out = _frontmatter(name, description) + body.lstrip()
            _write_text(item.dst, out, apply=apply)
            continue


def _build_plan(
    src_claude: Path,
    dst_codex_skills: Path,
    *,
    apply: bool,
    overwrite: bool,
    only: str,
) -> list[PlannedWrite]:
    plan: list[PlannedWrite] = []
    existing_skills = _index_existing_skills(dst_codex_skills)

    agents_dir = src_claude / "agents"
    if only in ("all", "agents") and agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            plan.extend(_convert_agent_file(agent_file, dst_codex_skills, apply=apply, overwrite=overwrite, existing_skills=existing_skills))

    skills_dir = src_claude / "skills"
    if only in ("all", "skills") and skills_dir.exists():
        for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            plan.extend(_convert_skill_dir(skill_dir, dst_codex_skills, apply=apply, overwrite=overwrite, existing_skills=existing_skills))

    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ~/.claude agents/skills into ~/.codex/skills")
    parser.add_argument("--src", default="~/.claude", help="Source Claude directory (default: ~/.claude)")
    parser.add_argument("--dst", default="~/.codex/skills", help="Destination Codex skills directory (default: ~/.codex/skills)")
    parser.add_argument("--only", choices=["all", "agents", "skills"], default="all", help="Convert only a subset (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing (default unless --apply)")
    parser.add_argument("--apply", action="store_true", help="Apply changes to destination")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination skill folders if they already exist")
    args = parser.parse_args()

    apply = bool(args.apply) and not bool(args.dry_run)
    src_claude = Path(args.src).expanduser().resolve()
    dst_codex_skills = Path(args.dst).expanduser().resolve()

    if not src_claude.exists():
        _eprint(f"[error] Source not found: {src_claude}")
        return 2

    if apply:
        dst_codex_skills.mkdir(parents=True, exist_ok=True)

    plan = _build_plan(src_claude, dst_codex_skills, apply=apply, overwrite=bool(args.overwrite), only=str(args.only))

    creates = [p for p in plan if p.kind == "create"]
    overwrites = [p for p in plan if p.kind == "overwrite"]
    skips = [p for p in plan if p.kind == "skip"]
    writes = [p for p in plan if p.kind == "write"]

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] src={src_claude} dst={dst_codex_skills}")

    for item in plan:
        if item.kind == "skip":
            print(f"- skip: {item.dst} ({item.note})")
        elif item.kind == "overwrite":
            print(f"- overwrite: {item.dst} ({item.note})")
        else:
            src = str(item.src) if item.src is not None else "-"
            print(f"- {item.kind}: {src} -> {item.dst} ({item.note})")

    if not apply:
        print("\nTip: re-run with --apply to write changes.")
        return 0

    if overwrites and not args.overwrite:
        _eprint("[error] internal: overwrite planned without --overwrite")
        return 2

    _apply_plan(plan, apply=apply, overwrite=bool(args.overwrite))

    print(
        "\nDone:",
        f"created={len(creates)}",
        f"writes={len(writes)}",
        f"skipped={len(skips)}",
        f"overwritten={len(overwrites)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

---
name: sdd-spec-updater
description: "Use when managing GAP IDs or validating doc cross-references: auto-assign next GAP ID, detect duplicates, check broken links, verify terminology consistency."
---

# SDD Spec Updater

## Purpose

Automate repetitive specification-driven development (SDD) tasks: GAP ID management and cross-reference validation across `docs/` trees.

## Features

### 1. GAP ID Auto-Assignment

Scan known-gaps documents, find the highest existing GAP ID, and return the next available ID.

```bash
python3 ~/.claude/skills/sdd-spec-updater/scripts/gap_id.py [--docs-root <path>] [--check-only] [--json]
```

**Default docs root**: `docs/` relative to the current working directory.

**What it does**:
- Scans all `*.md` files under docs root for `GAP-NNN` patterns
- Reports all existing GAP IDs with their source file and line
- Detects duplicate IDs and warns
- Returns the next available ID

**Usage in conversation**:
- "GAP 추가해" -> run the script, get next ID, use it
- "GAP 중복 확인" -> run with `--check-only` flag

### 2. Cross-Reference Checker

Validate markdown cross-references, GAP ID references, and terminology consistency.

```bash
python3 ~/.claude/skills/sdd-spec-updater/scripts/xref_check.py [--docs-root <path>] [--changed-files file1.md file2.md] [--terminology <path>] [--json]
```

**What it checks**:
- Broken relative markdown links (`[text](../path/to/file.md)`)
- GAP ID references to non-existent GAPs (e.g., `GAP-099` referenced but never defined)
- Terminology inconsistencies (configurable via `references/terminology.json`)

**Modes**:
- Full scan: check all files under docs root
- Changed-files mode: check only specified files (useful for PR scope)

## Trigger Phrases

- "이거 스펙에 반영해", "GAP 추가해", "SSOT 업데이트"
- "크로스 레퍼런스 체크", "링크 깨진거 확인"
- "add GAP", "check cross-references", "validate docs links"

## References

- `references/terminology.json`: canonical term dictionary for consistency checks (matching is **case-insensitive**)

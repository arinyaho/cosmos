# Codex DSL Gate

## When this skill should be used
- The user request is ambiguous/unstructured natural language.
- The task could cause unintended side effects (file edits, commands, network/destructive actions).
- You want repeatable execution (same intent → same plan → same constraints).

## Default behavior (2-phase handshake)
1) **Do not execute anything yet.** First, normalize the request into a Task Card (YAML).
2) If any required fields are missing, ask **1–3 clarifying questions** (keep them minimal).
3) Present the final Task Card and ask the user for explicit confirmation:
   - Require one of: `커밋해줘`, `적용해`, `반영해`
4) Only after confirmation, execute strictly within the Task Card constraints.
5) If new risk/ambiguity appears during execution, stop and regenerate the Task Card for re-confirmation.

## Safety defaults
- Default `mode: explore`
- Default `allow_network: false`
- Default `allow_destructive: false`
- Default `files_write: []` (empty whitelist means **no writes**, and no side-effect tool calls)

## Task Card schema (Codex DSL v0.1)
```yaml
mode: explore | commit | lock

intent:
  goal: ""
  success_criteria:
    - ""

scope:
  in_scope:
    - ""
  out_of_scope:
    - ""

inputs:
  context_notes: ""
  files_read:
    - ""
  files_write: []

constraints:
  allow_network: false
  allow_destructive: false
  allowed_tools:
    - shell_command
    - apply_patch

plan:
  - step: ""
    side_effects: none | patch | shell

verification:
  - command: ""

stop_rules:
  - ""

confirm:
  required: true
  phrase: "커밋해줘"
```

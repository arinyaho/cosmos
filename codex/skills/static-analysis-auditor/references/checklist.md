# Static Analysis Checklist

## 1) Async Pipeline Mapping
- Map request → enqueue → worker → storage/DB → status API → caller.
- Identify where status is **set**, **persisted**, and **observed**.
- Confirm which components are in-memory only vs. durable.

## 2) Failure Propagation
- Every external I/O error must update state visible to the caller.
- Flag any `log/continue` without status mutation.
- Ensure failures don’t get stuck in “running” or “pending”.

## 3) Long-Polling/Status APIs
- Verify termination on both **success** and **failure**.
- Ensure timeout path returns meaningful status, not silent retry.
- Make sure failures are not masked by “count-based done” logic.

## 4) External I/O Reliability
- Upload/download paths should have retry/backoff and timeouts.
- Retry must be bounded; include jitter for thundering herd.
- Check idempotency for retries (safe to re-upload or overwrite?).

## 5) Observability & Tests
- Logs should include job_id/request_id and error context.
- Failure-path tests for each boundary (storage, DB, RPC).

## Search Heuristics (rg patterns)
```
rg -n "failed|error" services/internal -S
rg -n "continue" services/internal -S
rg -n "StatusSuccess|JobStatusSuccess" services/internal -S
rg -n "Get.*Status|Status" services/internal -S
rg -n "Upload|Download|PutObject|GetObject" services/internal -S
rg -n "retry|backoff|attempt" services/internal -S
```

## Common Red Flags
- Success set unconditionally after a best-effort upload.
- Status only stored in memory without persistence to DB.
- Polling endpoint uses only “count-based done” without failure path.
- External I/O done inside worker but errors not surfaced to caller.

## 6) Architecture-Specific Checks (example)
- **Distributed state consistency**: job status stored in memory vs DB vs storage; confirm source-of-truth and fallback order.
- **Idempotency**: retries or duplicate requests must be safe; verify keying by request_id/job_id/shard_id.
- **Retry/backoff alignment**: ensure consistent policies across shaper/backend/orchestrator/storage.
- **Partial failure propagation**: storage/network failure must surface to caller and stop downstream success flows.
- **Queue/backpressure**: verify bounded queues, worker semaphores, and avoidance of goroutine leaks.
- **Stale job cleanup**: confirm cleanup for stuck jobs and dangling in-memory states.
- **Contract alignment**: gRPC status vs DB status vs API response should be semantically consistent.
- **Storage consistency**: account for eventual consistency when reading after write.
- **Migration safety**: index/schema changes must be backward compatible on rolling restart.
- **Observability**: logs/metrics must correlate request_id/job_id across services.

## 7) DB State Invariants (shards/searchable ↔ mappings)
Canonical spec:
- `docs/specs/backend/shard-searchable-invariants-v1.md`

Use this section to ensure code paths uphold the invariant (this class of bugs often shows up as **count drift**, not immediate errors).

Search heuristics (rg):
```
rg -n "DeactivatedNodes|DeleteRowInShardNodeMap|Upsert.*shard-node map" services/internal -S
rg -n "UpdateShardSearchable\\(|searchable\\s*=" services/internal -S
rg -n "_shardnodemap|_shard_map" services/internal -S
```

Common red flags:
- Delete from `*_shardnodemap` without flipping `shards.searchable=false`.
- “Searchable rows” computed from `shards` table alone (no join) while deactivation paths exist.

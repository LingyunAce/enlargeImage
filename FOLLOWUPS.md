# Follow-ups

Tech debt and known issues from the initial implementation (2026-06-06). All items below are non-blocking but should be addressed before a production deployment.

## High Priority

### Multi-scale SwinIR runner dict (spec §10)
**Status:** ✅ **Resolved** (commits `f3e0f89` and `33e59c7`). `MultiRunner` class in `backend/app/pipeline/runner.py` dispatches by scale. `backend/run.py` scans `MODEL_DIR/*.pth`, instantiates one `SwinIRRunner` per file, and wires them into a `MultiRunner`. `Pipeline.run` was updated to use `supports_scale()` instead of strict equality. 47 tests pass including a new `test_multi_runner_routes_by_scale`.

### Frontend state stomping during polling
**Status:** Mostly fixed (commit `4a2bf80`). When the user selects a different history item while a job is polling, `setActive` no longer stomps the selected job. However, the disabled state of the Uploader is only based on `active.status === "running"`, not `"queued"`, which can allow a double-submit during the queued window.

**Suggested fix:** Include `"queued"` in the Uploader's `disabled` condition.

### Default `app` is a stub-runner skeleton
**Status:** Implemented (commit `4a2bf80`) but limited. The default `app = create_app()` uses `_StubRunner` which returns zero images. This is fine for the API skeleton and tests, but production must construct a real `SwinIRRunner` with loaded weights and pass it in.

**Suggested fix:** Add a `create_production_app()` factory that loads all available weights and registers runners by scale. Document the difference.

## Medium Priority

### Cache-only reads in `JobManager.get` / `list_recent`
**Status:** Spec §7.3 requires "miss 再查 SQLite" but current code never queries the store on cache miss. `startup_reap_ghosts` materialises the table into the cache so this works after a fresh restart, but a long-lived process with a trimmed cache would silently return stale results.

**Suggested fix:** In `JobManager.get`, if not in cache, query `store.get` and populate the cache. Same for `list_recent`.

### Internal error handler with `trace_id` (spec §8.2)
**Status:** Not implemented. The current code lets FastAPI's default 500 leak. Spec requires a uniform `{"error": "internal", "trace_id": ...}` response and structured logging.

**Suggested fix:** Add an `@app.exception_handler(Exception)` that logs the traceback with a UUID and returns the structured response.

### Global exception handler
**Status:** Related to above. Add request-scoped error handling in middleware or via `app.exception_handler`.

### Frontend test coverage
**Status:** Zero frontend tests. The async state machine in `page.tsx` (upload → poll → history → compare) is non-trivial and would benefit from tests.

**Suggested fix:** Add Vitest + React Testing Library; write at minimum a test for `pollJob` (mocking `getJob`).

### `output_path` and `input_path` in `Job.to_dict()`
**Status:** These fields are leaked to the API response, exposing absolute filesystem paths. Not a security risk (DB is locally controlled) but is info disclosure.

**Suggested fix:** Filter these fields out in the API layer or remove from `to_dict()`.

### Throttled progress writes — test coverage
**Status:** Spec §11.1 explicitly requires a test for "50ms 内连发 100 个 progress → 实际 flush 次数 ≤ 5". The throttling logic exists in `JobManager._flush_loop` but isn't tested.

**Suggested fix:** Add a test that fires 100 progress events in 50ms and asserts ≤ 5 SQLite writes.

### Semaphore ordering test
**Status:** Spec §11.1 requires a test for semaphore=1 with two jobs running sequentially. Not implemented.

**Suggested fix:** Add a test that submits 2 jobs and verifies they run sequentially via timing.

### Delete-of-running-job test
**Status:** The cooperative cancel-then-wait flow in `JobManager.delete` for RUNNING jobs is not exercised by any test.

**Suggested fix:** Add a test that starts a long-running job and calls `delete` mid-run; verify it transitions through CANCELLED and is removed from store + disk.

## Low Priority

### Trim uses private SQLite connection
**Status:** `JobManager.trim` opens its own `sqlite3.connect(self.store.db_path)` and re-implements `DELETE FROM jobs`. `JobStore.delete(jid)` already does this.

**Suggested fix:** Replace with `self.store.delete(j.id)`.

### Oversize uploads are fully buffered before rejection
**Status:** `await file.read()` loads the entire body into memory before the `> 20MB` check fires. A 1 GB upload would consume 1 GB of RAM.

**Suggested fix:** Check `request.headers["content-length"]` first; reject without reading. Or use FastAPI's `max_upload_size` if available.

### 7-day retention of failed jobs' files
**Status:** Spec §8.4 says failed rows keep files for 7 days. `trim` deletes files immediately.

**Suggested fix:** Implement age-based retention; add `failed_at` timestamp and only delete files older than 7 days.

### Sync SQLite writes on the event loop
**Status:** `_run_job` and the flush loop call `store.upsert` synchronously from the event loop. With semaphore=1 and tiny writes, latency is invisible. Will become a bottleneck if semaphore is increased.

**Suggested fix:** Move to `run_in_executor` or use a thread pool for DB I/O.

### Logging
**Status:** Unstructured. No `trace_id`. No request-scoped context.

**Suggested fix:** Add a JSON-formatted logger with request IDs; integrate with FastAPI middleware.

### PNG encoding `optimize=False`
**Status:** Defensible default for speed, but worth a comment explaining the trade-off.

**Suggested fix:** Add a comment in `_encode_png` in `job_manager.py`.

### Type safety: `Job.stage` is `str` server-side
**Status:** `Job.stage` is typed `Optional[str]` (loose) but the API contract expects `StageName` literal values. Drift risk.

**Suggested fix:** Tighten to `Optional[StageName] = None`.

### `_safe_unlink` silently swallows all OSErrors
**Status:** Including `PermissionError` which usually indicates a real problem.

**Suggested fix:** Log at warning level instead of silent.

### `e2e_real_model.py` parametrised on `[4]` only
**Status:** Test name suggests a sweep but only one element.

**Suggested fix:** Parametrise on `[2, 4, 8]` (each skipped individually without weights).

### Inline styles in some components
**Status:** `HistoryList`, `ProgressPanel`, `CompareViewer` use inline styles for grid/borders/colors. Should be in `globals.css` for consistency.

**Suggested fix:** Extract to CSS classes.

### CORS configuration
**Status:** No CORS middleware. The `next.config.js` rewrite handles dev (`:3000` → `:8000`), but for non-rewritten deployments (separate origin), CORS must be enabled.

**Suggested fix:** Add `CORSMiddleware` with configurable allowed origins.

### Hardcoded `localhost:8000` in `next.config.js`
**Status:** No env-var indirection. Fine for dev; will need adjustment for staging/prod.

**Suggested fix:** Use `process.env.BACKEND_URL || "http://localhost:8000"`.

### Makefile / tox / CI config
**Status:** None. README documents separate commands for backend and frontend.

**Suggested fix:** Add a top-level `Makefile` with `make test`, `make lint`, `make dev`.

## Spec Deviations (documented in code)

### SeamBlender: uniform weight, not linear alpha ramp
**Status:** Deviation acknowledged in code. The spec's "linear ramp 0→1 entering overlap, 1→0 exiting overlap" was mathematically broken (produced a near-black seam at tile boundaries), so the implementation uses uniform 1.0 averaging. This is the correct behaviour for always-overlapping tiles from the Tiler.

**Suggested fix:** Update spec §5.3 to describe the actual algorithm. Current implementation is correct; spec text is stale.

### `basicsr` upsampler conditional
**Status:** `build_swinir` uses `nearest+conv` for x4 (Real-World SR) and `pixelshuffle` for x2/x8 (because basicsr's `nearest+conv` branch hard-asserts `upscale == 4`).

**Suggested fix:** Document in spec §12 that real x2/x8 checkpoints would need to come from the Classical SR family.

## Acknowledgements

The initial implementation was completed in a single session using the subagent-driven-development skill. All 21 plan tasks were implemented with TDD; deviations were reviewed and either justified in code or flagged here for follow-up. Final state: 46 backend tests pass + 1 skipped, frontend typecheck and build pass, smoke test (uvicorn + full job lifecycle) works end-to-end.

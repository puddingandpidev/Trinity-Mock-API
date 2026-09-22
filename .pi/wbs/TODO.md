# WBS — Trinity Mock API (dev only)

> One file, current state. This file IS the plan. Read top to bottom, resume from "Next Action".

## Goal
Build a **dev-only mock** of the Team Server REST API defined in `spec.md`
(38 endpoints) so frontend/tooling can be developed against a stable,
seedable API surface. **Not a security tool** — dummy data only.

## Constraints / decisions (agreed)
- Dev-only: in-memory state, no auth, seeded dummy agents/tasks.
- Language: **Python 3 + FastAPI + Uvicorn**, managed with **uv** (venv in
  project root, no Docker).
- "Functionally plausible": command POSTs create tasks that progress
  `pending → running → completed`; fileDownload/upload tasks create
  `activeDownloads` entries that progress and then appear as records in
  `/data/downloads`; checkin refreshes/creates agents.
- Port **8000** by default (env `PORT`/`HOST` override).
- Artifacts (dummy payloads/files) written under `./data/` (gitignored).

## Tasks

### 1. Env setup — DONE (2026-09-15)
- [x] uv installed (`~/.local/bin/uv`, v0.12.15), venv `.venv` (uv 0.12.15,
      fastapi 0.141.0 + uvicorn 0.49.0), `requirements.txt`, `.pi/wbs/bootstrap-env.sh`
      (re-run to recreate venv from scratch), `.gitignore`.
      Server verified serving on 8000.

### 2. Implement mock API (all 38 endpoints) — DONE (2026-09-15)
- [x] `main.py` (single file, stdlib+fastapi only): state module with seeded
      dummy agents/tasks/payloads/downloads/transfers; background worker thread
      (task lifecycle + transfer progress + finalize → download record);
      all endpoints incl. 9 dynamic command routes, checkin, payloads generate,
      downloads list/get/delete, tcp+http listener CRUD, config, login (mock JWT).
      404 `{"error": ...}` for unknown ids; FastAPI default 422 for bad bodies.
      OpenAPI auto at `/docs`, `/openapi.json`.

### 3. Verify (smoke test) — DONE (2026-09-15)
- [x] `smoke_test.py` (stdlib urllib only): **ALL PASS** — 52 checks covering
      all 38 operations: list/detail/create/update/delete, 404 cases, task
      lifecycle (pending→running→completed), fileDownload→activeDownloads
      (name/path/size/received)→data/downloads record, upload→downloads,
      cancelFileDownload, clearQueue, stop, payload generate (+404 bad
      listener), login, teamserverIp, listener CRUD tcp/http.
      OpenAPI count: 31 paths / **38 operations** (spec match).
- [x] Bug found+fixed during verify: `os.path.basename` on Linux doesn't split
      Windows `C:\temp\x` paths → transfer `name` was the full path. Fixed with
      `_base_name()` (normalizes `\\`→`/`).

## Next Action
- **DONE — handoff.** Server running via `nohup` (pid in `server.pid`).
  To restart: `pkill -f '[m]ain.py'` then `.venv/bin/python main.py`.

## Open Questions / assumptions (note in WIP.md)
- Spec's `PUT/DELETE /listeners/{type}` take `?id=N` query param (used `id`).
- `POST /payloads/generate` "returns nothing" → implemented as `200 {}`.
- `GET /tasks/{id}` ambiguity: task id → object; agent id → task list;
  else 404 `{"error": ...}` (spec only pins 404).
- `activeDownloads` `path` (spec) is a full path; used directly as the
  download `path` (no name→path mapping needed).
- `DELETE /data/downloads/{id}` deletes the record; keeps file on disk
  (gitignored dev artifact).

## Blockers
- none

## Log
- 2026-09-15: created plan (env: uv+FastAPI, port 8000, in-memory).
- 2026-09-15: env bootstrap done (uv 0.12.15, .venv, fastapi+uvicorn).
- 2026-09-15: main.py + smoke_test.py implemented; smoke ALL PASS (52/52);
  38 operations verified in OpenAPI. Handoff ready.

# Log

- **2026-09-15** — Environment bootstrap: uv 0.12.15 installed
  (`~/.local/bin/uv`), project venv `.venv` (Python 3.13.11, fastapi 0.141.0,
  uvicorn 0.49.0), `requirements.txt` + `.pi/wbs/bootstrap-env.sh` created.
  Smoke: server serves on :1337.
- **2026-09-15** — Implemented `main.py` (all 38 endpoints, in-memory state,
  seeded dummy data, background worker for task lifecycle + transfers),
  `smoke_test.py` (52 checks), `README.md`.
- **2026-09-15** — Verification: smoke test initially 51/52
  (`tasks.activeDownloads.entry` failed). Root cause: `os.path.basename`
  doesn't split Windows `C:\...` paths on Linux, so transfer `name` was the
  full path. Fixed via `_base_name()` separator normalization. Re-ran:
  **ALL PASS (52/52)**. OpenAPI: 31 paths / 38 operations (spec match).
  Status: handoff ready.

# WIP — Trinity Mock API

**Status: COMPLETE** (2026-09-15). Smoke test ALL PASS (52/52 checks, all 38
operations covered). Server was left running at `http://127.0.0.1:1337`
(pid in `server.pid`) — kill & restart with:

```bash
pkill -f '[m]ain.py'          # careful: don't use -f "main.py" unescaped;
                              # the bracket trick avoids matching your own shell
.venv/bin/python main.py      # or: uv run python main.py
uv run python smoke_test.py   # verify
```

## What was built

```
Trinity-Mock-API/
├── main.py          # mock server — single file, FastAPI
├── smoke_test.py    # smoke test — stdlib only, 52 checks
├── README.md        # usage + endpoint table + behavior notes
├── requirements.txt # fastapi, uvicorn
├── .venv/           # uv-managed (fastapi 0.141.0, uvicorn 0.49.0)
├── .pi/wbs/         # this state (TODO.md, WIP.md, Log.md, bootstrap-env.sh)
└── data/            # generated dummy artifacts (gitignored)
    ├── payloads/    # dummy exe/elf/ps1 "payloads"
    └── uploads/     # dummy agent file downloads per agent id
```

### Endpoints (38 operations / 31 paths — verified against /openapi.json)
- config: `GET /api/v1/config/teamserverIp`, `GET /api/v1/config/status`
- auth: `POST /api/v1/auth/login` (any non-empty creds → mock JWT)
- agents: `GET /api/v1/agents`, `GET /api/v1/agents/{agentId}`,
  `POST /api/v1/agent/checkin` (known uuid → refresh; unknown → register)
- tasks: `GET /api/v1/tasks`, `GET /api/v1/tasks/{taskId|agentId}`,
  `GET /api/v1/tasks/{agentId}/activeDownloads`,
  `DELETE /api/v1/tasks/{agentId}/clearQueue`, `POST /api/v1/tasks/{agentId}/stop`
- commands (9): spawn/{powershell,shell,runAs,run,runU},
  execute/{killProcess,escalate,dotnetAssembly,bof,fileDownload,
  cancelFileDownload,upload}
- payloads: `GET /api/v1/payloads`, `POST /api/v1/payloads/generate`,
  `GET /api/v1/payloads/{payloadId}`
- downloads: `GET /api/v1/data/downloads`, `GET/DELETE /api/v1/data/downloads/{id}`
- listeners: tcp + http, each `GET/POST`, `PUT/DELETE ...?id=N`

### Mock semantics (the "plausibly functional" parts)
- Background worker thread (0.5 s tick):
  tasks `pending → running` (~1 s) `→ completed` (2–6 s); `stop`/
  `clearQueue`/`cancelFileDownload` → `cancelled`.
- `fileDownload`/`upload` create a transfer: visible in `activeDownloads`
  as `{name, path, size, received}` with `received` growing each tick;
  on completion → record appended to `data/downloads` (+ dummy file written
  to `data/uploads/{agentId}/`).
- Seed data: 3 agents (2 Windows, 1 Linux; one admin), 5 tasks (incl. a
  running fileDownload with an active transfer on agent #2), 3 payloads
  (2 tcp-listener, 1 http-listener), 2 download records.
- `POST /payloads/generate`: validates listener id across both types →
  404 `{"error": "listener not found", ...echo}`; success → writes dummy
  artifact (MZ/ELF/ps1 magic) under `data/payloads/`, returns `200 {}`.

### Assumptions made (spec gaps — all documented in README)
1. `PUT/DELETE /api/v1/listeners/{tcp,http}` id passed as `?id=N` query param.
2. `POST /payloads/generate` success → `200 {}` (spec: "returns nothing").
3. `GET /tasks/{id}`: task id → object; agent id → list of that agent's
   tasks; unknown → 404 `{"error": ...}`.
4. `activeDownloads[].path` used verbatim as the `data/downloads` record's
   `path`.
5. `DELETE /data/downloads/{id}` removes the record, keeps the on-disk file.
6. `auth/login` accepts any non-empty username/password (dev mock JWT).
7. Bad JSON body → FastAPI default 422 (spec silent).

## Gotchas / notes for next session
- **uv PATH**: some shells start without `~/.local/bin`; either
  `export PATH="$HOME/.local/bin:$PATH"` or use `.venv/bin/python` directly.
- **pkill trap**: `pkill -f "main.py"` matches your own bash -c command line
  and kills the shell. Use `pkill -f '[m]ain.py'` or kill via `server.pid`.
- **Windows paths on Linux**: `os.path.basename()` doesn't split `\` —
  the mock normalizes separators in `_base_name()` (this was the one
  bug found during verification; keep in mind if you touch path handling).
- Server is stateless across restarts (re-seeds); `data/` accumulates
  dummy files until you `rm -rf data`.
- No Docker, no auth, no persistence — by design (dev-only).

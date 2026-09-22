# Trinity Mock API (dev only)

> ⚠️ **Not a security tool. Not a real C2.** Development/testing only,
> fictional data, unauthenticated — never expose it to an untrusted network.
> See [DISCLAIMER.md](./DISCLAIMER.md).

In-memory mock of the Trinity "Team Server" REST API defined in
[spec.md](./spec.md). **Not a security tool** — used only for local development
of frontend/tooling against a stable, seedable API surface.

- **Stack:** Python 3 + FastAPI + Uvicorn (uv-managed venv, no Docker)
- **State:** in-memory, seeded with dummy agents/tasks/payloads/downloads
  (all IPs, hosts, usernames are fictional RFC 5737 / example-style values)
- **Artifacts:** dummy bytes written under `./data/` (gitignored)

## Quick start

```bash
cd Trinity-Mock-API
uv sync            # once (creates .venv with fastapi + uvicorn)
uv run python main.py
```

Server: `http://127.0.0.1:8000` — interactive docs at `/docs`, OpenAPI at
`/openapi.json`. Override with `HOST` / `PORT` env vars (e.g. `PORT=9090`).

## Smoke test

With the server running in another terminal:

```bash
uv run python smoke_test.py
```

Exercises every one of the 38 endpoints (list/detail/create/update/delete/
error cases, task lifecycle, transfer tracking, payload generation, download
records). Exits non-zero on any failure.

## TeamServer conformance

This mock is a behavioural stand-in for the real Trinity TeamServer. Every one
of the **26 TeamServer operations is matched 1:1** (path, method, request
contract and the typed response fields the Android client deserialises).
Responses are declared with Pydantic `response_model`s (`AgentDTO`,
`HttpListenerDTO`) named after the SwaggerGen schemas, so `openapi.json` is
diffable against the real spec.

```bash
# against the running mock; pass a swagger spec as the 2nd arg (file or URL)
node conformance_check.mjs http://127.0.0.1:8000 /path/to/teamserver-swagger.json
```

The remaining **18 mock-only extensions** exist for the wider Trinity design
(payloads, agent check-in, downloads, legacy settings aliases, mock
convenience routes). **None of them are used by the `devel` Android client**
and none are covered by the TeamServer union backend.

See **[CONFORMANCE.md](./CONFORMANCE.md)** for the full op-by-op table, the
contract fixes, the deliberate deviations kept for the client, and the
TeamServer-side issues observed during verification.

## Endpoints (38)

| Area | Endpoints |
| --- | --- |
| config | `GET /api/v1/config/teamserverIp`, `GET /api/v1/config/status` |
| auth | `POST /api/v1/auth/login` |
| agents | `GET /api/v1/agents`, `GET /api/v1/agents/{agentId}`, `POST /api/v1/agent/checkin` |
| tasks | `GET /api/v1/tasks`, `GET /api/v1/tasks/{taskId\|agentId}`, `GET /api/v1/tasks/{agentId}/activeDownloads`, `DELETE /api/v1/tasks/{agentId}/clearQueue`, `POST /api/v1/tasks/{agentId}/stop` |
| commands (9) | `POST /api/v1/commands/{agentId}/spawn/{powershell,shell,runAs,run,runU}`, `POST /api/v1/commands/{agentId}/execute/{killProcess,escalate,dotnetAssembly,bof,fileDownload,cancelFileDownload,upload}` |
| payloads | `GET /api/v1/payloads`, `POST /api/v1/payloads/generate`, `GET /api/v1/payloads/{payloadId}` |
| downloads | `GET /api/v1/data/downloads`, `GET /api/v1/data/downloads/{id}`, `DELETE /api/v1/data/downloads/{id}` |
| listeners | `GET/POST /api/v1/listeners/tcp`, `PUT/DELETE /api/v1/listeners/tcp?id=`, `GET/POST /api/v1/listeners/http`, `PUT/DELETE /api/v1/listeners/http?id=` |

## Behavior notes (mock semantics)

- **Task lifecycle:** POSTed commands create a `pending` task; a background
  worker flips it to `running` (~1 s), then `completed` (2–6 s later).
  `stop` / `clearQueue` / `cancelFileDownload` set `cancelled`.
- **Transfers:** `execute/fileDownload` and `execute/upload` create a transfer
  visible via `GET /api/v1/tasks/{agentId}/activeDownloads` (fields
  `name, path, size, received`, `received` grows over time); when it completes,
  the task completes and a record appears in `GET /api/v1/data/downloads`
  (with the dummy file written under `data/uploads/{agentId}/`).
  **The spec's `/activeDownloads` field `path` is used as the download's
  `path`** — no extra `name`-to-`path` mapping needed.
- **`GET /api/v1/tasks/{id}`** routes on id type: task id → object,
  agent id → task list, otherwise 404 with `{"error": ...}` (the spec only
  pins down the 404 case).
- **`POST /api/v1/agent/checkin`**: known uuid refreshes the agent's
  last-checkin; unknown uuid registers a new agent.
- **`POST /api/v1/payloads/generate`**: `200 {}` on success (spec: "returns
  nothing"); writes a dummy artifact under `data/payloads/`; 404 with
  `{"error": "listener not found", ...}` for a bad listener id.
- **`DELETE /api/v1/data/downloads/{id}`**: removes the record; the file on
  disk is kept (harmless dev artifact, gitignored).
- **`PUT/DELETE /api/v1/listeners/{tcp,http}?id=N`**: 404 with
  `{"error": "listener not found"}` for unknown ids.
- **`POST /api/v1/auth/login`**: any non-empty username/password → mock JWT
  (non-functional, 3600 s expiry).
- **Errors:** unknown ids → `404 {"error": "..."}`; malformed JSON →
  FastAPI default `422`.
- **Pagination:** `GET /api/v1/agents`, `/api/v1/tasks[/tasks]` and
  `/api/v1/data/downloads` accept optional `?page=&size=` (omit for the full
  list, so existing clients are unaffected).
- **Campaigns:** three fictional campaigns are seeded (Nightfall / Redshift /
  Halcyon) and agents carry `campaignId` 1/2/3 for the Campaign tabs.
- **Listener `agentCount`** is computed from the agents referencing each
  listener, so it stays consistent as agents check in / go offline.
- **Graph summary:** `GET /` returns `graph: {nodes, egressLinks, p2pLinks}`
  for the dashboard graph view.
- **Determinism:** seeded agent/task/payload ids use `uuid5`, so a restart
  reproduces the exact same baseline.
- **Persistence (opt-in):** set `MOCK_PERSIST=1` to dump state to
  `data/state.json` on shutdown and reload it on startup. Off by default so a
  restart always resets to the seeded baseline.
- **Docs tags:** endpoints are grouped in `/docs` by
  payloads · agents · commands · tasks · data · listeners · server · auth · meta.

## Layout

```
Trinity-Mock-API/
├── main.py               # the mock server (single file)
├── smoke_test.py         # 38-endpoint smoke test (stdlib only)
├── conformance_check.mjs # TeamServer path parity + devel contract gates
├── CONFORMANCE.md        # 1:1 mapping, extensions, deviations, evidence
├── spec.md               # the spec (given)
├── requirements.txt      # fastapi, uvicorn
├── .pi/wbs/              # WBS plan + env bootstrap script
└── data/                 # generated dummy artifacts (gitignored)
```

## Licence

[MIT](./LICENSE). This project is not affiliated with, or endorsed by, any
other project or institution.

## Disclaimer

Not a security tool; no offensive capability; fictional data only; must not be
exposed to an untrusted network. Read **[DISCLAIMER.md](./DISCLAIMER.md)** in
full before running or sharing it.

## Attribution

AI-assisted development by the "pi" coding agent — session record in
[AI.log](./AI.log), details in [NOTICE](./NOTICE).

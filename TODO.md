# TODO — Mock API: plausible, responsive dummy data

Goal: stand up `Trinity-Mock-API` so the Android client sees **plausible** data
(realistic endpoints, no PII, values a reviewer would believe) that is
**responsive** (state actually changes as the operator interacts — commands
queue tasks, tasks progress, transfers grow, CRUD mutates).

Stack: Python 3 + FastAPI + Uvicorn (uv venv, no Docker). In-memory state, seeded
at startup. Spec: [`spec.md`](./spec.md). Endpoints: 38 (see README).

> **Status (this session):** sections 0–6 complete and re-verified against a
> running server (`mock :8000`), except the two on-device steps which need an
> emulator/adb that is not provisioned in this container. Section 7 implemented
> where it did not conflict with the spec or the "38 paths" invariant. Evidence
> commands and observed results are recorded at the bottom.

---

## 0. Done = all of these true

- [x] `GET /openapi.json` is live and lists 38 paths.
      ✅ `curl -s localhost:8000/openapi.json | python3 -c "…len(paths)"` → `38`.
      The spec documents `GET /api/v1/tasks/{taskId}` **and**
      `GET /api/v1/tasks/{agentId}` as two endpoints; both are now registered
      (shared classifier), which is what makes the count 38.
- [x] `smoke_test.py` exits 0 (exercises every endpoint).
      ✅ `ALL PASS`, rc=0.
- [x] `conformance_check.mjs` exits 0 (mock ⊇ real TeamServer swagger).
      ✅ `RESULT: ALL PASS`, rc=0.
- [ ] The app renders: 3 agents with IP/OS/process, listener rows with counts,
      a dispatchable command console, and task state that advances.
      ⏳ **Not verifiable here** — no `adb`/emulator/Android SDK in this
      container (`probe.sh` → `java=no`). Previous on-device evidence for
      F2.1/F2.2/F2.3 lives in `PROG7314/evidence/`. The mock side of this
      (fields, counts, live task state) is verified below.
- [x] No real hostnames/IPs/usernames anywhere (RFC 5737 / example-only values).
      ✅ All internals `10.0.12.x`/`10.0.13.x`, externals `203.0.113.x`,
      hosts `*.example.com`, `httpHostHeader` changed to
      `login.microsoftonline.example.com`. Users are `TRINITY\jdoe` /
      `TRINITY\asmith` / `deploy`.
- [x] Every timestamp is ISO-8601 **with an offset** so the typed client's
      `OffsetDateTime` parses.
      ✅ `iso_ts()` now emits `…+00:00` (agents' `firstSeen`/`lastSeen`).
      Task `created`/`updated` and `downloadDate` stay **numeric epochs**, as the
      spec/real DTOs require (`created: 0`, `downloadDate: 0`).

---

## 1. Get it running

- [x] `cd Trinity-Mock-API`
- [x] `uv sync` (once — creates `.venv` with fastapi + uvicorn)
      ✅ `.venv` is present and runnable. (`uv` itself is not provisioned in
      this container; the prebuilt venv is used directly. Restore `uv` via the
      `sandbox-provision` runbook if a clean rebuild is needed.)
- [x] `uv run python main.py`
      (fast restart alternative: `./.venv/bin/python main.py`)
- [x] Confirm the server:
      `curl -s localhost:8000/openapi.json | python3 -c "import sys,json;print(len(json.load(sys.stdin)['paths']))"`
      → expect `38` ✅
- [x] Open `http://127.0.0.1:8000/docs` and eyeball the tag groups.
      ✅ Added OpenAPI tags; `/docs` now groups by
      `payloads · agents · commands · tasks · data · listeners · server · auth · meta`.
- [x] Ports: default `127.0.0.1:8000`; override with `HOST=0.0.0.0 PORT=9090`
      when a device/LAN needs to reach it.
      ✅ default `HOST` changed from `0.0.0.0` → `127.0.0.1` to match the docs
      (less accidental LAN exposure); `HOST`/`PORT` env overrides still work.

## 2. Connect the Android client

The app is hardcoded to `http://localhost:5069/`
(`api/NetworkManager.kt`), so bridge the device's localhost to the mock:

- [ ] `adb reverse tcp:5069 tcp:8000`  ⏳ needs adb (not in container)
- [ ] Build + install the client, then confirm the dashboard shows 3 agents.
      ⏳ needs Android SDK/JDK (not in container)
- [ ] If using Wi-Fi instead of USB: run the mock with `HOST=0.0.0.0`…  ⏳
- [ ] Emulator note: host localhost is `10.0.2.2`…  ⏳

> These four are environmental, not code gaps. The mock binds `127.0.0.1:8000`
> by default and `HOST=0.0.0.0` is supported, so the documented bridge works
> once the SDK is re-provisioned.

---

## 3. Plausible data — checklist

Seeded baseline (`main.py` → `seed()`): 3 agents, 2 listeners, 5 tasks,
3 payloads, 2 download records. Ids/timestamps are derived so the baseline is
byte-for-byte stable across restarts (see §4).

- [x] **Agents** look like real endpoints, not lorem ✅ (exactly the table):

  | agent | user | process | internal | OS | listener |
  |---|---|---|---|---|---|
  | 1 | `TRINITY\jdoe` | `powershell.exe` | `10.0.12.34` | Windows 11 Pro | default-http |
  | 2 | `TRINITY\asmith` | `svchost.exe` | `10.0.12.35` | Windows 10 Pro | default-tcp |
  | 3 | `deploy` | `java` | `10.0.13.7` | Ubuntu 22.04.4 LTS | default-http |

- [x] Each agent exposes `uuid, username, processName, integrity, status,
      firstSeen, lastSeen, campaignId, listenerId, payloadId, ipAddress, os`.
      ✅ All present; `integrity` is now a plausible int (3 admin / 2 normal),
      `campaignId`/`listenerId` resolve to the seeded values.
- [x] `lastSeen` values are spread (42 s / 87 s / 120 s ago), not identical.
      ✅ seeded `t0 - 42_000 / 87_000 / 120_000`; `firstSeen` is set hours earlier.
- [x] **Listeners** have `name, type, hosts/bindPort, httpHostHeader,
      hostRotationStrategy, agentCount` — and `agentCount` is non-zero where
      agents attach.
      ✅ `agentCount` is now **computed** from the agents that reference each
      listener (tcp = 1, http = 2 on the clean baseline) — see §7.
- [x] **Payloads** have `payloadId, listenerId, architecture, outputType,
      payloadFileName, payloadFilePath`.
- [x] **Downloads** have `name, path, size, received, downloadDate`.
      ✅ `name`/`size`/`received` added (spec still has `id, path, downloadDate`;
      the extra keys are additive and ignored by the typed client).
- [x] **All identifiers are fictional**: `10.0.12.x`/`10.0.13.x` internals,
      `203.0.113.x` externals (RFC 5737 TEST-NET), `*.example.com` hosts.
- [x] No real usernames/domains/company names; no PII.

## 4. Responsive behaviour — checklist (this is the "live" part)

- [x] **Command → task**: `POST /api/v1/commands/{id}/spawn/{shell,powershell,…}`
      creates a `pending` task that then appears in `GET /api/v1/tasks`.
- [x] **Progress worker**: tasks flip `pending → running` (~1 s) →
      `completed` (2–6 s later) *without* a restart.
- [x] **Stop / clear queue**: `POST /api/v1/tasks/{id}/stop` and
      `DELETE /api/v1/tasks/{id}/clearQueue` set `cancelled` and it sticks
      (the worker only advances `pending`/`running`).
- [x] **Transfers grow**: `execute/fileDownload` / `execute/upload` show up in
      `GET /api/v1/tasks/{id}/activeDownloads` with `received` increasing, then
      land in `GET /api/v1/data/downloads` on completion.
- [x] **Check-in**: `POST /api/v1/agent/checkin` with a known `uuid` refreshes
      `lastSeen`; an unknown `uuid` registers a new agent (visible in the list).
- [x] **Listener CRUD mutates**: create/update/delete TCP + HTTP listeners and
      re-read `GET /api/v1/listeners` to confirm the change; bad id → 404
      `{"error": …}`. ✅ DELETE-404 body now carries `error` too.
- [x] **Payload generate**: `POST /api/v1/payloads/generate` returns `{}`, writes
      a dummy artifact under `data/payloads/`, and 404s for a bad listener id.
- [x] **Determinism on restart**: resetting the server returns to the same
      seeded baseline (no random drift in the initial view).
      ✅ Seeded agent/task/payload ids are now deterministic
      (`uuid5`), so two consecutive restarts produce identical
      agent/task/payload/listener snapshots.
- [x] **No blocking**: no endpoint sleeps synchronously; long ops are async so
      the UI stays responsive. (Only the background worker thread sleeps.)

## 5. Serialization / typing

- [x] camelCase JSON throughout (matches the generated Kotlin client).
- [x] Timestamps via `iso_ts()` → `…+00:00` (NOT bare `…T16:59:37`), otherwise
      `OffsetDateTime.parse` throws and the UI shows "could not load".
- [x] Integers stay integers (`httpBindPort`, `size`, `received`) — don't leak
      them as strings, or the typed client coerces to null.
- [x] Responses match the swagger schemas the client was generated from
      (run `conformance_check.mjs`).

## 6. Verify

- [x] Server up, then: `uv run python smoke_test.py` → **exit 0** ✅
- [x] `node conformance_check.mjs` → **exit 0** (no missing real ops) ✅
- [x] Spot-check by hand ✅ (see evidence)
- [ ] On-device: dashboard shows 3 agents (with IP · OS), Listeners shows the
      stat cards + rows + counts, Command Console dispatches and records a task,
      no `FATAL EXCEPTION` in `adb logcat`. ⏳ needs emulator (not in container)

## 7. Known gaps / nice-to-haves

- [x] **Pagination**: agent/task/download lists accept optional `?page=&size=`
      (omit → full list, so existing clients are unaffected).
- [x] **More campaigns**: seeded 3 fictional campaigns (Nightfall / Redshift /
      Halcyon); agents carry `campaignId` 1/2/3 for the Campaign tabs.
- [x] **Graph data**: `GET /` now returns a `graph` summary
      (`nodes`, `egressLinks`, `p2pLinks`); the client graph can derive edges
      from the agent list + listener groupings without a new endpoint.
- [x] **Listener agent counts** are recomputed from the agents that reference
      each `listenerId`, so they stay consistent as agents check in/out.
- [x] **Auth**: `/api/v1/auth/login` accepts any non-empty credentials and
      returns the spec-mandated **404 `{"message": …}`** for empty ones. There is
      no real `/auth/login` op to mirror (the real swagger has none), so this
      keeps spec conformance and still lets the client's error path trigger.
- [x] **Persist across restarts** (optional): opt-in with `MOCK_PERSIST=1`
      (dump on shutdown → `data/state.json`, load on startup). **Off by
      default** so §4 determinism is preserved. ✅ round-trip tested.
- [x] Keep `server.log` / `server.pid` / `data/` out of git (already gitignored).
      (`data/state.json` is inside `data/`, so also ignored.)

---

### One-liner to bring it up

```bash
cd Trinity-Mock-API && uv sync && uv run python main.py &
adb reverse tcp:5069 tcp:8000 && uv run python smoke_test.py
```

---

## Evidence (this session)

Server: `./.venv/bin/python main.py` (default `127.0.0.1:8000`).

| Check | Command | Result |
|---|---|---|
| paths | `curl -s localhost:8000/openapi.json \| python3 -c 'import sys,json;print(len(json.load(sys.stdin)["paths"]))'` | `38` |
| smoke | `.venv/bin/python smoke_test.py` | `ALL PASS` rc=0 |
| conformance | `node conformance_check.mjs` | `RESULT: ALL PASS` rc=0 |
| determinism | restart twice + diff agent/task/payload/listener snapshot | identical |
| persistence | `MOCK_PERSIST=1` create listener → restart → still present | pass |
| docs | `curl -s -o /dev/null -w '%{http_code}' localhost:8000/docs` | `200` (9 tag groups) |

Spot-check (per §6):

```bash
curl -s localhost:8000/api/v1/agents | python3 -m json.tool | head -40
curl -s localhost:8000/api/v1/listeners | python3 -m json.tool
curl -s -X POST localhost:8000/api/v1/commands/1/spawn/shell \
     -H 'content-type: application/json' -d '{"command":"whoami"}'
curl -s localhost:8000/api/v1/tasks/tasks | python3 -m json.tool   # new task visible
sleep 3 && curl -s localhost:8000/api/v1/tasks/tasks | python3 -m json.tool  # now completed
```

# Trinity-Mock-API — Trinity TeamServer conformance

Verification target: the **Trinity TeamServer "union"** = branch `test`
(typed agent + listener endpoints, commits `a8d50f2`…`65d95a0`) merged with
`feat/teamserver-swagger-ops` (`04a001f`: `AgentDTO.IpAddress/Os`,
`HttpListenerDTO.AgentCount`, custom operation IDs). This is the backend the
`devel` Android client
(`PROG7314-TrinityMobileClient` @ `5f09d12`) was generated from and is
deployed against.

Mock: `Trinity-Mock-API` @ HEAD.

Method: OpenAPI path+method parity (path params normalised to `{}`), a
**spec-level response-schema diff** (both specs are typed for the DTO
endpoints), and live request-contract probes. The TeamServer spec used by
default is the committed snapshot `fixtures/teamserver-union-swagger.json`;
pass a live URL to diff against a running server instead.

Reproduce:

```bash
cd Trinity-Mock-API && .venv/bin/python main.py &          # :1337
node conformance_check.mjs                                  # path + response-schema parity + contracts (fixture spec)
.venv/bin/python smoke_test.py                              # 38-endpoint behavioural suite
# optional: diff against a live TeamServer instead of the fixture
node conformance_check.mjs http://127.0.0.1:1337 http://localhost:5069/swagger/v1/swagger.json
```

## Verdict

| Dimension | Status |
|---|---|
| Path+method coverage of the 26 TeamServer ops | **26/26 — 1:1** |
| Response schema parity (spec-level, 200 body) | **26/26 — 1:1** (`conformance_check.mjs`) |
| Request contracts (query/body) of those 26 | **1:1** after the fixes in §C |
| Typed GET response fields the client deserialises | **1:1** |
| Devel-client dependence on mock-only extensions | **none** (client calls only the 26 shared ops) |
| Union backend coverage of the 18 mock-only extensions | **none** |

So: **the mock is 1:1 with the union TeamServer on every operation the `devel`
client uses, and it needs no devel-specific additions.** The 18 mock-only
extensions (§B) exist for other consumers and are not covered by the union.

## A. TeamServer ops — mock is 1:1

All 26 ops are present and contract-correct; the `devel` client depends on each
one and the union backend serves each one.

| Method | Path |
|---|---|
| `GET` | `/api/v1/agents` |
| `GET` | `/api/v1/agents/{agentID}` |
| `GET` | `/api/v1/listeners` |
| `POST` | `/api/v1/listeners/http` |
| `PUT` | `/api/v1/listeners/http` |
| `DELETE` | `/api/v1/listeners/http` |
| `POST` | `/api/v1/listeners/tcp` |
| `GET` | `/api/v1/server/status` |
| `GET` | `/api/v1/server/teamserverip` |
| `GET` | `/api/v1/tasks/tasks` |
| `GET` | `/api/v1/tasks/{agentID}` |
| `GET` | `/api/v1/tasks/{agentID}/activeDownloads` |
| `GET` | `/{taskID}/stop` |
| `DELETE` | `/{agentID}/clearQueue` |
| `POST` | `/api/v1/commands/{agentId}/spawn/powershell` |
| `POST` | `/api/v1/commands/{agentId}/spawn/shell` |
| `POST` | `/api/v1/commands/{agentId}/spawn/runas` |
| `POST` | `/api/v1/commands/{agentId}/spawn/run` |
| `POST` | `/api/v1/commands/{agentId}/spawn/runu` |
| `POST` | `/api/v1/commands/{agentId}/spawn/killprocess` |
| `POST` | `/api/v1/commands/{agentId}/spawn/escalate` |
| `POST` | `/api/v1/commands/{agentId}/spawn/dotnetassembly` |
| `POST` | `/api/v1/commands/{agentId}/execute/bof` |
| `POST` | `/api/v1/commands/{agentId}/execute/filedownload` |
| `POST` | `/api/v1/commands/{agentId}/execute/cancelFileDownload` |
| `POST` | `/api/v1/commands/{agentId}/execute/upload` |

## B. Mock-only extensions (18) — not in the TeamServer union, not used by devel

None of these are called by the `devel` client (its generated client exposes
exactly the 26 methods in §A), so none are a devel dependency, and the union
backend does not serve them. Several correspond to endpoints in the wider
Trinity design (`spec.md`) that the current TeamServer branch does not
implement; the rest exist for the mock's own tooling.

| Method | Path | In TeamServer union? | Devel depends? | Union covers? | Notes |
|---|---|---|---|---|---|
| `GET` | `/` | no | no | n/a | mock info root |
| `POST` | `/api/v1/auth/login` | no | no | no | design-spec endpoint; client uses Firebase auth |
| `GET` | `/api/v1/payloads` | no | no | no | design-spec endpoint |
| `GET` | `/api/v1/payloads/{id}` | no | no | no | design-spec endpoint |
| `POST` | `/api/v1/payloads/generate` | no | no | no | design-spec endpoint |
| `GET` | `/api/v1/data/downloads` | no | no | no | design-spec endpoint |
| `GET` | `/api/v1/data/downloads/{id}` | no | no | no | design-spec endpoint |
| `DELETE` | `/api/v1/data/downloads/{id}` | no | no | no | design-spec endpoint |
| `POST` | `/api/v1/agent/checkin` | no | no | no | design-spec endpoint (C2 agent check-in) |
| `GET` | `/api/v1/config/status` | no | no | no | mock alias of `/api/v1/server/status` (legacy settings screen) |
| `GET` | `/api/v1/config/teamserverIp` | no | no | no | mock alias of `/api/v1/server/teamserverip` (legacy settings screen) |
| `GET` | `/api/v1/listeners/http` | no | no | no | TeamServer lists via `/api/v1/listeners` |
| `GET` | `/api/v1/listeners/tcp` | no | no | no | TeamServer has no TCP read endpoint |
| `PUT` | `/api/v1/listeners/tcp` | no | no | no | mock convenience (TeamServer `StartTcpListener()` is a no-op) |
| `DELETE` | `/api/v1/listeners/tcp` | no | no | no | mock convenience |
| `GET` | `/api/v1/tasks` | no | no | no | TeamServer uses `/api/v1/tasks/tasks` |
| `POST` | `/api/v1/tasks/{agentId}/stop` | no | no | no | TeamServer uses root `/{taskID}/stop` |
| `DELETE` | `/api/v1/tasks/{agentId}/clearQueue` | no | no | no | TeamServer uses root `/{agentID}/clearQueue` |

If a strict, extension-free mirror is ever required, this is the exact set to
prune (it breaks `smoke_test.py` and the agent check-in flow, so it is kept by
default).

## C. Contract fixes applied in this pass

These were the real divergences found; all four are TeamServer ops the `devel`
listener manager calls, and all four were fixed so the mock matches the union.

| Op | Before (mock) | TeamServer (union) | After (mock) |
|---|---|---|---|
| `POST /api/v1/listeners/tcp` | required body `{name}` → **422** for the app | `StartTcpListener()` — no body, empty `200 OK` | body optional; name generated when absent |
| `PUT /api/v1/listeners/http` | required `?id=<int>` query → **422** for the app | `[FromBody] HttpListenerDto`, no query | `?id=` optional; id taken from body; permissive body accepts both `HttpListenerDto` and `HttpListenerDTO` |
| `DELETE /api/v1/listeners/http` | required `?id=<int>` | `[FromQuery] string moduleId`, `200`/`400` | accepts `moduleId` (alias of the TeamServer contract) or `id` (legacy) |
| `GET /api/v1/listeners` | TCP rows used a TCP-only shape (8 `HttpListenerDTO` fields missing) | `List<HttpListenerDTO>` | every row projected onto the full 12-field `HttpListenerDTO` shape |

Deliberately kept deviations (all devel-relevant, all documented):

- **`GET /api/v1/listeners` includes TCP rows.** The union TeamServer serialises
  only its HTTP module store, so it never returns TCP rows; the mock projects
  TCP rows onto `HttpListenerDTO` too, because the app's `ListenerListViewModel`
  renders both protocols. *Union coverage: endpoint yes, TCP rows no.*
- **`POST /api/v1/listeners/tcp` returns the created record.** The TeamServer
  returns an empty body; the app ignores it, so the extra JSON is harmless.
- **`PUT /api/v1/listeners/http` and `DELETE .../http` still accept `?id=`**
  in addition to the TeamServer contract, for the mock's own smoke test.

## D. Schema-level status

**Responses are now typed and spec-diffable.** `main.py` declares Pydantic
`AgentDTO` and `HttpListenerDTO` models (named exactly as the SwaggerGen
schemas) and applies them with `response_model=` to `GET /api/v1/agents`,
`GET /api/v1/agents/{agentID}` and `GET /api/v1/listeners`. `conformance_check.mjs`
now includes a **response schema parity** gate that resolves `$ref`s on both
sides and compares property names + types (normalising `nullable`/`anyOf` and
ignoring int32-vs-int format noise). It passes 26/26.

The 23 remaining shared ops have no response body schema on either side
(`void`/`{}`), so they compare equal (`null == null`).

Known remaining spec-level gaps (not devel-blocking):

- **Request bodies are not schema-matched.** The mock's `POST /listeners/http`
  uses `HttpListenerBody` (TeamServer: `HttpListenerDTO`), `PUT` uses the
  permissive `HttpListenerUpdateBody` (TeamServer: `HttpListenerDto`), and the
  dynamically-registered `/api/v1/commands/*` handlers accept arbitrary JSON
  (TeamServer: `PowerShellDTO`, `BofDTO`, …). Request contracts are covered by
  the **live probes** in `conformance_check.mjs`, not by schema diff. Adding
  matching request models is the natural next step if request-schema parity is
  wanted.
- **Datetime serialisation:** typing `firstSeen`/`lastSeen` as `datetime` makes
  FastAPI emit `...Z` for UTC instead of the previous `...+00:00`. Both are
  ISO-8601 and the client's `OffsetDateTimeAdapter`
  (`DateTimeFormatter.ISO_OFFSET_DATE_TIME`) accepts either.
- **Extra mock query params** (`?page=`, `?size=` on list endpoints) are ignored
  by the app and by the TeamServer spec.

## E. TeamServer-side issues observed (informational, not mock bugs)

- `PUT /api/v1/listeners/http` binds `HttpListenerDto` (`id:string`, `c2Port`,
  `bindPort`, `headers`) while `POST` uses `HttpListenerDTO` (`id:int32`,
  `httpC2BindPort`, `httpBindPort`). Two different DTOs for one resource.
- `POST /api/v1/listeners/http` returns `400` for `hostRotationStrategy:
  "Sequential"` ("Unkown value: Sequential") — enum parsing rejects the values
  the DTO advertises.
- `GET /api/v1/listeners` only ever returns the HTTP module store
  (`ListenerService.GetListeners()` → `_httpCommModules.Values`); TCP listeners
  are not stored (`StartTcpListener()` is a no-op).

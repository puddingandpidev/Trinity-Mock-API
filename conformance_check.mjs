#!/usr/bin/env node
// Conformance check: the Mock API must expose every operation (METHOD + path
// skeleton) of the REAL Trinity TeamServer, and must honour the request
// contracts of the operations the `devel` Android client calls.
//
// Path parameters are normalised ({x} -> :p) because parameter names differ.
// Method+path parity is checked against a TeamServer swagger spec; the three
// listener-manager contracts and the typed listener/agent response fields are
// probed live against the running mock.
//
// Usage: node conformance_check.mjs [mockBaseUrl] [realSwaggerPathOrUrl]
//   mockBaseUrl           default http://127.0.0.1:1337
//   realSwagger           default fixtures/teamserver-union-swagger.json (a snapshot of the
//                         Trinity TeamServer "union" spec); override with a file path or an
//                         http(s):// URL (e.g. http://localhost:5069/swagger/v1/swagger.json),                         or the REAL_SWAGGER env var.
// Exit code 0 = path parity + contracts pass, 1 = divergences.
//
// See CONFORMANCE.md for the full op-by-op mapping and the documented
// mock-only extensions.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const mockBase = process.argv[2] || "http://127.0.0.1:1337";
const realSwagger = process.argv[3] || process.env.REAL_SWAGGER
  || path.join(here, "fixtures", "teamserver-union-swagger.json");

// HttpListenerDTO property set (TeamServer spec) — every listener row must carry all of these.
const HTTP_LISTENER_DTO_KEYS = [
  "id", "name", "type", "hosts", "httpC2BindPort", "httpBindPort",
  "userAgent", "httpHostHeader", "hostRotationStrategy", "maxRetryStrategy",
  "agentCount", "error",
];

const norm = (p) => p.replace(/\{[^}]+\}/g, ":p");

async function loadMockSpec() {
  const res = await fetch(`${mockBase}/openapi.json`);
  if (!res.ok) throw new Error(`mock /openapi.json -> ${res.status}`);
  return res.json();
}

async function loadRealSpec() {
  if (/^https?:\/\//.test(realSwagger)) {
    const res = await fetch(realSwagger);
    if (!res.ok) throw new Error(`${realSwagger} -> ${res.status}`);
    return res.json();
  }
  return JSON.parse(readFileSync(realSwagger, "utf8"));
}

function opsOf(spec) {
  const ops = new Set();
  for (const [p, item] of Object.entries(spec.paths)) {
    for (const m of Object.keys(item)) {
      if (["get", "put", "post", "delete", "patch"].includes(m)) ops.add(`${m.toUpperCase()} ${norm(p)}`);
    }
  }
  return ops;
}

// Canonical, name-agnostic description of an OpenAPI schema, for spec-level diffing.
// Returns null for an untyped/empty schema. `nullable` (3.0) and `anyOf [T, null]` (3.1)
// are normalised to T; integer `format` differences are ignored (int32 vs none); only
// date/time formats are kept so temporal fields still have to match.
function canon(spec, sch, depth = 0) {
  if (depth > 8 || !sch || Object.keys(sch).length === 0) return null;
  if (sch.$ref) {
    const name = sch.$ref.split("/").pop();
    const node = spec.components?.schemas?.[name] || {};
    const props = {};
    for (const k of Object.keys(node.properties || {}).sort()) props[k] = canon(spec, node.properties[k], depth + 1);
    return { ref: name, props };
  }
  if (Array.isArray(sch.anyOf)) {
    const nonNull = sch.anyOf.filter((x) => x.type !== "null");
    if (nonNull.length === 1) return canon(spec, nonNull[0], depth + 1);
    return { anyOf: nonNull.map((x) => canon(spec, x, depth + 1)) };
  }
  if (sch.type === "array") return { array: canon(spec, sch.items, depth + 1) };
  if (sch.type === "object" || sch.properties) {
    const props = {};
    for (const k of Object.keys(sch.properties || {}).sort()) props[k] = canon(spec, sch.properties[k], depth + 1);
    return { object: props };
  }
  if (sch.type) {
    const temporal = ["date-time", "date", "time"].includes(sch.format) ? sch.format : null;
    return { type: sch.type, format: temporal };
  }
  return null;
}

function responseSchema(spec, op) {
  const r = op?.responses?.["200"] || op?.responses?.["201"];
  return canon(spec, r?.content?.["application/json"]?.schema);
}

function opByKey(spec, method, normPath) {
  for (const [p, item] of Object.entries(spec.paths)) {
    if (norm(p) !== normPath) continue;
    const op = item[method.toLowerCase()];
    if (op) return op;
  }
  return null;
}

async function probe(method, urlPath, body) {
  const res = await fetch(`${mockBase}${urlPath}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? (["POST", "PUT"].includes(method) ? undefined : undefined) : JSON.stringify(body),
  });
  let json = null;
  try { json = await res.json(); } catch { /* empty body */ }
  return { status: res.status, json };
}

const fails = [];
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${ok || !detail ? "" : `  <-- ${detail}`}`);
  if (!ok) fails.push(name);
};

const mockSpec = await loadMockSpec();
const realSpec = await loadRealSpec();
const realOps = opsOf(realSpec);
const mockOps = opsOf(mockSpec);

console.log(`# mock-vs-real TeamServer conformance (${realOps.size} real ops, ${mockOps.size} mock ops)`);
console.log("## path + method parity");
for (const op of [...realOps].sort()) check(op, mockOps.has(op), "MISSING in mock");

console.log("## response schema parity (spec-level, 200 body)");
for (const op of [...realOps].sort()) {
  const [method, npath] = op.split(" ");
  const real = responseSchema(realSpec, opByKey(realSpec, method, npath));
  const mock = responseSchema(mockSpec, opByKey(mockSpec, method, npath));
  const ok = JSON.stringify(real) === JSON.stringify(mock);
  check(`${op} response schema`, ok, `real=${JSON.stringify(real)} mock=${JSON.stringify(mock)}`);
}

console.log("## listener-manager request contracts (devel client)");
// POST /api/v1/listeners/tcp — the app sends NO body.
const tcp = await probe("POST", "/api/v1/listeners/tcp");
check("POST /api/v1/listeners/tcp (no body)", tcp.status < 300, `got ${tcp.status}`);

// PUT /api/v1/listeners/http — the app sends the HttpListenerDto body, no query param.
const created = await probe("POST", "/api/v1/listeners/http", {
  name: "conformance-http", type: "http", hosts: ["127.0.0.1"],
  httpC2BindPort: 443, httpBindPort: 8080, hostRotationStrategy: "Sequential",
  maxRetryStrategy: "Exponential",
});
const httpId = created.json && (created.json.id ?? created.json.Id);
check("POST /api/v1/listeners/http (create for probe)", created.status < 300 && httpId != null,
  `got ${created.status}`);

if (httpId != null) {
  const put = await probe("PUT", "/api/v1/listeners/http", {
    id: String(httpId), name: "conformance-http-updated", c2Port: 443, bindPort: 8080,
    userAgent: "", headers: {}, hosts: ["127.0.0.1"],
  });
  check("PUT /api/v1/listeners/http (body only, no query)", put.status < 300 && put.status !== 422,
    `got ${put.status}`);

  // DELETE /api/v1/listeners/http?moduleId=<id> — the app sends moduleId as a query param.
  const del = await probe("DELETE", `/api/v1/listeners/http?moduleId=${httpId}`);
  check("DELETE /api/v1/listeners/http?moduleId=", del.status < 300 && del.status !== 422,
    `got ${del.status}`);
}

console.log("## typed response fields (devel client deserialises these)");
const listeners = await probe("GET", "/api/v1/listeners");
const rows = Array.isArray(listeners.json) ? listeners.json : [];
check("GET /api/v1/listeners -> list", listeners.status < 300 && Array.isArray(listeners.json),
  `got ${listeners.status}`);
if (rows.length) {
  const bad = rows.filter((r) => HTTP_LISTENER_DTO_KEYS.some((k) => !(k in r)));
  check("GET /api/v1/listeners rows carry all HttpListenerDTO keys", bad.length === 0,
    `${bad.length}/${rows.length} rows missing keys`);
}
const agents = await probe("GET", "/api/v1/agents");
if (agents.status < 300 && Array.isArray(agents.json) && agents.json.length) {
  const need = ["id", "uuid", "username", "processName", "integrity", "status",
    "firstSeen", "lastSeen", "campaignId", "listenerId", "payloadId", "ipAddress", "os"];
  const bad = agents.json.filter((a) => need.some((k) => !(k in a)));
  check("GET /api/v1/agents rows carry all AgentDTO keys", bad.length === 0,
    `${bad.length}/${agents.json.length} rows missing keys`);
}

const mockOnly = [...mockOps].filter((op) => !realOps.has(op)).sort();
console.log(`## mock-only extensions (${mockOnly.length}, documented in CONFORMANCE.md)`);
for (const op of mockOnly) console.log(`  EXT ${op}`);

console.log(fails.length === 0 ? "RESULT: ALL PASS" : `RESULT: ${fails.length} FAILURES: ${fails.join(", ")}`);
process.exit(fails.length === 0 ? 0 : 1);

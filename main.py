#!/usr/bin/env python
"""Trinity Team Server — mock REST API (dev only, in-memory).

Implements all 38 endpoints from spec.md, seeded with plausible dummy data.
Stateful enough to be "functionally plausible":
  * command POSTs enqueue tasks that progress pending -> running -> completed
  * execute/fileDownload + execute/upload tasks drive "transfers" that land as
    records in /api/v1/data/downloads (files written under ./data/uploads)
  * GET /api/v1/tasks/{agentId}/activeDownloads shows in-progress transfers
  * POST /api/v1/agent/checkin refreshes an existing agent or registers a new one
  * listener CRUD mutates state; /payloads/generate writes a dummy artifact
Run:  uv run python main.py      (or: uv run uvicorn main:app)
"""
from __future__ import annotations

import base64
import json
import os
import random
import re
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ------------------------------------------------------------------ paths/time
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
PAYLOAD_DIR = os.path.join(DATA_DIR, "payloads")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
for _d in (DATA_DIR, PAYLOAD_DIR, UPLOAD_DIR):
    os.makedirs(_d, exist_ok=True)

STATE_FILE = os.path.join(DATA_DIR, "state.json")
# Opt-in state persistence; off by default so a restart always resets to the
# seeded baseline (deterministic initial view). Set MOCK_PERSIST=1 to survive a bounce.
PERSIST = os.environ.get("MOCK_PERSIST", "").lower() in ("1", "true", "yes")

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
LOCK = threading.RLock()


def now_ms() -> int:
    return int(time.time() * 1000)


def fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def iso_ts(ms: int) -> str:
    """ISO-8601 date-time with UTC offset (spec: date-time -> client OffsetDateTime)."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _dummy_bytes(output_type: str) -> bytes:
    if output_type in ("exe", "dll", "service"):
        return b"MZ" + random.randbytes(8192)
    if output_type == "elf":
        return b"\x7fELF" + random.randbytes(4096)
    if output_type == "shellcode":
        return b"\x90\x90" + random.randbytes(2048)
    if output_type == "ps1":
        return b"# trinity mock stager (dev only)\nWrite-Host 'trinity mock payload'\n"
    return random.randbytes(1024)


def _fake_jwt(sub: str) -> str:
    def b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(
        json.dumps({"sub": sub, "iss": "trinity-mock-api", "exp": int(time.time()) + 3600}).encode()
    )
    return f"{header}.{payload}.{b64(secrets.token_bytes(32))}"


def _stable_uuid(seed: str) -> str:
    """Deterministic id so the seeded baseline is identical across restarts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"trinity-mock/{seed}"))


# ------------------------------------------------------------------------ state
class State:
    def __init__(self) -> None:
        self.tcp_listeners: dict[int, dict] = {}
        self.http_listeners: dict[int, dict] = {}
        self.next_listener_id = 1
        self.agents: dict[str, dict] = {}
        self.next_agent_id = 1
        self.tasks: dict[str, dict] = {}
        self.payloads: dict[str, dict] = {}
        self.downloads: dict[int, dict] = {}
        self.next_download_id = 1
        self.transfers: dict[str, list[dict]] = {}
        # Campaign groupings used by the Campaign X/Y/Z tabs (id -> record).
        self.campaigns: dict[int, dict] = {}

    def to_dict(self) -> dict:
        return {
            "tcp_listeners": self.tcp_listeners,
            "http_listeners": self.http_listeners,
            "next_listener_id": self.next_listener_id,
            "agents": self.agents,
            "next_agent_id": self.next_agent_id,
            "tasks": self.tasks,
            "payloads": self.payloads,
            "downloads": self.downloads,
            "next_download_id": self.next_download_id,
            "transfers": self.transfers,
            "campaigns": self.campaigns,
        }

    def load(self, d: dict) -> None:
        self.tcp_listeners = {int(k): v for k, v in d["tcp_listeners"].items()}
        self.http_listeners = {int(k): v for k, v in d["http_listeners"].items()}
        self.next_listener_id = d["next_listener_id"]
        self.agents = d["agents"]
        self.next_agent_id = d["next_agent_id"]
        self.tasks = d["tasks"]
        self.payloads = d["payloads"]
        self.downloads = {int(k): v for k, v in d["downloads"].items()}
        self.next_download_id = d["next_download_id"]
        self.transfers = d["transfers"]
        self.campaigns = {int(k): v for k, v in d.get("campaigns", {}).items()}

    def _agent(self, *, pid, process, user, is_admin, computer, host, internal,
               external, osname, version, charset, session, listener, port,
               note, last_checkin, sleep, first_seen=None, listener_id=None,
               campaign_id=None, agent_id=None, alive=True):
        agent_id = agent_id or str(uuid.uuid4())
        self.agents[agent_id] = {
            "id": self.next_agent_id, "agentId": agent_id, "pid": pid,
            "process": process, "user": user,
            "firstSeen": last_checkin if first_seen is None else first_seen,
            "isAdmin": is_admin, "computer": computer, "host": host,
            "internal": internal, "external": external, "os": osname,
            "version": version, "charset": charset,
            "systemArch": "AMD64", "beaconArch": "AMD64", "session": session,
            "listener": listener, "listener_id": listener_id, "port": port,
            "note": note, "alive": alive, "campaign_id": campaign_id,
            "lastCheckinTime": last_checkin,
            "sleep": {"sleep": sleep[0], "jitter": sleep[1]},
        }
        self.next_agent_id += 1
        return agent_id

    def _task(self, agent_id, command, status, created, updated, finish_at=None,
              task_id=None):
        t = {
            "taskId": task_id or str(uuid.uuid4()), "agentId": agent_id,
            "taskCommand": command,
            "user": self.agents[agent_id]["user"], "created": created, "updated": updated,
            "taskStatus": status, "_finish_at": finish_at,
        }
        self.tasks[t["taskId"]] = t
        return t

    def _payload(self, listener_id, guardrails, arch, exit_fn, syscall, out_type,
                 filename, payload_id=None):
        pid = payload_id or str(uuid.uuid4())
        path = os.path.join(PAYLOAD_DIR, filename)
        with open(path, "wb") as f:
            f.write(_dummy_bytes(out_type))
        self.payloads[pid] = {
            "payloadId": pid, "listenerId": str(listener_id),
            "useListenerGuardRails": guardrails, "architecture": arch,
            "exitFunction": exit_fn, "systemCallMethod": syscall,
            "outputType": out_type, "payloadFileName": filename,
            "payloadFilePath": path,
        }
        return pid

    def _download(self, path, date_ms, content: bytes | None = None):
        fid = self.next_download_id
        self.next_download_id += 1
        if content is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(content)
        size = len(content) if content is not None else 0
        self.downloads[fid] = {
            "id": fid, "name": os.path.basename(path), "path": path,
            "size": size, "received": size, "downloadDate": date_ms,
        }
        return fid

    def seed(self) -> None:
        t0 = now_ms()

        # Campaigns (fictional) so agents group into Campaign X/Y/Z tabs.
        self.campaigns = {
            1: {"id": 1, "name": "Operation Nightfall", "status": "active"},
            2: {"id": 2, "name": "Operation Redshift", "status": "active"},
            3: {"id": 3, "name": "Operation Halcyon", "status": "paused"},
        }

        tcp = {
            "id": self.next_listener_id,
            "name": "default-tcp",
            "type": "tcp",
            "port": 8080,
            "localHostOnly": False,
            "guardRails": {"ipAddress": "10.0.0.1", "userName": "Administrator",
                           "serverName": "SRV-DC01", "domain": "trinity.local"},
        }
        self.next_listener_id += 1
        self.tcp_listeners[tcp["id"]] = tcp

        http = {
            "id": self.next_listener_id,
            "name": "default-http",
            "type": "http",
            "hosts": ["updates.trinity-sec.example.com",
                      "login.microsoftonline.example.com"],
            "httpC2BindPort": 443,
            "httpBindPort": 443,
            "userAgent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
            "httpHostHeader": "login.microsoftonline.example.com",
            "hostRotationStrategy": "Sequential",
            "maxRetryStrategy": "Exponential",
            "guardRails": {"ipAddress": "10.0.0.1", "userName": "",
                           "serverName": "", "domain": "trinity.local"},
        }
        self.next_listener_id += 1
        self.http_listeners[http["id"]] = http

        a1 = self._agent(
            pid=4920, process="powershell.exe", user="TRINITY\\jdoe", is_admin=True,
            computer="WIN-JDOE-01", host="jdoe-ws", internal="10.0.12.34",
            external="203.0.113.24", osname="Windows 11 Pro",
            version="Windows 11 Pro (Build 26100.1)", charset="windows-1252",
            session="RDP-Tcp#0", listener="default-http", listener_id=http["id"],
            campaign_id=1, port=443,
            note="finance dept", last_checkin=t0 - 42_000,
            first_seen=t0 - 6 * 3_600_000, sleep=(60, 25),
            agent_id=_stable_uuid("agent/jdoe"),
        )
        a2 = self._agent(
            pid=7716, process="svchost.exe", user="TRINITY\\asmith", is_admin=False,
            computer="WIN-ASM-02", host="asmith-lt", internal="10.0.12.35",
            external="203.0.113.25", osname="Windows 10 Pro",
            version="Windows 10 Pro (Build 19045.3803)", charset="windows-1252",
            session="Console", listener="default-tcp", listener_id=tcp["id"],
            campaign_id=2, port=8080,
            note="", last_checkin=t0 - 87_000,
            first_seen=t0 - 20 * 3_600_000, sleep=(30, 15),
            agent_id=_stable_uuid("agent/asmith"),
        )
        a3 = self._agent(
            pid=31337, process="java", user="deploy", is_admin=False,
            computer="srv-deploy-01", host="srv-deploy-01", internal="10.0.13.7",
            external="203.0.113.30", osname="Ubuntu 22.04.4 LTS",
            version="Ubuntu 22.04.4 LTS (Kernel 5.15.0-105-generic)", charset="UTF-8",
            session="pts/0", listener="default-http", listener_id=http["id"],
            campaign_id=3, port=443,
            note="ci runner", last_checkin=t0 - 120_000,
            first_seen=t0 - 30 * 3_600_000, sleep=(120, 30),
            agent_id=_stable_uuid("agent/deploy"),
        )

        self._task(a1, "spawn/powershell", "completed", t0 - 3_600_000,
                   t0 - 3_594_000, task_id=_stable_uuid("task/a1-spawn-pwsh"))
        self._task(a1, "spawn/powershell", "cancelled", t0 - 1_800_000,
                   t0 - 1_799_000, task_id=_stable_uuid("task/a1-spawn-pwsh-cancel"))
        self._task(a2, "execute/fileDownload", "completed", t0 - 2_700_000,
                   t0 - 2_695_000, task_id=_stable_uuid("task/a2-dl-done"))
        rt = self._task(a2, "execute/fileDownload", "running", t0 - 8_000, t0 - 7_000,
                        finish_at=t0 + 15_000,
                        task_id=_stable_uuid("task/a2-dl-active"))
        self._task(a3, "spawn/shell", "pending", t0 - 1_000, t0 - 1_000,
                   task_id=_stable_uuid("task/a3-shell"))

        self.transfers[a2] = [{
            "name": "sysnative.dll",
            "path": os.path.join(UPLOAD_DIR, a2, "sysnative.dll"),
            "size": 512 * 1024,
            "received": 128 * 1024,
            "_taskId": rt["taskId"],
        }]

        self._payload("2", True, "windows/x64", "winhttp", "SysWhidCall", "exe",
                      "trinity_winhttp.exe", payload_id=_stable_uuid("payload/winhttp"))
        self._payload("1", False, "windows/x64", "winhttp", "WhidCall", "ps1",
                      "stager.ps1", payload_id=_stable_uuid("payload/stager"))
        self._payload("2", False, "linux/x64", "http", "DirectSyscall", "elf",
                      "trinity_linux", payload_id=_stable_uuid("payload/linux"))

        self._download(os.path.join(UPLOAD_DIR, a1, "win.ini"), t0 - 7_200_000,
                       content=b"[fonts]\n[extensions]\n[mru]\n[files]\n")
        self._download(os.path.join(UPLOAD_DIR, a2, "sam"), t0 - 1_800_000,
                       content=random.randbytes(64 * 1024))


STATE = State()
STATE.seed()

# ------------------------------------------------------------------------ views
AGENT_LIST_KEYS = ["agentId", "pid", "process", "user", "isAdmin", "computer", "host",
                  "internal", "external", "os", "systemArch", "beaconArch", "listener",
                  "note", "alive", "lastCheckinTime", "lastCheckinMs",
                  "lastCheckinFormatted", "sleep"]


def agent_detail_view(a: dict) -> dict:
    # Real TeamServer AgentDTO shape (camelCase, SwaggerGen output).
    return {
        "id": a["id"],
        "uuid": a["agentId"],
        "username": a["user"],
        "processName": a["process"],
        "integrity": 3 if a.get("isAdmin") else 2,
        "status": "Active" if a["alive"] else "Diconnected",
        "firstSeen": iso_ts(a["firstSeen"]),
        "lastSeen": iso_ts(a["lastCheckinTime"]),
        "campaignId": a.get("campaign_id"),
        "listenerId": a.get("listener_id"),
        "payloadId": 1,
        "ipAddress": a["internal"],
        "os": a["os"],
    }


def agent_list_view(a: dict) -> dict:
    return agent_detail_view(a)


def task_list_view(t: dict) -> dict:
    return {"taskId": t["taskId"], "id": t["agentId"], "taskCommand": t["taskCommand"],
            "user": t["user"], "created": t["created"], "updated": t["updated"],
            "taskStatus": t["taskStatus"]}


def task_detail_view(t: dict) -> dict:
    return {"taskId": t["taskId"], "agentId": t["agentId"],
            "taskCommand": t["taskCommand"], "user": t["user"],
            "created": t["created"], "updated": t["updated"],
            "taskStatus": t["taskStatus"]}


# ------------------------------------------------------------------ response DTOs
# Named exactly as the TeamServer SwaggerGen schemas so the mock's openapi.json is
# schema-diffable against the real spec. Types mirror
# TeamServer/Trinity.Shared/DTOs (int32 -> int, nullable -> Optional).
class AgentDTO(BaseModel):
    id: int = 0
    uuid: str | None = None
    username: str | None = None
    processName: str | None = None
    integrity: int | None = None
    status: str | None = None
    firstSeen: datetime | None = None
    lastSeen: datetime | None = None
    campaignId: int | None = None
    listenerId: int = 0
    payloadId: int = 0
    ipAddress: str | None = None
    os: str | None = None


class HttpListenerDTO(BaseModel):
    id: int = 0
    name: str | None = None
    type: str | None = None
    hosts: list[str] | None = None
    httpC2BindPort: int = 0
    httpBindPort: int = 0
    userAgent: str | None = None
    httpHostHeader: str | None = None
    hostRotationStrategy: str | None = None
    maxRetryStrategy: str | None = None
    agentCount: int = 0
    error: str | None = None


def _paginate(items: list, page: int | None, size: int | None) -> list:
    """Optional ?page=&size= slicing; returns the whole list when omitted."""
    if page is None or size is None or size <= 0:
        return items
    start = max(0, (page - 1) * size)
    return items[start:start + size]


# ----------------------------------------------------------------------- worker
def _finalize_transfer(st: State, tr: dict) -> None:
    path = tr["path"]
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(random.randbytes(min(tr["size"], 8 * 1024 * 1024)))
    fid = st.next_download_id
    st.next_download_id += 1
    st.downloads[fid] = {
        "id": fid, "name": tr.get("name", os.path.basename(path)), "path": path,
        "size": tr["size"], "received": tr["size"], "downloadDate": now_ms(),
    }


def _worker_loop(st: State) -> None:
    while True:
        time.sleep(0.5)
        with LOCK:
            now = now_ms()
            for t in st.tasks.values():
                s = t["taskStatus"]
                if s == "pending" and now >= t["created"] + 800:
                    t["taskStatus"] = "running"
                    t["updated"] = now
                    t["_finish_at"] = now + random.randint(2000, 6000)
                elif s == "running" and t.get("_finish_at") and now >= t["_finish_at"]:
                    t["taskStatus"] = "completed"
                    t["updated"] = now
            for agent_id in list(st.transfers.keys()):
                still: list[dict] = []
                for tr in st.transfers[agent_id]:
                    if tr["received"] < tr["size"]:
                        step = max(64 * 1024, tr["size"] // random.randint(4, 8))
                        tr["received"] = min(tr["size"], tr["received"] + step)
                    if tr["received"] >= tr["size"]:
                        _finalize_transfer(st, tr)
                    else:
                        still.append(tr)
                st.transfers[agent_id] = still


# -------------------------------------------------------------------------- app
@asynccontextmanager
async def lifespan(_app: FastAPI):
    if PERSIST and os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                STATE.load(json.load(f))
        except Exception:
            STATE.seed()
    th = threading.Thread(target=_worker_loop, args=(STATE,), daemon=True)
    th.start()
    try:
        yield
    finally:
        if PERSIST:
            with LOCK:
                tmp = STATE_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(STATE.to_dict(), f, indent=2)
                os.replace(tmp, STATE_FILE)


app = FastAPI(
    title="Trinity Team Server (mock)",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "payloads", "description": "Agent payload generation and artifacts."},
        {"name": "agents", "description": "Registered agents and their check-in endpoint."},
        {"name": "commands", "description": "Command dispatch; each POST enqueues a task."},
        {"name": "tasks", "description": "Task queue, transfers, stop and clear-queue."},
        {"name": "data", "description": "Exfiltrated / downloaded file records."},
        {"name": "listeners", "description": "TCP and HTTP C2 listeners (CRUD)."},
        {"name": "server", "description": "Team server config, status and aliases."},
        {"name": "auth", "description": "Mock operator login."},
        {"name": "meta", "description": "Service metadata and dashboard graph summary."},
    ],
)


async def _json_body(request: Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@app.get("/")
def root():
    with LOCK:
        counts: dict = {}
        for a in STATE.agents.values():
            lid = a.get("listener_id")
            counts[lid] = counts.get(lid, 0) + 1
        nodes = len(STATE.agents)
        p2p = sum(c * (c - 1) // 2 for c in counts.values())
    return {"service": "trinity-mock-api", "spec": "spec.md", "docs": "/docs",
            "port": PORT,
            # summary for the dashboard Graph View: agent nodes + link counts
            "graph": {"nodes": nodes, "egressLinks": nodes, "p2pLinks": p2p}}


# ---- payloads ---------------------------------------------------------------
class PayloadGenBody(BaseModel):
    listenerId: str = ""
    useListenerGuardRails: bool = False
    architecture: str = "windows/x64"
    exitFunction: str = "winhttp"
    systemCallMethod: str = "WhidCall"
    outputType: str = "exe"
    payloadFileName: str = "payload"


@app.get("/api/v1/payloads")
def list_payloads():
    with LOCK:
        return list(STATE.payloads.values())


@app.post("/api/v1/payloads/generate")
def generate_payload(body: PayloadGenBody):
    try:
        lid: int | None = int(str(body.listenerId))
    except (TypeError, ValueError):
        lid = None
    with LOCK:
        listener = (STATE.tcp_listeners.get(lid) or STATE.http_listeners.get(lid)) \
            if lid is not None else None
        if listener is None:
            return JSONResponse(
                {
                    "listenerId": body.listenerId,
                    "useListenerGuardRails": body.useListenerGuardRails,
                    "architecture": body.architecture,
                    "exitFunction": body.exitFunction,
                    "systemCallMethod": body.systemCallMethod,
                    "outputType": body.outputType,
                    "payloadFileName": body.payloadFileName,
                    "error": "listener not found",
                },
                status_code=404,
            )
        pid = str(uuid.uuid4())
        filename = body.payloadFileName or "payload"
        path = os.path.join(PAYLOAD_DIR, filename)
        with open(path, "wb") as f:
            f.write(_dummy_bytes(body.outputType))
        STATE.payloads[pid] = {
            "payloadId": pid, "listenerId": str(lid),
            "useListenerGuardRails": body.useListenerGuardRails,
            "architecture": body.architecture, "exitFunction": body.exitFunction,
            "systemCallMethod": body.systemCallMethod, "outputType": body.outputType,
            "payloadFileName": filename, "payloadFilePath": path,
        }
    return {}


@app.get("/api/v1/payloads/{payload_id}")
def get_payload(payload_id: str):
    with LOCK:
        p = STATE.payloads.get(payload_id)
    if p is None:
        return JSONResponse({"error": f"payload '{payload_id}' not found"}, status_code=404)
    return p


# ---- agents -------------------------------------------------------------------
class CheckinBody(BaseModel):
    action: str = "checkin"
    uuid: str
    ips: list[str] = []
    external_ip: str = ""
    os: str = ""
    host: str = ""
    process_name: str = ""
    pid: int = 0
    architecture: str = ""
    motherboard: str = ""
    ram: int = 0
    disk_size: int = 0
    free_disk: int = 0
    cpu_count: int = 0
    mac: str = ""
    domain: str = ""
    integrity_level: int = 0
    user: str = ""
    users: list[str] = []


@app.get("/api/v1/agents", response_model=list[AgentDTO])
def list_agents(page: int | None = None, size: int | None = None):
    with LOCK:
        items = [agent_list_view(a) for a in STATE.agents.values()]
        return _paginate(items, page, size)


@app.get("/api/v1/agents/{agentID}", response_model=AgentDTO)
def get_agent(agentID: str):
    """Real swagger: GET /api/v1/agents/{agentID} (agentID is int). Accept int id or uuid."""
    with LOCK:
        a = None
        if agentID.isdigit():
            for v in STATE.agents.values():
                if v.get("id") == int(agentID):
                    a = v
                    break
        else:
            a = STATE.agents.get(agentID)
    if a is None:
        return JSONResponse({"error": f"agent '{agentID}' not found"}, status_code=404)
    return agent_detail_view(a)


@app.post("/api/v1/agent/checkin")
def checkin(body: CheckinBody):
    now = now_ms()
    with LOCK:
        a = STATE.agents.get(body.uuid)
        if a is None:
            listener_name, port, listener_id = "", 0, None
            if STATE.http_listeners:
                h = next(iter(STATE.http_listeners.values()))
                listener_name, port = h["name"], h.get("httpBindPort", 443)
                listener_id = h["id"]
            elif STATE.tcp_listeners:
                c = next(iter(STATE.tcp_listeners.values()))
                listener_name, port = c["name"], c.get("port", 8080)
                listener_id = c["id"]
            windows = "windows" in (body.os or "").lower()
            STATE.agents[body.uuid] = {
                "id": STATE.next_agent_id, "agentId": body.uuid, "pid": body.pid,
                "firstSeen": now,
                "process": body.process_name or "unknown",
                "user": body.user, "isAdmin": body.integrity_level >= 0x3000,
                "computer": body.host or f"HOST-{body.uuid[:8]}",
                "host": body.host, "internal": body.ips[0] if body.ips else "",
                "external": body.external_ip, "os": body.os, "version": body.os,
                "charset": "windows-1252" if windows else "UTF-8",
                "systemArch": "AMD64", "beaconArch": "AMD64", "session": "",
                "listener": listener_name, "listener_id": listener_id,
                "port": port, "note": "", "campaign_id": None,
                "alive": True, "lastCheckinTime": now,
                "sleep": {"sleep": 60, "jitter": 30},
            }
            STATE.next_agent_id += 1
        else:
            a["lastCheckinTime"] = now
            a["alive"] = True
            if body.pid:
                a["pid"] = body.pid
            if body.process_name:
                a["process"] = body.process_name
            if body.ips:
                a["internal"] = body.ips[0]
            if body.external_ip:
                a["external"] = body.external_ip
            if body.os:
                a["os"] = body.os
                a["version"] = body.os
            if body.host:
                a["host"] = body.host
    return {"action": body.action, "id": body.uuid, "status": "success"}


# ---- tasks ----------------------------------------------------------------------
@app.get("/api/v1/tasks")
def list_tasks(page: int | None = None, size: int | None = None):
    with LOCK:
        ts = sorted(STATE.tasks.values(), key=lambda t: t["created"], reverse=True)
        items = [task_list_view(t) for t in ts]
        return _paginate(items, page, size)


# Real TeamServer path (swagger: GET /api/v1/tasks/tasks) — same payload.
app.get("/api/v1/tasks/tasks")(list_tasks)


def _resolve_agent(agent_id: str):
    """Resolve an agent by UUID or by its integer id (both are accepted)."""
    a = STATE.agents.get(agent_id)
    if a is not None:
        return a
    if str(agent_id).isdigit():
        for v in STATE.agents.values():
            if v.get("id") == int(agent_id):
                return v
    return None


def _task_or_agent_dispatch(seg: str):
    with LOCK:
        t = STATE.tasks.get(seg)
        if t is not None:
            return task_detail_view(t)
        a = _resolve_agent(seg)
        if a is not None:
            uid = a["agentId"]
            ts = sorted((x for x in STATE.tasks.values() if x["agentId"] == uid),
                        key=lambda t: t["created"], reverse=True)
            return [task_list_view(t) for t in ts]
    return JSONResponse({"error": f"task or agent '{seg}' not found"}, status_code=404)


# The spec lists GET /api/v1/tasks/{taskId} and GET /api/v1/tasks/{agentId} as
# two documented endpoints; both share one classifier because either id is a UUID.
@app.get("/api/v1/tasks/{taskId}")
def get_task_by_id(taskId: str):
    return _task_or_agent_dispatch(taskId)


@app.get("/api/v1/tasks/{agentId}")
def get_tasks_by_agent(agentId: str):
    return _task_or_agent_dispatch(agentId)


@app.get("/api/v1/tasks/{agent_id}/activeDownloads")
def active_downloads(agent_id: str):
    with LOCK:
        a = _resolve_agent(agent_id)
        if a is None:
            return JSONResponse({"error": f"agent '{agent_id}' not found"},
                                status_code=404)
        return [{"name": tr["name"], "path": tr["path"], "size": tr["size"],
                 "received": tr["received"]}
                for tr in STATE.transfers.get(a["agentId"], [])]


@app.delete("/api/v1/tasks/{agent_id}/clearQueue")
def clear_queue(agent_id: str):
    with LOCK:
        a = _resolve_agent(agent_id)
        if a is None:
            return JSONResponse(
                {"command": "clearQueue", "message": f"agent '{agent_id}' not found",
                 "taskId": ""}, status_code=404)
        uid = a["agentId"]
        n = 0
        for t in STATE.tasks.values():
            if t["agentId"] == uid and t["taskStatus"] == "pending":
                t["taskStatus"] = "cancelled"
                t["updated"] = now_ms()
                n += 1
    return {"command": "clearQueue", "message": f"cancelled {n} pending task(s)",
            "taskId": ""}


# Real TeamServer shape: DELETE /{agentID}/clearQueue at root level.
app.delete("/{agent_id}/clearQueue")(clear_queue)


@app.post("/api/v1/tasks/{agent_id}/stop")
async def stop_task(agent_id: str, request: Request):
    body = await _json_body(request)
    tid = str(body.get("taskId", ""))
    with LOCK:
        a = _resolve_agent(agent_id)
        if a is None:
            return JSONResponse({"command": "stop",
                                 "message": f"agent '{agent_id}' not found",
                                 "taskId": tid}, status_code=404)
        t = STATE.tasks.get(tid)
        if t is None or t["agentId"] != a["agentId"] \
                or t["taskStatus"] not in ("pending", "running"):
            return JSONResponse({"command": "stop",
                                 "message": "task not found or not active",
                                 "taskId": tid}, status_code=404)
        t["taskStatus"] = "cancelled"
        t["updated"] = now_ms()
    return {"command": "stop", "message": "task stopped", "taskId": tid}


# Real TeamServer shape: GET /{taskID}/stop at root level (no /api/v1 prefix).
@app.get("/{task_id}/stop")
async def stop_task_root(task_id: str):
    with LOCK:
        t = STATE.tasks.get(task_id)
        if t is None or t["taskStatus"] not in ("pending", "running"):
            return JSONResponse({"command": "stop",
                                 "message": "task not found or not active",
                                 "taskId": task_id}, status_code=404)
        t["taskStatus"] = "cancelled"
        t["updated"] = now_ms()
    return {"command": "stop", "message": "task stopped", "taskId": task_id}


# ---- commands -------------------------------------------------------------------
def _base_name(raw: str, fallback: str) -> str:
    """Basename that understands Windows paths regardless of host OS."""
    p = str(raw).replace("\\", "/")
    return os.path.basename(p) or fallback


def _handle_command(kind: str, name: str, agent_id: str, body: dict):
    cmd = f"{kind}/{name}"
    now = now_ms()
    with LOCK:
        agent = _resolve_agent(agent_id)
        if agent is None:
            return JSONResponse({"command": cmd,
                                 "message": f"agent '{agent_id}' not found",
                                 "taskId": ""}, status_code=404)
        uid = agent["agentId"]
        if name == "cancelFileDownload":
            tid = str(body.get("taskId", ""))
            t = STATE.tasks.get(tid)
            if t is None or t["agentId"] != uid \
                    or t["taskStatus"] not in ("pending", "running"):
                return JSONResponse(
                    {"command": cmd, "message": "no active file download to cancel",
                     "taskId": tid}, status_code=404)
            t["taskStatus"] = "cancelled"
            t["updated"] = now
            STATE.transfers[uid] = [tr for tr in STATE.transfers.get(uid, [])
                                    if tr.get("_taskId") != tid]
            return {"command": cmd, "message": "file download cancelled",
                    "taskId": tid}
        transfer = None
        if name == "filedownload":
            fname = _base_name(body.get("path", "download.bin"), "download.bin")
            transfer = {"name": fname,
                        "path": os.path.join(UPLOAD_DIR, uid, fname),
                        "size": random.randint(512 * 1024, 8 * 1024 * 1024),
                        "received": 0}
        elif name == "upload":
            fname = _base_name(body.get("path", "upload.bin"), "upload.bin")
            transfer = {"name": fname,
                        "path": os.path.join(UPLOAD_DIR, uid, fname),
                        "size": random.randint(256 * 1024, 4 * 1024 * 1024),
                        "received": 0}
        t = {"taskId": str(uuid.uuid4()), "agentId": uid,
             "taskCommand": cmd, "user": agent["user"],
             "created": now, "updated": now, "taskStatus": "pending",
             "_finish_at": None}
        if transfer is not None:
            transfer["_taskId"] = t["taskId"]
            STATE.transfers.setdefault(uid, []).append(transfer)
        STATE.tasks[t["taskId"]] = t
    return {"command": cmd, "message": "task created", "taskId": t["taskId"]}


# Exact real-TeamServer command names (swagger: /api/v1/commands/{agentId}/...).
COMMAND_SPECS = {
    "spawn": ["powershell", "shell", "runas", "run", "runu",
              "killprocess", "escalate", "dotnetassembly"],
    "execute": ["bof", "filedownload", "cancelFileDownload", "upload"],
}
for _kind, _names in COMMAND_SPECS.items():
    for _name in _names:
        def _make(kind=_kind, name=_name):
            async def handler(agent_id: str, request: Request):
                body = await _json_body(request)
                return _handle_command(kind, name, agent_id, body)
            handler.__name__ = f"command_{kind}_{name}"
            return handler
        app.add_api_route(f"/api/v1/commands/{{agent_id}}/{_kind}/{_name}",
                         _make(), methods=["POST"])


# ---- data/downloads ---------------------------------------------------------------
@app.get("/api/v1/data/downloads")
def list_downloads(page: int | None = None, size: int | None = None):
    with LOCK:
        items = [STATE.downloads[k] for k in sorted(STATE.downloads)]
        return _paginate(items, page, size)


@app.get("/api/v1/data/downloads/{did}")
def get_download(did: int):
    with LOCK:
        d = STATE.downloads.get(did)
    if d is None:
        return JSONResponse({"message": f"download {did} not found"}, status_code=404)
    if not os.path.exists(d["path"]):
        return {"bytes": base64.b64encode(b"").decode()}
    with open(d["path"], "rb") as f:
        return {"bytes": base64.b64encode(f.read()).decode()}


@app.delete("/api/v1/data/downloads/{did}")
def delete_download(did: int):
    with LOCK:
        d = STATE.downloads.pop(did, None)
    if d is None:
        return JSONResponse({"error": f"download {did} not found"}, status_code=404)
    return {}


def _agent_count(listener_id: int) -> int:
    """Live count of agents attached to a listener (kept consistent with agents)."""
    return sum(1 for a in STATE.agents.values()
               if a.get("listener_id") == listener_id)


def _coerce_id(value) -> "int | None":
    """TeamServer identifiers are loose: HttpListenerDTO.id is int32, HttpListenerDto.id
    is a string moduleId. Accept either and pull the first integer out of a string."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def _http_dto(rec: dict, agent_count: int = 0) -> dict:
    """Project any listener record onto the TeamServer HttpListenerDTO shape.

    Guarantees every HttpListenerDTO property key is present so a generated client
    (Gson) never sees a missing field, regardless of listener protocol.
    """
    return {
        "id": rec.get("id"),
        "name": rec.get("name", ""),
        "type": rec.get("type", "http"),
        "hosts": list(rec.get("hosts") or []),
        "httpC2BindPort": int(rec.get("httpC2BindPort") or rec.get("c2Port")
                              or rec.get("port") or 0),
        "httpBindPort": int(rec.get("httpBindPort") or rec.get("bindPort") or 0),
        "userAgent": rec.get("userAgent", ""),
        "httpHostHeader": rec.get("httpHostHeader", ""),
        "hostRotationStrategy": rec.get("hostRotationStrategy", ""),
        "maxRetryStrategy": rec.get("maxRetryStrategy", ""),
        "agentCount": agent_count,
        "error": rec.get("error"),
    }


# TeamServer: GET /api/v1/listeners serialises its HTTP module store as HttpListenerDTO.
# Mock extension (documented in CONFORMANCE.md): TCP rows are included too, projected
# onto the same HttpListenerDTO shape, because the app renders both protocols.
@app.get("/api/v1/listeners", response_model=list[HttpListenerDTO])
def list_all_listeners():
    with LOCK:
        recs = ([STATE.tcp_listeners[k] for k in sorted(STATE.tcp_listeners)] +
                [STATE.http_listeners[k] for k in sorted(STATE.http_listeners)])
        return [_http_dto(r, _agent_count(r["id"])) for r in recs]


# ---- listeners ---------------------------------------------------------------------
class GuardRails(BaseModel):
    ipAddress: str = ""
    userName: str = ""
    serverName: str = ""
    domain: str = ""


class TcpListenerBody(BaseModel):
    # Optional: the TeamServer's POST /api/v1/listeners/tcp takes no body
    # (ListenerController.StartTcpListener()); the app sends no body, the smoke
    # test does. A name is generated when omitted.
    name: str | None = None
    type: str = "tcp"
    port: int = 8080
    localHostOnly: bool = False
    guardRails: GuardRails = GuardRails()


class HttpListenerBody(BaseModel):
    name: str
    type: str = "http"
    hosts: list[str] = []
    httpC2BindPort: int = 443
    httpBindPort: int = 443
    userAgent: str = ""
    httpHostHeader: str = ""
    hostRotationStrategy: str = "Sequential"
    maxRetryStrategy: str = "Exponential"
    guardRails: GuardRails = GuardRails()


class HttpListenerUpdateBody(BaseModel):
    """Permissive body for PUT /api/v1/listeners/http.

    The TeamServer binds PUT to `HttpListenerDto` (id:string, c2Port, bindPort,
    headers) while POST uses `HttpListenerDTO` (id:int32, httpC2BindPort,
    httpBindPort). Accept both so the app's generated HttpListenerDto body works.
    """
    id: str | None = None
    name: str | None = None
    type: str | None = None
    hosts: list[str] | None = None
    httpC2BindPort: int | None = None
    httpBindPort: int | None = None
    userAgent: str | None = None
    httpHostHeader: str | None = None
    hostRotationStrategy: str | None = None
    maxRetryStrategy: str | None = None
    c2Port: int | None = None
    bindPort: int | None = None
    headers: dict | None = None
    error: str | None = None
    guardRails: GuardRails | None = None


@app.get("/api/v1/listeners/tcp")
def list_tcp():
    with LOCK:
        return [{**STATE.tcp_listeners[k], "agentCount": _agent_count(k)}
                for k in sorted(STATE.tcp_listeners)]


@app.post("/api/v1/listeners/tcp")
def post_tcp(body: TcpListenerBody | None = None):
    # TeamServer signature: StartTcpListener() -> Ok() (no body, empty 200).
    with LOCK:
        lid = STATE.next_listener_id
        STATE.next_listener_id += 1
        data = body.model_dump(exclude_none=True) if body is not None else {}
        rec = {
            "id": lid,
            "name": data.get("name") or f"tcp-{lid}",
            "type": data.get("type", "tcp"),
            "port": data.get("port", 8080),
            "localHostOnly": data.get("localHostOnly", False),
            "guardRails": data.get("guardRails") or GuardRails().model_dump(),
        }
        STATE.tcp_listeners[lid] = rec
        return {**rec, "agentCount": 0}


@app.put("/api/v1/listeners/tcp")
def put_tcp(body: TcpListenerBody, id: int):
    with LOCK:
        rec = STATE.tcp_listeners.get(id)
        if rec is None:
            return JSONResponse({**body.model_dump(exclude_none=True), "error": "listener not found"},
                                status_code=404)
        rec.update(body.model_dump(exclude_none=True))
        rec["id"] = id
        return {**rec, "agentCount": _agent_count(id)}


@app.delete("/api/v1/listeners/tcp")
def del_tcp(id: int):
    with LOCK:
        rec = STATE.tcp_listeners.pop(id, None)
    if rec is None:
        return JSONResponse({"error": "listener not found"}, status_code=404)
    return {}


@app.get("/api/v1/listeners/http")
def list_http():
    with LOCK:
        return [{**STATE.http_listeners[k], "agentCount": _agent_count(k)}
                for k in sorted(STATE.http_listeners)]


@app.post("/api/v1/listeners/http")
def post_http(body: HttpListenerBody):
    with LOCK:
        lid = STATE.next_listener_id
        STATE.next_listener_id += 1
        rec = {"id": lid, **body.model_dump()}
        STATE.http_listeners[lid] = rec
        return {**rec, "agentCount": 0}


@app.put("/api/v1/listeners/http")
def put_http(body: HttpListenerUpdateBody, id: int | None = None):
    # TeamServer signature: UpdateHttpListener([FromBody] HttpListenerDto) -> no query
    # param. `id` stays optional for the mock CLI/smoke test and legacy callers.
    with LOCK:
        body_data = body.model_dump(exclude_none=True)
        target = _coerce_id(id) if id is not None else _coerce_id(body_data.get("id"))
        if target is None:
            return JSONResponse({"error": "listener id required (query ?id= or body .id)"},
                                status_code=400)
        rec = STATE.http_listeners.get(target)
        if rec is None:
            return JSONResponse({**body_data, "error": "listener not found"},
                                status_code=404)
        rec.update(body_data)
        rec["id"] = target
        return {**rec, "agentCount": _agent_count(target)}


@app.delete("/api/v1/listeners/http")
def del_http(moduleId: str | None = None, id: int | None = None):
    # TeamServer signature: StopHttpListener([FromQuery] string moduleId) -> Ok()/BadRequest().
    # `id` stays optional so the mock CLI/smoke test keeps working.
    with LOCK:
        target = _coerce_id(moduleId) if moduleId is not None else _coerce_id(id)
        if target is None:
            return JSONResponse({"error": "moduleId query parameter required"},
                                status_code=400)
        rec = STATE.http_listeners.pop(target, None)
    if rec is None:
        return JSONResponse({"error": "listener not found"}, status_code=400)
    return {}


# Real TeamServer shape (swagger: /api/v1/server/*).
@app.get("/api/v1/server/status")
def server_status():
    return {}


@app.get("/api/v1/server/teamserverip")
def server_teamserver_ip():
    return {"ipV4": "203.0.113.10", "ipV6": "2001:db8:1234::10"}


# ---- config / auth ------------------------------------------------------------------
# Mock-only extras (shipped Compose settings screens call /api/v1/config/*);
# real TeamServer serves /api/v1/server/* above.
@app.get("/api/v1/config/teamserverIp")
def teamserver_ip():
    return {"ipV4": "203.0.113.10", "ipV6": "2001:db8:1234::10"}


@app.get("/api/v1/config/status")
def config_status():
    return {}


class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def login(body: LoginBody):
    if not body.username or not body.password:
        return JSONResponse({"message": "invalid username or password"}, status_code=404)
    return {"access_token": _fake_jwt(body.username), "token_type": "bearer",
            "expires_in": 3600}


# --- OpenAPI tag grouping so /docs shows Payloads/Agents/Tasks/... groups -------------
def _tag_for(path: str) -> list[str]:
    if path.startswith("/api/v1/payloads"):
        return ["payloads"]
    if path.startswith("/api/v1/agent/") or path.startswith("/api/v1/agents"):
        return ["agents"]
    if path.startswith("/api/v1/commands"):
        return ["commands"]
    if (path.startswith("/api/v1/tasks") or path.endswith("/clearQueue")
            or path.endswith("/stop")):
        return ["tasks"]
    if path.startswith("/api/v1/data"):
        return ["data"]
    if path.startswith("/api/v1/listeners"):
        return ["listeners"]
    if path.startswith("/api/v1/server") or path.startswith("/api/v1/config"):
        return ["server"]
    if path.startswith("/api/v1/auth"):
        return ["auth"]
    return ["meta"]


for _route in app.routes:
    _p = getattr(_route, "path", "")
    if _p == "/" or _p.startswith("/api/v1"):
        _route.tags = _tag_for(_p)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")

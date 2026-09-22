#!/usr/bin/env python
"""Smoke test for the Trinity mock API. Expects the server at 127.0.0.1:1337."""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:1337"
FAILS: list[str] = []


def req(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, None


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        FAILS.append(name)


def wait_for_server(timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            code, _ = req("GET", "/api/v1/config/status")
            if code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise SystemExit("server did not come up")


def wait_task_status(task_id: str, statuses, timeout: float = 30):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        c, t = req("GET", f"/api/v1/tasks/{task_id}")
        if c == 200:
            last = t.get("taskStatus")
            if last in statuses:
                return True, last
        time.sleep(0.5)
    return False, last


def main() -> None:
    wait_for_server()

    # -- config ------------------------------------------------------------------
    c, b = req("GET", "/api/v1/config/teamserverIp")
    check("config.teamserverIp", c == 200 and b.get("ipV4") and b.get("ipV6"), str(b))
    c, b = req("GET", "/api/v1/config/status")
    check("config.status", c == 200 and b == {})

    # real TeamServer shape (swagger: /api/v1/server/*)
    c, b = req("GET", "/api/v1/server/status")
    check("server.status", c == 200 and b == {})
    c, b = req("GET", "/api/v1/server/teamserverip")
    check("server.teamserverip", c == 200 and b.get("ipV4") and b.get("ipV6"))

    # -- auth ----------------------------------------------------------------------
    c, b = req("POST", "/api/v1/auth/login", {"username": "admin", "password": "admin"})
    check("auth.login", c == 200 and b.get("token_type") == "bearer"
          and b.get("expires_in", 0) > 0 and b.get("access_token", "").count(".") == 2)

    # -- agents ----------------------------------------------------------------------
    c, agents = req("GET", "/api/v1/agents")
    ok = c == 200 and isinstance(agents, list) and len(agents) >= 3
    check("agents.list", ok, f"n={len(agents) if isinstance(agents, list) else '?'}")
    a0 = agents[0]["uuid"]
    need = ["id", "uuid", "username", "processName", "integrity", "status",
            "firstSeen", "lastSeen", "campaignId", "listenerId", "payloadId"]
    check("agents.list.fields", all(set(need) <= set(a) for a in agents))

    c, a = req("GET", f"/api/v1/agents/{a0}")
    check("agents.detail", c == 200 and all(k in a for k in need))
    c, a = req("GET", f"/api/v1/agents/{agents[0]['id']}")
    check("agents.byIntId", c == 200 and a.get("uuid") == a0)

    c, b = req("GET", "/api/v1/agents/nope-nope")
    check("errors.agent404", c == 404 and b.get("error"))

    new_uuid = str(uuid.uuid4())
    c, b = req("POST", "/api/v1/agent/checkin", {
        "action": "checkin", "uuid": new_uuid, "ips": ["10.9.9.9"],
        "external_ip": "203.0.113.99", "os": "Windows 11 Pro", "host": "smoke-host",
        "process_name": "cmd.exe", "pid": 1234, "architecture": "x64",
        "mac": "AA:BB:CC:DD:EE:FF", "domain": "trinity.local",
        "integrity_level": 16664, "user": "smoke\\user", "users": ["smoke\\user"],
    })
    check("agents.checkin", c == 200 and b.get("id") == new_uuid
          and b.get("status") == "success" and b.get("action") == "checkin")
    c, agents = req("GET", "/api/v1/agents")
    check("agents.checkin.registered",
          any(a["uuid"] == new_uuid for a in agents))

    # -- tasks ------------------------------------------------------------------------
    # real TeamServer shape (swagger: GET /api/v1/tasks/tasks)
    c, tasks = req("GET", "/api/v1/tasks/tasks")
    ok = c == 200 and isinstance(tasks, list) and len(tasks) >= 1
    ok = ok and all(set(["taskId", "id", "taskCommand", "user", "created",
                         "updated", "taskStatus"]) <= set(t) for t in tasks)
    check("tasks.list", ok, f"n={len(tasks) if isinstance(tasks, list) else '?'}")

    some_task = tasks[0]["taskId"]
    c, t = req("GET", f"/api/v1/tasks/{some_task}")
    check("tasks.byId", c == 200 and t.get("taskId") == some_task and "agentId" in t)
    c, t = req("GET", f"/api/v1/tasks/{a0}")
    check("tasks.byAgent", c == 200 and isinstance(t, list)
          and all(x["id"] == a0 for x in t))
    c, b = req("GET", "/api/v1/tasks/nope-nope")
    check("errors.task404", c == 404 and b.get("error"))

    # -- commands ----------------------------------------------------------------------
    simple_cmds = [
        ("spawn", "powershell", {"commandlet": "Get-Process", "arguements": ""}),
        ("spawn", "shell", {"command": "whoami"}),
        # exact real-TeamServer command names (swagger)
        ("spawn", "runas", {"domain": "trinity.local", "user": "Administrator",
                           "command": "cmd.exe", "arguments": "/c id"}),
        ("spawn", "run", {"program": "notepad.exe", "arguments": ""}),
        ("spawn", "runu", {"pid": 4920, "command": "cmd.exe", "arguements": ""}),
        ("spawn", "killprocess", {"pid": 4920}),
        ("spawn", "escalate", {"regKey": "HKLM\\SOFTWARE",
                               "targetBinary": "C:\\Windows\\System32\\svchost.exe"}),
        ("spawn", "dotnetassembly", {"assembly": "Tool.dll", "arguments": "--run"}),
        ("execute", "bof", {"bof": "YWJjZA==", "entrypoint": "go", "arugments": ""}),
    ]
    first_tid = None
    for kind, name, body in simple_cmds:
        c, b = req("POST", f"/api/v1/commands/{a0}/{kind}/{name}", body)
        ok = c == 200 and b.get("command") == f"{kind}/{name}" \
            and b.get("taskId") and "message" in b
        check(f"commands.{kind}/{name}", ok)
        if first_tid is None:
            first_tid = b.get("taskId")

    c, b = req("POST", "/api/v1/commands/nope-nope/spawn/shell", {"command": "x"})
    check("errors.command404", c == 404 and b.get("command")
          and b.get("message") and "taskId" in b)

    ok, st = wait_task_status(first_tid, {"completed"})
    check("commands.lifecycle.completed", ok, st or "")

    # filedownload: create, watch activeDownloads, wait for download record
    c, fd = req("POST", f"/api/v1/commands/{a0}/execute/filedownload",
                {"path": "C:\\temp\\smoke.bin"})
    check("commands.filedownload.post", c == 200 and fd.get("taskId"))
    c, ad = req("GET", f"/api/v1/tasks/{a0}/activeDownloads")
    check("tasks.activeDownloads.shape", c == 200 and isinstance(ad, list)
          and all(set(["name", "path", "size", "received"]) <= set(x) for x in ad))
    saw_active = any(x["name"] == "smoke.bin" for x in (ad or []))
    deadline = time.time() + 8
    while not saw_active and time.time() < deadline:
        c, ad = req("GET", f"/api/v1/tasks/{a0}/activeDownloads")
        saw_active = any(x["name"] == "smoke.bin" for x in (ad or []))
        time.sleep(0.5)
    check("tasks.activeDownloads.entry", saw_active)
    ok, st = wait_task_status(fd["taskId"], {"completed"})
    c, dls = req("GET", "/api/v1/data/downloads")
    check("commands.filedownload.record", ok
          and any("smoke.bin" in d["path"] for d in dls), st or "")

    # upload (real UploadDTO field is `path`)
    c, up = req("POST", f"/api/v1/commands/{a0}/execute/upload",
                {"path": "C:\\Users\\public\\smoke.txt"})
    check("commands.upload.post", c == 200 and up.get("taskId"))
    ok, st = wait_task_status(up["taskId"], {"completed"})
    c, dls = req("GET", "/api/v1/data/downloads")
    check("commands.upload.record", ok
          and any("smoke.txt" in d["path"] for d in dls), st or "")

    # cancelFileDownload
    c, fd2 = req("POST", f"/api/v1/commands/{a0}/execute/filedownload",
                 {"path": "C:\\temp\\cancel-me.bin"})
    c2, cb = req("POST", f"/api/v1/commands/{a0}/execute/cancelFileDownload",
                 {"taskId": fd2.get("taskId", "")})
    check("commands.cancelFileDownload", c2 == 200
          and cb.get("taskId") == fd2.get("taskId"))
    c, t = req("GET", f"/api/v1/tasks/{fd2['taskId']}")
    check("commands.cancelFileDownload.cancelled", t.get("taskStatus") == "cancelled")

    # clearQueue
    req("POST", f"/api/v1/commands/{a0}/spawn/shell", {"command": "dir"})
    req("POST", f"/api/v1/commands/{a0}/spawn/shell", {"command": "ipconfig"})
    time.sleep(0.2)
    # real TeamServer shape: DELETE /{agentID}/clearQueue at root level
    c, b = req("DELETE", f"/{a0}/clearQueue")
    check("tasks.clearQueue", c == 200 and b.get("command") == "clearQueue"
          and b.get("taskId") == "" and "message" in b)

    # stop — real TeamServer shape: GET /{taskID}/stop at root level
    c, st2 = req("POST", f"/api/v1/commands/{a0}/spawn/shell", {"command": "tasklist"})
    c2, sb = req("GET", f"/{st2.get('taskId', '')}/stop")
    check("tasks.stop", c2 == 200 and sb.get("taskId") == st2.get("taskId"))
    c, t = req("GET", f"/api/v1/tasks/{st2['taskId']}")
    check("tasks.stop.cancelled", t.get("taskStatus") == "cancelled")

    # -- payloads ---------------------------------------------------------------------
    c, pays = req("GET", "/api/v1/payloads")
    need_p = ["payloadId", "listenerId", "useListenerGuardRails", "architecture",
              "exitFunction", "systemCallMethod", "outputType", "payloadFileName",
              "payloadFilePath"]
    check("payloads.list", c == 200 and isinstance(pays, list) and len(pays) >= 3
          and all(set(need_p) <= set(p) for p in pays))
    c, p = req("GET", f"/api/v1/payloads/{pays[0]['payloadId']}")
    check("payloads.byId", c == 200 and p.get("payloadId") == pays[0]["payloadId"])
    c, b = req("GET", "/api/v1/payloads/nope")
    check("errors.payload404", c == 404 and b.get("error"))

    c, tls = req("GET", "/api/v1/listeners/tcp")
    lid = str(tls[0]["id"])
    fname = f"smoke_{int(time.time())}.exe"
    c, b = req("POST", "/api/v1/payloads/generate", {
        "listenerId": lid, "useListenerGuardRails": True,
        "architecture": "windows/x64", "exitFunction": "winhttp",
        "systemCallMethod": "SysWhidCall", "outputType": "exe",
        "payloadFileName": fname})
    check("payloads.generate", c == 200 and b == {})
    c, pays2 = req("GET", "/api/v1/payloads")
    check("payloads.generate.registered", len(pays2) == len(pays) + 1)
    c, b = req("POST", "/api/v1/payloads/generate", {
        "listenerId": "9999", "useListenerGuardRails": False,
        "architecture": "windows/x64", "exitFunction": "winhttp",
        "systemCallMethod": "WhidCall", "outputType": "ps1",
        "payloadFileName": "nope.ps1"})
    check("payloads.generate.badListener", c == 404 and b.get("error")
          and b.get("payloadFileName") == "nope.ps1")

    # -- data/downloads -------------------------------------------------------------------
    c, dls = req("GET", "/api/v1/data/downloads")
    check("downloads.list", c == 200 and isinstance(dls, list) and len(dls) >= 2
          and all(set(["id", "path", "downloadDate"]) <= set(d) for d in dls))
    did = dls[0]["id"]
    c, b = req("GET", f"/api/v1/data/downloads/{did}")
    ok = c == 200 and isinstance(b.get("bytes"), str)
    if ok:
        try:
            base64.b64decode(b["bytes"], validate=True)
        except Exception:
            ok = False
    check("downloads.bytes", ok)
    c, b = req("DELETE", f"/api/v1/data/downloads/{did}")
    check("downloads.delete", c == 200 and b == {})
    c, b = req("GET", f"/api/v1/data/downloads/{did}")
    check("downloads.deleted", c == 404)

    # -- listeners: flat (real TeamServer: GET /api/v1/listeners) ----------------
    c, all_ls = req("GET", "/api/v1/listeners")
    check("listeners.all", c == 200 and isinstance(all_ls, list) and len(all_ls) >= 2)

    # -- listeners: tcp ---------------------------------------------------------------------
    c, tls = req("GET", "/api/v1/listeners/tcp")
    need_t = ["id", "name", "type", "port", "localHostOnly", "guardRails"]
    check("listeners.tcp.list", c == 200 and isinstance(tls, list) and len(tls) >= 1
          and all(set(need_t) <= set(x) for x in tls))
    body = {"name": "smoke-tcp", "type": "tcp", "port": 9999, "localHostOnly": False,
            "guardRails": {"ipAddress": "10.0.0.9", "userName": "",
                           "serverName": "", "domain": "smoke.local"}}
    c, b = req("POST", "/api/v1/listeners/tcp", body)
    check("listeners.tcp.create", c == 200 and b.get("name") == "smoke-tcp"
          and b.get("id") is not None)
    new_id = b["id"]
    body2 = dict(body)
    body2["port"] = 9998
    c, b = req("PUT", f"/api/v1/listeners/tcp?id={new_id}", body2)
    check("listeners.tcp.update", c == 200 and b.get("port") == 9998)
    c, b = req("DELETE", f"/api/v1/listeners/tcp?id={new_id}")
    check("listeners.tcp.delete", c == 200 and b == {})
    c, tls2 = req("GET", "/api/v1/listeners/tcp")
    check("listeners.tcp.deleted", all(x["id"] != new_id for x in tls2))
    c, b = req("PUT", "/api/v1/listeners/tcp?id=9999", body)
    check("errors.listener404.put", c == 404 and b.get("error"))

    # -- listeners: http ---------------------------------------------------------------------
    c, hls = req("GET", "/api/v1/listeners/http")
    need_h = ["id", "name", "type", "hosts", "httpC2BindPort", "httpBindPort",
              "userAgent", "httpHostHeader", "hostRotationStrategy",
              "maxRetryStrategy", "guardRails"]
    check("listeners.http.list", c == 200 and isinstance(hls, list) and len(hls) >= 1
          and all(set(need_h) <= set(x) for x in hls))
    hbody = {"name": "smoke-http", "type": "http", "hosts": ["smoke.example.com"],
             "httpC2BindPort": 8443, "httpBindPort": 8443,
             "userAgent": "smoke-agent/1.0", "httpHostHeader": "smoke.example.com",
             "hostRotationStrategy": "Random", "maxRetryStrategy": "Fixed",
             "guardRails": {"ipAddress": "10.0.0.9", "userName": "",
                            "serverName": "", "domain": "smoke.local"}}
    c, b = req("POST", "/api/v1/listeners/http", hbody)
    check("listeners.http.create", c == 200 and b.get("name") == "smoke-http")
    hid = b["id"]
    hbody2 = dict(hbody)
    hbody2["httpC2BindPort"] = 8444
    c, b = req("PUT", f"/api/v1/listeners/http?id={hid}", hbody2)
    check("listeners.http.update", c == 200 and b.get("httpC2BindPort") == 8444)
    c, b = req("DELETE", f"/api/v1/listeners/http?id={hid}")
    check("listeners.http.delete", c == 200 and b == {})
    c, hls2 = req("GET", "/api/v1/listeners/http")
    check("listeners.http.deleted", all(x["id"] != hid for x in hls2))

    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURES: {FAILS}'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()

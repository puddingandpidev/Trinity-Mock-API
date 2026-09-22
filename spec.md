The Representational State Transfer Application Programming Interface (REST API) is responsible for the management of commands issued to agents, listeners, operators.

## Team Server Architecture 

<figure>
<img src="/Docs/Design/Attachments/ApiArchUmlDiagram.png" alt="Team Server UML Architecture">
<figcaption>
Team Server UML Architecture Diagram.
</figcaption>
</figure>

## Development stack

| Component                  | Technology choice              | Version/Details       | Project Template | Hosting                       |
| -------------------------- | ------------------------------ | --------------------- | ---------------- | ----------------------------- |
| Backend Language           | C#                             | C# 12 / .NET 10.0 LTS | N/A              | N/A                           |
| Containerisation           | Docker                         | Docker 29.7.2         | N/A              | N/A                           |
| Entity Framework (EF) Core | Object Relational Mapper (ORM) | EF CORE 10.0          | N/A              | N/A                           |
| Documentation              | Swashbuckle                    | Swashbuckle 10.2.3    | M/A              | Integrated inside App Service |
| Database                   | PostgreSQL                     | Npgsql 10.0.3         | N/A              | Oracle FREE tier              |
| API                        | ASP.NET Core Web API           | ASP.NET Core 10.0     | Web API template | Oracle FREE tier              |

## Endpoint Overview 

| Method | Endpoint                                              | Description                                                             |
| ------ | ----------------------------------------------------- | ----------------------------------------------------------------------- |
| GET    | /api/v1/payloads                                      | Retrieves a list of all created payloads.                               |
| GET    | /api/v1/payloads/{payloadId}                          | Retrieves details for a specific payload.                               |
| POST   | /api/v1/payloads/generate                             | Generates a new agent payload artifact.                                 |
| GET    | /api/v1/agents/{agentID}                              | Retrieves status and metadata for a specific agent (int agentID).       |
| GET    | /api/v1/agents                                        | Retrieves a list of all registered agents.                              |
| POST   | /api/v1/agent/checkin                                 | Dedicated checkin endpoint that all agents send checkin requests.       |
| GET    | /api/v1/tasks/tasks                                    | Retrieves a list of all agent tasks. (real)                             |
| GET    | /api/v1/tasks/{taskId}                                | Retrieves details and status for a specific task. (mock; real path is by agent) |
| GET    | /api/v1/tasks/{agentId}                               | Retrieves tasks for a specific agent. (real)                            |
| GET    | /api/v1/tasks/{agentId}/activeDownloads               | Lists active file transfers occurring on a specific agent. (real)       |
| DELETE | /{agentId}/clearQueue                                 | Cancels all pending tasks in an agent's queue. (real, root level)       |
| GET    | /{taskId}/stop                                        | Commands an agent to halt execution of a task. (real, root level, GET)  |
| POST   | /api/v1/commands/{agentId}/spawn/powershell           | Spawns a new PowerShell session on the target agent.                    |
| POST   | /api/v1/commands/{agentId}/spawn/shell                | Spawns a native OS command shell session on the agent.                  |
| POST   | /api/v1/commands/{agentId}/spawn/runas                | Executes a command on the agent under different user credentials. (real) |
| POST   | /api/v1/commands/{agentId}/spawn/run                  | Spawns and executes a process on the target agent. (real)               |
| POST   | /api/v1/commands/{agentId}/spawn/runu                 | Runs a process detached or with specific user token privileges. (real)  |
| POST   | /api/v1/commands/{agentId}/spawn/killprocess          | Terminates a running process on the agent's host system. (real)         |
| POST   | /api/v1/commands/{agentId}/spawn/escalate             | Triggers a privilege escalation exploit module on the agent. (real)     |
| POST   | /api/v1/commands/{agentId}/spawn/dotnetassembly       | Executes a .NET assembly a specified process on the host. (real)        |
| POST   | /api/v1/commands/{agentId}/execute/bof                | Executes a Beacon Object File (BOF) in-memory on the agent. (real)      |
| POST   | /api/v1/commands/{agentId}/execute/filedownload       | Instructs the agent to download a file from the server. (real)          |
| POST   | /api/v1/commands/{agentId}/execute/cancelFileDownload | Cancels an ongoing file download task on the agent. (real)              |
| POST   | /api/v1/commands/{agentId}/execute/upload             | Instructs the agent to exfiltrate a file to the server.                 |
| GET    | /api/v1/data/downloads                                | Lists all successfully downloaded/exfiltrated files on the team server. |
| GET    | /api/v1/data/downloads/{id}                           | Retrieves a specific downloaded file or its binary data.                |
| DELETE | /api/v1/data/downloads/{id}                           | Removes a downloaded file record from the team server storage.          |
| GET    | /api/v1/listeners                                     | Flat list of all listeners (tcp + http). (real)
| POST   | /api/v1/listeners/tcp                                 | Creates and starts a new TCP listener. (real; mock also serves GET/PUT/DELETE)
| GET    | /api/v1/listeners/http                                | Lists HTTP/HTTPS listeners. (mock; real reads via /api/v1/listeners)
| POST   | /api/v1/listeners/http                                | Creates and starts an HTTP/HTTPS listener. (real)
| PUT    | /api/v1/listeners/http                                | Updates an HTTP/HTTPS listener. (real)
| DELETE | /api/v1/listeners/http                                | Stops and removes an HTTP/HTTPS listener. (real)
| GET    | /api/v1/server/teamserverip                           | C2 teamserver configuration IPs. (real)
| GET    | /api/v1/server/status                                 | Overall system/infrastructure health status. (real)
| GET    | /api/v1/config/teamserverIp                           | Mock-only alias of /api/v1/server/teamserverip (shipped settings screen)
| GET    | /api/v1/config/status                                 | Mock-only alias of /api/v1/server/status (shipped settings screen)
| POST   | /api/v1/auth/login                                    | Authenticates a user and generates a session token.                     |

## Endpoint Specifications 

Below each REST API endpoint is detailed in terms of its request and response JSON schema. 
### Payloads
#### GET /api/v1/payloads

> [!IMPORTANT] Request
> ```json 
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json 
> [
>   {
>     "payloadId": "string",
>     "listenerId": "string",
>     "useListenerGuardRails": false,
>     "architecture": "string",
>     "exitFunction": "string",
>     "systemCallMethod": "string",
>     "outputType": "string",
>     "payloadFileName": "string",
>     "payloadFilePath": "string"
>   },
>   {
>     "payloadId": "string",
>     "listenerId": "string",
>     "useListenerGuardRails": true,
>     "architecture": "string",
>     "exitFunction": "string",
>     "systemCallMethod": "string",
>     "outputType": "string",
>     "payloadFileName": "string",
>     "payloadFilePath": "string"
>   }
> ]
> ```

> [!ERROR] Gateway Timeout 504
> ```json 
> []
> ```

#### GET /api/v1/payloads/{payloadId}

> [!IMPORTANT] Request
> ```json 
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
> "payloadId": "string",
> "listenerId": "string",
> "useListenerGuardRails": false,
> "architecture": "string",
> "exitFunction": "string",
> "systemCallMethod": "string",
> "outputType": "string",
> "payloadFileName": "string",
> "payloadFilePath": "string"
> }
> ```

> [!ERROR] Gateway Timeout 504
> ```json 
> []
> ```

#### POST /api/v1/payloads/generate

> [!IMPORTANT] Request
> ```json 
> {
>   "listenerId": "string",
>   "useListenerGuardRails": true,
>   "architecture": "string",
>   "exitFunction": "string",
>   "systemCallMethod": "string",
>   "outputType": "string",
>   "payloadFileName": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json 
> {}
> ```

> [!ERROR] Bad Request 404
> ```json 
> {
>   "listenerId": "string",
>   "useListenerGuardRails": "boolean",
>   "architecture": "string",
>   "exitFunction": "string",
>   "systemCallMethod": "string",
>   "outputType": "string",
>   "payloadFileName": "string",
>   "error": "string"
> }
> ```

### Agents
#### GET /api/v1/agents/{agentID}

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> Real TeamServer AgentDTO shape (camelCase, SwaggerGen output):
> ```json
> {
>   "id": 1,
>   "uuid": "string",
>   "username": "string",
>   "processName": "string",
>   "integrity": null,
>   "status": "Active | Diconnected",
>   "firstSeen": "2026-09-21T20:41:21",
>   "lastSeen": "2026-09-21T20:41:21",
>   "campaignId": null,
>   "listenerId": 1,
>   "payloadId": 1
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "error": "string"
> }
> ```

#### GET /api/v1/agents

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> [
>   {
>     "agentId": "string",
>     "pid": 0,
>     "process": "string",
>     "user": "string",
>     "isAdmin": true,
>     "computer": "string",
>     "host": "string",
>     "internal": "string",
>     "external": "string",
>     "os": "string",
>     "systemArch": "string",
>     "beaconArch": "string",
>     "listener": "string",
>     "note": "string",
>     "alive": true,
>     "lastCheckinTime": 0,
>     "lastCheckinMs": 0,
>     "lastCheckinFormatted": "string",
>     "sleep": {
>       "sleep": 0,
>       "jitter": 0
>     }
>   },
>   {
>     "agentId": "string",
>     "pid": 0,
>     "process": "string",
>     "user": "string",
>     "isAdmin": true,
>     "computer": "string",
>     "host": "string",
>     "internal": "string",
>     "external": "string",
>     "os": "string",
>     "systemArch": "string",
>     "beaconArch": "string",
>     "listener": "string",
>     "note": "string",
>     "alive": true,
>     "lastCheckinTime": 0,
>     "lastCheckinMs": 0,
>     "lastCheckinFormatted": "string",
>     "sleep": {
>       "sleep": 0,
>       "jitter": 0
>     }
>   }
> ]
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### POST /api/v1/agent/checkin

> [!IMPORTANT] Request
> ```json
> {
>   "action": "string",
>   "uuid": "string",
>   "ips": ["string"],
>   "external_ip": "string",
>   "os": "string",
>   "host": "string",
>   "process_name": "string",
>   "pid": 0,
>   "architecture": "string",
>   "motherboard": "string",
>   "ram": 0,
>   "disk_size": 0,
>   "free_disk": 0,
>   "cpu_count": 0,
>   "mac": "string",
>   "domain": "string",
>   "integrity_level": 0,
>   "user": "string",
>   "users": ["string", "string"]
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "action": "string",
>   "id": "string",
>   "status": "string"
> }
> ```

### Tasks
#### GET /api/v1/tasks

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200 with tasks
> ```json
> [
>   {
>     "taskId": "string",
>     "id": "string",
>     "taskCommand": "string",
>     "user": "string",
>     "created": 0,
>     "updated": 0,
>     "taskStatus": "string"
>   },
>   {
>     "taskId": "string",
>     "id": "string",
>     "taskCommand": "string",
>     "user": "string",
>     "created": 0,
>     "updated": 0,
>     "taskStatus": "string"
>   }
> ]
> ```

> [!SUCCESS] Successful Request 200 Empty
> ```json
> []
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### GET /api/v1/tasks/{taskId}

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "taskId": "string",
>   "agentId": "string",
>   "taskCommand": "string",
>   "user": "string",
>   "created": 0,
>   "updated": 0,
>   "taskStatus": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "error": "string"
> }
> ```

#### GET /api/v1/tasks/{agentId}

Specifies in query the task search filters.

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200 With Tasks
> ```json
> [
>   {
>     "taskId": "string",
>     "id": "string",
>     "taskCommand": "string",
>     "user": "string",
>     "created": 0,
>     "updated": 0,
>     "taskStatus": "string"
>   },
>   {
>     "taskId": "string",
>     "id": "string",
>     "taskCommand": "string",
>     "user": "string",
>     "created": 0,
>     "updated": 0,
>     "taskStatus": "string"
>   }
> ]
> ```

> [!SUCCESS] Successful Request 200 Empty
> ```json
> []
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "error": "string"
> }
> ```

#### GET /api/v1/tasks/{agentId}/activeDownloads

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200 With Files
> ```json
> [
>   {
>     "name": "string",
>     "path": "string",
>     "size": 0,
>     "received": 0
>   }
> ]
> ```

> [!SUCCESS] Successful Request 200 Empty
> ```json
> []
> ```

#### DELETE /api/v1/tasks/{agentId}/clearQueue

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/tasks/{agentId}/stop

> [!IMPORTANT] Request
> 
> ```json
> {
>   "taskId": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

### Commands
#### POST /api/v1/commands/{agentId}/spawn/powershell

> [!IMPORTANT] Request
> ```json
> {
>   "commandlet": "string",
>   "arguements": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/spawn/shell

> [!IMPORTANT] Request
> ```json
> {
>   "command": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/spawn/runAs

> [!IMPORTANT] Request 
> ```json
> {
>   "domain": "string",
>   "user": "string",
>   "command": "string",
>   "arguments": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/spawn/run

> [!IMPORTANT] Request
> ```json
> {
>   "program": "string",
>   "arguments": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/spawn/runU

> [!IMPORTANT] Request
> ```json
> {
>   "pid": 0,
>   "command": "string",
>   "arguements": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/killProcess

> [!IMPORTANT] Request
> ```json
> {
>   "pid": 0
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/escalate

> [!IMPORTANT] Request
> ```json
> {
>   "regKey": "string",
>   "targetBinary": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/dotnetAssembly

> [!IMPORTANT] Request
> ```json
> {
>   "assembly": "string",
>   "arguments": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/bof

> [!IMPORTANT] Request
> ```json
> {
>   "bof": "string",
>   "entrypoint": "string",
>   "arugments": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": 0
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/fileDownload`

> [!IMPORTANT] Request
> ```json
> {
>   "path": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": 0
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/cancelFileDownload

> [!IMPORTANT] Request
> ```json
> {
>   "taskId": 0
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": 0
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

#### POST /api/v1/commands/{agentId}/execute/upload

> [!IMPORTANT] Request
> ```json
> {
>   "file": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": 0
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "command": "string",
>   "message": "string",
>   "taskId": "string"
> }
> ```

### Data

#### GET /api/v1/data/downloads

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> [
>   {
>     "id": 0,
>     "path": "string",
>     "downloadDate": 0
>   },
>   {
>     "id": 0,
>     "path": "string",
>     "downloadDate": 0
>   }
> ]
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### GET /api/v1/data/downloads/{id}

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "bytes": "string"
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "message": "string"
> }
> ```

#### DELETE /api/v1/data/downloads/{id}

Query parameter: download ID
> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {}
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "error": "string"
> }
> ```

### TCP Listeners 

#### GET /api/v1/listeners/tcp

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> [
>   {
>     "id": 0,
>     "name": "string",
>     "type": "string",
>     "port": 0,
>     "localHostOnly": false,
>     "guardRails": {
>       "ipAddress": "string",
>       "userName": "string",
>       "serverName": "string",
>       "domain": "string"
>     }
>   },
>   {
>     "id": 0,
>     "name": "string",
>     "type": "string",
>     "port": 0,
>     "localHostOnly": false,
>     "guardRails": {
>       "ipAddress": "string",
>       "userName": "string",
>       "serverName": "string",
>       "domain": "string"
>     }
>   }
> ]
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### POST /api/v1/listeners/tcp

> [!IMPORTANT] Request
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   },
>   "error": "string"
> }
> ```

#### PUT /api/v1/listeners/tcp

Query parameter: tcp_listener ID
> [!IMPORTANT] Request
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "port": 0,
>   "localHostOnly": false,
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   },
>   "error": "string"
> }
> ```

#### DELETE /api/v1/listeners/tcp 

Query parameter: tcp_listener ID

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json 
> {} 
> ```

> [!ERROR] Bad Request 404
> ```json 
> {} 
> ```

### HTTP Listeners 

#### GET /api/v1/listeners/http

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> [
>   {
>     "id": 0,
>     "name": "string",
>     "type": "string",
>     "hosts": [
>       "string",
>       "string"
>     ],
>     "httpC2BindPort": 0,
>     "httpBindPort": 0,
>     "userAgent": "string",
>     "httpHostHeader": "string",
>     "hostRotationStrategy": "string",
>     "maxRetryStrategy": "string",
>     "guardRails": {
>       "ipAddress": "string",
>       "userName": "string",
>       "serverName": "string",
>       "domain": "string"
>     }
>   },
>   {
>     "id": 0,
>     "name": "string",
>     "type": "string",
>     "hosts": [
>       "string",
>       "string"
>     ],
>     "httpC2BindPort": 0,
>     "httpBindPort": 0,
>     "userAgent": "string",
>     "httpHostHeader": "string",
>     "hostRotationStrategy": "string",
>     "maxRetryStrategy": "string",
>     "guardRails": {
>       "ipAddress": "string",
>       "userName": "string",
>       "serverName": "string",
>       "domain": "string"
>     }
>   }
> ]
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### POST /api/v1/listeners/http 

> [!IMPORTANT] Request
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   },
>   "error": "string"
> }
> ```

#### PUT /api/v1/listeners/http

Query parameter: http_listener ID
> [!IMPORTANT] Request
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   }
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "name": "string",
>   "type": "string",
>   "hosts": [
>     "string",
>     "string"
>   ],
>   "httpC2BindPort": 0,
>   "httpBindPort": 0,
>   "userAgent": "string",
>   "httpHostHeader": "string",
>   "hostRotationStrategy": "string",
>   "maxRetryStrategy": "string",
>   "guardRails": {
>     "ipAddress": "string",
>     "userName": "string",
>     "serverName": "string",
>     "domain": "string"
>   },
>   "error": "string"
> }
> ```

#### DELETE /api/v1/listeners/http

Query parameter: http_listener ID

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {}
> ```

> [!ERROR] Bad Request 404
> ```json
> {}
> ```

### Server 

#### GET /api/v1/config/teamserverIp

> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "ipV4": "string",
>   "ipV6": "string"
> }
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

#### GET /api/v1/config/status
> [!IMPORTANT] Request
> ```json
> {}
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {}
> ```

> [!ERROR] Service Unavailable 504
> ```json
> {}
> ```

### Authentication 

#### POST /api/v1/auth/login

> [!IMPORTANT] Request
> ```json
> {
>   "username": "string",
>   "password": "string"
> }
> ```

> [!SUCCESS] Successful Request 200
> ```json
> {
>   "access_token": "string",
>   "token_type": "string",
>   "expires_in": 0
> }
> ```

> [!ERROR] Bad Request 404
> ```json
> {
>   "message": "string"
> }
> ```


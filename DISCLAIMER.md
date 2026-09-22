# Disclaimer

**Trinity Mock API is a development and testing artefact. It is not a security
tool, not a real command-and-control server, and not a product.**

- **No offensive capability.** Every endpoint returns deterministic, in-memory
  dummy data. Nothing here executes code, connects to, scans, or controls any
  host. It is a mock of an HTTP contract.
- **Fictional data only.** Agents, users, hosts, IP addresses, files and
  payloads are invented — RFC 5737 documentation ranges (`203.0.113.0/24`,
  `2001:db8::/32`), `example.com`, `TRINITY\jdoe`, `DEMO-PC`, and similar.
- **Unsafe by design for exposure.** Most endpoints have no authentication and
  all state is global and in-memory. It binds `127.0.0.1` by default. **Do not
  expose it to an untrusted network or the public internet.**
- **Educational context.** It mimics the REST contract of a university team
  project ("Trinity", PROG7314 / INSY7315). It is not affiliated with, or
  endorsed by, any other project, company, or institution.
- **No warranty.** Provided "as is", without warranty of any kind; the authors
  accept no liability for any use. Do not use it for unlawful activity.

If you are looking for a real C2 framework or security tool: this is not one,
and the seeded "capabilities" (spawn shell, upload/download, BOF, escalate,
keylogger, …) are static strings that only produce rows in a list.

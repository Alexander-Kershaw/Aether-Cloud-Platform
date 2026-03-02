***
# AETHER CLOUD PLATFORM (ACP) DEVLOG
***
## Repo skeleton and env sanity (2026-03-02)

**Action:** Created the ACP repository skeleton with a strict local-only `data/` directory (gitignored) and a `.env.example` containing only default local credentials and port mappings.

**Decision:** start with a minimal `bootstrap` container in Compose. This intentionally does not include any real services as of now. The purpose is to validate Docker and Compose execution initially, before introducing a multi-service failure surface.

**Tradeoff:** this initial setup doesn’t prove any platform capability yet. It only proves the scaffolding is correct and appropriate for future development.

---

## ACP CLI Foundation (2026-03-02)

### Objective

Establish a command-line interface (`aether` or by `./aether.sh`) to act as the primary control surface for the Aether Cloud Platform.

This transforms ACP from a collection of inconvenient Docker commands into a cohesive platform with a stable and reproducible operational interface.

Instead of interacting with infrastructure directly via:

```bash
docker compose up -d
docker compose down
```

Users interact with ACP via:

```bash
aether up
aether down
aether status
aether doctor
```

This abstraction is intentional. The CLI becomes the platform boundary, and Docker Compose becomes an implementation detail.

---

### Implementation

The CLI was implemented in Python using **Typer**, chosen for:

- clean command structure
- excellent help output
- minimal boilerplate
- easy extensibility for future commands (e.g., `smoke-test`, `submit`, `reset`)

The CLI lives in the `aether/` package and is exposed via a console entrypoint defined in `pyproject.toml`:

```toml
[project.scripts]
aether = "aether.cli:app"
```

Therefore, the CLI may be installed into the environment and executed globally via:

```bash
aether up
```

A Conda environment (`ACP_env`) was used to isolate dependencies and ensure reproducibility.

Editable install in conda environment:

```bash
pip install -e .
```

CLI iteration as a result should be quick and smooth without reinstalling after code changes.

---

#### Packaging issue encountered

Initial installation failed with:

```bash
Multiple top-level packages discovered in a flat-layout
```
**CAUSE:**
The cause of this was due to Setuptools attempting to package the entire repository, including the infrastructure directories (`docker/`, `data/`, etc...), rather than the CLI package exclusively.

**RESOLUTION:**
Explicit package declaration in `pyproject.toml`:

```toml
[tool.setuptools]
packages = ["aether"]
```

This restricted packaging to the intended CLI module.

Since ACP is the initial infrastructure project before building additional project within its architecture, ACP is not a Python library. The CLI is a component of the platform rather than a standalone entity.

---

#### Initial CLI command dictionary 

| Command          | Purpose                                              |
| ---------------- | ---------------------------------------------------- |
| `aether up`      | Starts platform via Docker Compose                   |
| `aether down`    | Stops platform                                       |
| `aether restart` | Clean restart                                        |
| `aether status`  | Shows Compose state                                  |
| `aether doctor`  | Validates Docker, environment, and port availability |


---

#### Verification


Successful tests: 

```bash
aether up
aether status
aether doctor
aether down
```

Confirmed:

- CLI executable available in Conda environment

- Compose lifecycle controlled exclusively via CLI

- Platform bootstrap container successfully managed

---

**STATUS: COMPLETE**

**ACP now has a stable, extensible, professional-grade control interface.**

This CLI will become the primary interface through which all future ACP functionality is accessed.

From this point forward:

- users interact with ACP via the CLI

- infrastructure is internal implementation

- smoke tests, diagnostics, and job submission will integrate into the CLI

---


## MinIO data lake online (2026-03-02)

### Objective
Brought up MinIO as the S3-compatible object store for ACP and provisioned the canonical lakehouse bucket (`aether-lakehouse`) via an init-style `mc` container.

This establishes a stable, cloud-like storage substrate so all future systems (Spark, Iceberg, Trino, streaming sinks) can write to a consistent S3 API and a consistent lake layout.

### Design decisions
- MinIO chosen as the local equivalent of AWS S3 (zero-cost, Docker-friendly, widely supported).
- An `mc` init container was used to create the bucket deterministically at boot.
- Lake layout prefixes (`bronze/`, `silver/`, `gold/`) are created immediately to enforce conventions straight away.

### Fix applied
Initial boot failed due to an invalid pinned `minio/mc` image tag (Docker registry did not publish the specified tag).
Updated pins to published release tags:
- `minio/minio:RELEASE.2025-01-20T14-49-07Z`
- `minio/mc:RELEASE.2025-01-17T23-25-50Z`

### Verification
- `aether up` brings up MinIO and reports `healthy`.
- Bucket persisted on the MinIO data volume (`docker exec acp-minio ls /data` shows `aether-lakehouse`).
- MinIO Console reachable at `http://localhost:9001` and bucket visible.
- `mc ls` confirms objects/prefixes exist inside the bucket.

---

**STATUS: COMPLETE**

**MinIO S3 lakehouse storage verified**

MinIO lakehouse successfully established with `gold/silver/bronze` layered architecture with deterministic bucket initiation (Init container `apc-mc-init` exits with exit code 0 after bucket creation)

---

## Streaming (Redpanda) (2026-03-02)

### Objective
Added Redpanda as ACP’s Kafka-compatible event streaming backbone and Redpanda Console for UI inspection.

A one-shot init container (`rpk-init`) creates the baseline topic `aether.events` at boot, making topic existence part of the platform contract rather than a manual setup step.

### Why Redpanda
Redpanda provides the Kafka API without the heavier operational footprint of ZooKeeper-era Kafka setups. For ACP this keeps the local platform fast, reproducible, and realistic enough to map cleanly onto cloud Kafka offerings.

### Verification
- `rpk topic list` shows `aether.events` with 1 partition and 1 replica.
- Produced 10 messages (`event_1` … `event_10`) and observed offsets 0–9.
- Consumed the same 10 messages back reliably via `rpk topic consume`.

---

**STATUS: COMPLETE**

**Confirmed message consumption, proved Redpanda service functionality.**

---


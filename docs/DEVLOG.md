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





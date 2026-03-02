from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
import re



app = typer.Typer(add_completion=False, help="AETHER Cloud Platform (ACP) CLI")
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker" / "compose.yml"
ENV_FILE = REPO_ROOT / ".env"

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")



def _run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return proc.returncode

def _compose_cmd(extra: list[str]) -> list[str]:
    return [
        "docker", "compose",
        "-f", str(COMPOSE_FILE),
        "--env-file", str(ENV_FILE),
        *extra,
    ]

# Check port
def _port_open(host: str, port: int, timeout_s: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False

# .env parser  
def _load_env_file(path: Path) -> dict[str, str]:
    raw: dict[str, str] = {}
    if not path.exists():
        return raw

    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        raw[k.strip()] = v.strip()

    def expand(val: str) -> str:
        def repl(m: re.Match[str]) -> str:
            name = m.group(1)
            return raw.get(name) or os.environ.get(name, "")
        prev = None
        cur = val
        for _ in range(5):
            if cur == prev:
                break
            prev = cur
            cur = _VAR.sub(repl, cur)
        return cur

    return {k: expand(v) for k, v in raw.items()}



def _docker_exec(container: str, args: list[str]) -> int:
    return _run(["docker", "exec", "-it", container, *args])



# COMMAND DEFINITIONS

# Start ACP stack
@app.command()
def up() -> None:
    if not COMPOSE_FILE.exists():
        raise typer.Exit(code=2)
    if not ENV_FILE.exists():
        console.print("[red]Missing .env[/red]. \n [yellow]Solution : create it via: cp .env.example .env[/yellow]")
        raise typer.Exit(code=2)

    console.print("AETHER Cloud Platform starting...\n")
    rc = _run(_compose_cmd(["up", "-d"]))
    if rc != 0:
        console.print("[red]docker compose up failed[/red]")
        raise typer.Exit(code=rc)

    console.print("\n[green]ACP containers started.[/green]")
    status()


# Stop ACP
@app.command()
def down() -> None:
    if not ENV_FILE.exists():
        console.print("[yellow]No .env found, running down anyway.[/yellow]")
    rc = _run(_compose_cmd(["down"]))
    raise typer.Exit(code=rc)


# Clean ACP restart
@app.command()
def restart() -> None:
    down()
    up()


# Show ACP container status
@app.command()
def status() -> None:
    table = Table(title="ACP Status", show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Result")

    table.add_row("compose file", "OK" if COMPOSE_FILE.exists() else "missing")
    table.add_row("env file", "OK" if ENV_FILE.exists() else "missing")
    console.print(table)

    console.print("\n[bold]docker compose ps[/bold]")
    _run(_compose_cmd(["ps"]))


# Run diagnostics (e.g docker install, env present, port avaliabilty)
@app.command()
def doctor() -> None:
    table = Table(title="ACP Doctor")
    table.add_column("Check", style="bold")
    table.add_column("Result")

    docker_ok = subprocess.run(["docker", "--version"], capture_output=True).returncode == 0
    table.add_row("docker", "OK" if docker_ok else "missing")

    table.add_row(".env present", "OK" if ENV_FILE.exists() else "missing")

    host = "127.0.0.1"
    ports = [9000, 9001, 19092, 18080, 18081, 18089, 19090, 13000]
    busy = [str(p) for p in ports if _port_open(host, p)]
    table.add_row("ports already in use", ", ".join(busy) if busy else "none detected")

    console.print(table)


# Run spark job on ACP spark cluster (MinIO and S3A wired in)
@app.command()
def spark_run(script_path: str = typer.Argument(..., help="Path under repo root, e.g. scripts/spark_write_parquet.py")) -> None:
    env = _load_env_file(ENV_FILE)

    access_key = env.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = env.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket = env.get("S3_BUCKET") or os.environ.get("S3_BUCKET") or "aether-lakehouse"

    if not access_key or not secret_key:
        console.print("[red]Missing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY[/red] in .env or shell.")
        raise typer.Exit(code=2)

    # Docker network endpoint
    s3_endpoint = "http://minio:9000"

    container_script = f"/opt/aether/{script_path.lstrip('/')}"
    packages = "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262"

    cmd = [
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--packages", packages,
        "--conf", f"spark.hadoop.fs.s3a.endpoint={s3_endpoint}",
        "--conf", "spark.hadoop.fs.s3a.path.style.access=true",
        "--conf", "spark.hadoop.fs.s3a.connection.ssl.enabled=false",
        "--conf", f"spark.hadoop.fs.s3a.access.key={access_key}",
        "--conf", f"spark.hadoop.fs.s3a.secret.key={secret_key}",
        "--conf", "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        "--conf", f"spark.acp.s3.bucket={bucket}", 
        container_script,
    ]

    console.print(f"[bold]Running Spark job:[/bold] {script_path}")
    rc = _docker_exec("acp-spark-master", cmd)
    raise typer.Exit(code=rc)



# List objects in MinIO using mc (verification)
@app.command()
def ls(prefix: str = typer.Argument(..., help="MinIO prefix, e.g. bronze/acp/sample_events")) -> None:
    env = _load_env_file(ENV_FILE)
    user = env.get("MINIO_ROOT_USER")
    pw = env.get("MINIO_ROOT_PASSWORD")
    bucket = env.get("S3_BUCKET") or "aether-lakehouse"

    if not user or not pw:
        console.print("[red]Missing MINIO_ROOT_USER / MINIO_ROOT_PASSWORD in .env[/red]")
        raise typer.Exit(code=2)

    script = (
        f"mc alias set aether http://minio:9000 {user} {pw} >/dev/null "
        f"&& mc ls -r aether/{bucket}/{prefix.lstrip('/')}"
    )

    rc = _run([
        "docker", "run", "--rm",
        "--network", "acp-net",
        "--entrypoint", "/bin/sh",
        "minio/mc:RELEASE.2025-01-17T23-25-50Z",
        "-lc", script
    ])
    raise typer.Exit(code=rc)
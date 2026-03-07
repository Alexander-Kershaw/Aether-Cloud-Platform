from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
import re
import shlex
from dataclasses import dataclass


app = typer.Typer(add_completion=False, help="AETHER Cloud Platform (ACP) CLI")
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker" / "compose.yml"
ENV_FILE = REPO_ROOT / ".env"

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


#========================================================================================================================    
# ACP compose command / env loading / docker execution
#========================================================================================================================


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


# Docker execution
def _docker_exec(container: str, args: list[str]) -> int:
    return _run(["docker", "exec", "-it", container, *args])

#========================================================================================================================
# Redpanda 
#========================================================================================================================
# Redpanda helper
def _rpk(args: list[str]) -> int:
    return _run(["docker", "exec", "-it", "acp-redpanda", "rpk", *args])


#========================================================================================================================
# Trino runner
#========================================================================================================================

@dataclass(frozen=True)
class TrinoTarget:
    container: str = "acp-trino"
    cli_bin: str = "trino"

# Run subprocess, raise typer error on failure
def _run_sub(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, text=True)
    except subprocess.CalledProcessError as e:
        raise typer.Exit(code=e.returncode)

# Trino helper (execute SQL inside Trino container)
def trino_exec(query: str, *, target: TrinoTarget = TrinoTarget()) -> None:
    cmd = [
        "docker", "exec", "-i",
        target.container,
        target.cli_bin,
        "--execute", query,
    ]
    _run_sub(cmd)

#========================================================================================================================
# Bronze Utilities
#========================================================================================================================

bronze_app = typer.Typer(help="Bronze layer utilities (raw external tables)")
app.add_typer(bronze_app, name="bronze")


def _bronze_schema_sql() -> str:
    return """
CREATE SCHEMA IF NOT EXISTS raw.bronze
WITH (location='s3a://aether-lakehouse/bronze/');
""".strip()


def _bronze_create_table_sql(table: str, dt: str) -> str:
    return f"""
CREATE TABLE raw.bronze.{table} (
  event_id bigint,
  dt varchar
)
WITH (
  external_location='s3a://aether-lakehouse/bronze/acp/sample_events/dt={dt}/',
  format='PARQUET'
);
""".strip()



#========================================================================================================================
# COMMAND DEFINITIONS
#========================================================================================================================

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

#========================================================================================================================
# Stop ACP
@app.command()
def down() -> None:
    if not ENV_FILE.exists():
        console.print("[yellow]No .env found, running down anyway.[/yellow]")
    rc = _run(_compose_cmd(["down"]))
    raise typer.Exit(code=rc)

#========================================================================================================================

# Clean ACP restart
@app.command()
def restart() -> None:
    down()
    up()

#========================================================================================================================
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


#========================================================================================================================
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

#========================================================================================================================
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

#========================================================================================================================

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


#========================================================================================================================

# List Kafka topics (Redpanda)
@app.command()
def topics() -> None:
    raise typer.Exit(code=_rpk(["topic", "list"]))

#========================================================================================================================
# Redpanda test: Produce N simple messages to a topic
@app.command()
def produce(
    topic: str,
    n: int = typer.Option(10, help="Number of messages"),
    prefix: str = typer.Option("event_", help="Message prefix"),
) -> None:
    script = f'for i in $(seq 1 {n}); do echo "{prefix}$i"; done | rpk topic produce {topic} --brokers redpanda:9092'
    rc = _run(["docker", "exec", "-i", "acp-redpanda", "bash", "-lc", script])
    raise typer.Exit(code=rc)

#========================================================================================================================
# Redpanda test: Consume N messages from a topic
@app.command()
def consume(
    topic: str,
    n: int = typer.Option(10, help="Number of messages"),
) -> None:
    raise typer.Exit(code=_rpk(["topic", "consume", topic, "--brokers", "redpanda:9092", "-n", str(n)]))

#========================================================================================================================
# Run SQL query in Trino (docker execution)
@app.command("sql")
def sql(
    query: str = typer.Argument(..., help="SQL query to execute in Trino"),
) -> None:
    trino_exec(query)
#========================================================================================================================




#========================================================================================================================
# Bronze Commands
#========================================================================================================================
# Register Parquet location as external table in Trino (raw.bronze)
@bronze_app.command("register")
def bronze_register(
    table: str = typer.Argument(..., help="Table name to register in raw.bronze"),
    dt: str = typer.Argument(..., help="Partition date, e.g. 2026-03-02"),
    drop_first: bool = typer.Option(True, "--drop/--no-drop", help="Drop table first to re-register cleanly"),
) -> None:
    trino_exec(_bronze_schema_sql())

    if drop_first:
        trino_exec(f"DROP TABLE IF EXISTS raw.bronze.{table}")

    trino_exec(_bronze_create_table_sql(table, dt))
    typer.echo(f"Registered raw.bronze.{table} for dt={dt}")

#========================================================================================================================
# List tables in raw.bronze
@bronze_app.command("tables")
def bronze_tables() -> None:
    trino_exec("SHOW TABLES FROM raw.bronze")

#========================================================================================================================
# Row count check
@bronze_app.command("count")
def bronze_count(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
) -> None:
    trino_exec(f"SELECT count(*) AS n FROM raw.bronze.{table}")

#========================================================================================================================
# Sample rows in raw.bronze
@bronze_app.command("sample")
def bronze_sample(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of rows to show"),
) -> None:
    trino_exec(f"SELECT * FROM raw.bronze.{table} LIMIT {limit}")

#========================================================================================================================
# Describe columns and type in raw.bronze table
@bronze_app.command("describe")
def bronze_describe(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
) -> None:
    trino_exec(f"DESCRIBE raw.bronze.{table}")

#========================================================================================================================


if __name__ == "__main__":
    app()
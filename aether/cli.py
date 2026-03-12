from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table


app = typer.Typer(add_completion=False, help="AETHER Cloud Platform (ACP) CLI")
bronze_app = typer.Typer(help="Bronze layer utilities (raw external tables)")
redpanda_app = typer.Typer(help="Redpanda utilities")

app.add_typer(bronze_app, name="bronze")
app.add_typer(redpanda_app, name="redpanda")

console = Console()

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker" / "compose.yml"
ENV_FILE = REPO_ROOT / ".env"

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


# ======================================================================================================================
# Core helpers
# ======================================================================================================================

def _run(
    cmd: list[str],
    *,
    check: bool = False,
    capture_output: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """
    Runs a subprocess command rooted at the repo directory.
    """
    try:
        return subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            check=check,
            capture_output=capture_output,
            text=text,
        )
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(code=exc.returncode)


def _compose_cmd(extra: list[str]) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "--env-file",
        str(ENV_FILE),
        *extra,
    ]


def _docker_exec(container: str, args: list[str], *, interactive: bool = False) -> subprocess.CompletedProcess:
    exec_flag = "-it" if interactive else "-i"
    return _run(["docker", "exec", exec_flag, container, *args])


def _port_open(host: str, port: int, timeout_s: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


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
        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
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


# ======================================================================================================================
# Trino helpers
# ======================================================================================================================

@dataclass(frozen=True)
class TrinoTarget:
    container: str = "acp-trino"
    cli_bin: str = "trino"


def trino_exec(query: str, *, target: TrinoTarget = TrinoTarget()) -> None:
    """
    Executes SQL inside the Trino container.
    """
    _run(
        [
            "docker",
            "exec",
            "-i",
            target.container,
            target.cli_bin,
            "--execute",
            query,
        ],
        check=True,
    )


# ======================================================================================================================
# Bronze SQL helpers
# ======================================================================================================================

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


# ======================================================================================================================
# Stack lifecycle commands
# ======================================================================================================================

@app.command()
def up() -> None:
    """
    Starts the ACP stack with docker compose.
    """
    if not COMPOSE_FILE.exists():
        console.print(f"[red]Missing compose file:[/red] {COMPOSE_FILE}")
        raise typer.Exit(code=2)

    if not ENV_FILE.exists():
        console.print("[red]Missing .env[/red]\n[yellow]Solution: cp .env.example .env[/yellow]")
        raise typer.Exit(code=2)

    console.print("AETHER Cloud Platform starting...\n")
    proc = _run(_compose_cmd(["up", "-d"]))
    if proc.returncode != 0:
        console.print("[red]docker compose up failed[/red]")
        raise typer.Exit(code=proc.returncode)

    console.print("\n[green]ACP containers started.[/green]")
    status()


@app.command()
def down() -> None:
    """
    Stops the ACP stack.
    """
    if not ENV_FILE.exists():
        console.print("[yellow]No .env found, running down anyway.[/yellow]")

    proc = _run(_compose_cmd(["down"]))
    raise typer.Exit(code=proc.returncode)


@app.command()
def restart() -> None:
    """
    Restarts the ACP stack.
    """
    down()
    up()


@app.command()
def status() -> None:
    """
    Shows ACP status and docker compose ps output.
    """
    table = Table(title="ACP Status")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("compose file", "OK" if COMPOSE_FILE.exists() else "MISSING")
    table.add_row("env file", "OK" if ENV_FILE.exists() else "MISSING")

    console.print(table)
    console.print()
    _run(_compose_cmd(["ps"]))


@app.command()
def doctor() -> None:
    """
    Runs quick ACP diagnostics.
    """
    env = _load_env_file(ENV_FILE)
    table = Table(title="ACP Doctor")
    table.add_column("Check")
    table.add_column("Result")

    docker_ok = _run(["docker", "--version"]).returncode == 0
    table.add_row("docker", "OK" if docker_ok else "MISSING")
    table.add_row(".env present", "OK" if ENV_FILE.exists() else "MISSING")

    ports_to_check = [
        ("MINIO_API_PORT", env.get("MINIO_API_PORT")),
        ("MINIO_CONSOLE_PORT", env.get("MINIO_CONSOLE_PORT")),
        ("REDPANDA_KAFKA_HOST_PORT", env.get("REDPANDA_KAFKA_HOST_PORT")),
        ("REDPANDA_ADMIN_HOST_PORT", env.get("REDPANDA_ADMIN_HOST_PORT")),
        ("REDPANDA_CONSOLE_HOST_PORT", env.get("REDPANDA_CONSOLE_HOST_PORT")),
        ("SPARK_MASTER_UI_HOST_PORT", env.get("SPARK_MASTER_UI_HOST_PORT")),
        ("SPARK_MASTER_RPC_HOST_PORT", env.get("SPARK_MASTER_RPC_HOST_PORT")),
        ("SPARK_WORKER_UI_HOST_PORT", env.get("SPARK_WORKER_UI_HOST_PORT")),
        ("TRINO_HOST_PORT", env.get("TRINO_HOST_PORT")),
        ("POSTGRES_HOST_PORT", env.get("POSTGRES_HOST_PORT")),
        ("HIVE_METASTORE_HOST_PORT", env.get("HIVE_METASTORE_HOST_PORT")),
        ("PROMETHEUS_HOST_PORT", env.get("PROMETHEUS_HOST_PORT")),
        ("GRAFANA_HOST_PORT", env.get("GRAFANA_HOST_PORT")),
    ]

    busy_ports: list[str] = []
    for name, value in ports_to_check:
        if not value:
            continue
        try:
            port = int(value)
        except ValueError:
            busy_ports.append(f"{name}={value} (invalid)")
            continue
        if _port_open("127.0.0.1", port):
            busy_ports.append(f"{name}={port}")

    table.add_row("ports already in use", ", ".join(busy_ports) if busy_ports else "none detected")
    console.print(table)


# ======================================================================================================================
# Spark and storage commands
# ======================================================================================================================

@app.command("spark-run")
def spark_run(
    script_path: str = typer.Argument(..., help="Path to Spark script relative to repo root, e.g. scripts/foo.py"),
) -> None:
    """
    Submits a Spark job through the Spark master container.
    """
    console.print(f"[bold]Running Spark job:[/bold] {script_path}")

    cmd = [
        "/opt/spark/bin/spark-submit",
        "--master",
        "spark://spark-master:7077",
        "--packages",
        ",".join(
            [
                "org.apache.hadoop:hadoop-aws:3.3.4",
                "com.amazonaws:aws-java-sdk-bundle:1.12.262",
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.1",
            ]
        ),
        f"/opt/aether/{script_path}",
    ]

    proc = _docker_exec("acp-spark-master", cmd)
    raise typer.Exit(code=proc.returncode)


@app.command("ls")
def ls_objects(
    prefix: str = typer.Argument(..., help="MinIO prefix, e.g. bronze/acp/sample_events"),
) -> None:
    """
    Lists objects in MinIO using the mc client.
    """
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

    proc = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "acp-net",
            "--entrypoint",
            "/bin/sh",
            "minio/mc:RELEASE.2025-01-17T23-25-50Z",
            "-lc",
            script,
        ]
    )
    raise typer.Exit(code=proc.returncode)


# ======================================================================================================================
# Redpanda commands
# ======================================================================================================================

def _rpk(args: list[str]) -> int:
    proc = _run(["docker", "exec", "-i", "acp-redpanda", "rpk", *args])
    return proc.returncode


@redpanda_app.command("topics")
def redpanda_topics() -> None:
    """
    Lists Redpanda topics.
    """
    raise typer.Exit(code=_rpk(["topic", "list"]))


@redpanda_app.command("produce")
def redpanda_produce(
    topic: str = typer.Argument(..., help="Topic name"),
    n: int = typer.Option(10, help="Number of messages"),
    prefix: str = typer.Option("event_", help="Message prefix"),
) -> None:
    """
    Produces N simple messages to a topic.
    """
    script = f'for i in $(seq 1 {n}); do echo "{prefix}$i"; done | rpk topic produce {topic} --brokers redpanda:9092'
    proc = _run(["docker", "exec", "-i", "acp-redpanda", "bash", "-lc", script])
    raise typer.Exit(code=proc.returncode)


@redpanda_app.command("consume")
def redpanda_consume(
    topic: str = typer.Argument(..., help="Topic name"),
    n: int = typer.Option(10, help="Number of messages"),
) -> None:
    """
    Consumes N messages from a topic.
    """
    raise typer.Exit(code=_rpk(["topic", "consume", topic, "--brokers", "redpanda:9092", "-n", str(n)]))


# ======================================================================================================================
# SQL command
# ======================================================================================================================

@app.command("sql")
def sql(
    query: str = typer.Argument(..., help="SQL query to execute in Trino"),
) -> None:
    """
    Executes a SQL query in Trino.
    """
    trino_exec(query)


# ======================================================================================================================
# Bronze commands
# ======================================================================================================================

@bronze_app.command("register")
def bronze_register(
    table: str = typer.Argument(..., help="Table name to register in raw.bronze"),
    dt: str = typer.Argument(..., help="Partition date, e.g. 2026-03-02"),
    drop_first: bool = typer.Option(True, "--drop/--no-drop", help="Drop table first to re-register cleanly"),
) -> None:
    """
    Registers a Bronze Parquet partition as an external table in Trino.
    """
    trino_exec(_bronze_schema_sql())

    if drop_first:
        trino_exec(f"DROP TABLE IF EXISTS raw.bronze.{table}")

    trino_exec(_bronze_create_table_sql(table, dt))
    typer.echo(f"Registered raw.bronze.{table} for dt={dt}")


@bronze_app.command("tables")
def bronze_tables() -> None:
    """
    Lists tables in raw.bronze.
    """
    trino_exec("SHOW TABLES FROM raw.bronze")


@bronze_app.command("count")
def bronze_count(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
) -> None:
    """
    Shows row count for a Bronze table.
    """
    trino_exec(f"SELECT count(*) AS n FROM raw.bronze.{table}")


@bronze_app.command("sample")
def bronze_sample(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of rows to show"),
) -> None:
    """
    Shows sample rows from a Bronze table.
    """
    trino_exec(f"SELECT * FROM raw.bronze.{table} LIMIT {limit}")


@bronze_app.command("describe")
def bronze_describe(
    table: str = typer.Argument(..., help="Table name in raw.bronze"),
) -> None:
    """
    Describes columns and types for a Bronze table.
    """
    trino_exec(f"DESCRIBE raw.bronze.{table}")


if __name__ == "__main__":
    app()
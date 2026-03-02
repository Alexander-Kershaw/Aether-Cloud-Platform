from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table



app = typer.Typer(add_completion=False, help="AETHER Cloud Platform (ACP) CLI")
console = Console()

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker" / "compose.yml"
ENV_FILE = REPO_ROOT / ".env"



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
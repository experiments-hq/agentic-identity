"""ACP command-line interface."""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="acp", help="Agent Control Plane CLI")
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev mode)"),
):
    """Start the ACP server."""
    import uvicorn
    uvicorn.run("acp.main:app", host=host, port=port, reload=reload, log_level="info")


@app.command()
def register(
    org_id: str = typer.Option(..., help="Organization ID"),
    team_id: str = typer.Option(..., help="Team ID"),
    name: str = typer.Option(..., help="Agent display name"),
    framework: str = typer.Option("custom", help="Agent framework"),
    environment: str = typer.Option("development", help="Environment"),
    created_by: str = typer.Option("cli", help="Registering user ID"),
    acp_url: str = typer.Option("http://localhost:8000", help="ACP server URL"),
):
    """Register a new agent and print its JWT token."""
    import httpx

    async def _run():
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{acp_url}/api/agents",
                json={
                    "org_id": org_id,
                    "team_id": team_id,
                    "display_name": name,
                    "framework": framework,
                    "environment": environment,
                    "created_by": created_by,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        table = Table(title="Agent Registered")
        table.add_column("Field", style="bold cyan")
        table.add_column("Value")
        for k, v in data.items():
            if k == "token":
                table.add_row(k, f"[dim]{v[:40]}...[/dim]")
            else:
                table.add_row(k, str(v))
        console.print(table)
        console.print(f"\n[bold green]JWT Token:[/bold green]\n{data['token']}\n")
        console.print("[yellow]Save this token — it will not be shown again.[/yellow]")

    asyncio.run(_run())


@app.command()
def fleet(
    org_id: str = typer.Option(None, help="Filter by org"),
    acp_url: str = typer.Option("http://localhost:8000", help="ACP server URL"),
):
    """List all registered agents."""
    import httpx

    async def _run():
        params = {}
        if org_id:
            params["org_id"] = org_id
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{acp_url}/api/agents", params=params)
            resp.raise_for_status()
            agents = resp.json()

        table = Table(title=f"Agent Fleet ({len(agents)} agents)")
        for col in ["agent_id", "display_name", "framework", "environment", "status", "last_seen_at"]:
            table.add_column(col)
        for a in agents:
            table.add_row(
                a["agent_id"][:8] + "…",
                a["display_name"],
                a["framework"],
                a["environment"],
                f"[green]{a['status']}[/green]" if a["status"] == "active" else f"[red]{a['status']}[/red]",
                (a["last_seen_at"] or "never")[:19],
            )
        console.print(table)

    asyncio.run(_run())


@app.command()
def verify_audit(
    acp_url: str = typer.Option("http://localhost:8000", help="ACP server URL"),
):
    """Verify the audit log hash chain integrity."""
    import httpx

    async def _run():
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{acp_url}/api/audit/verify")
            resp.raise_for_status()
            result = resp.json()

        if result["valid"]:
            console.print("[bold green]✓ Audit log integrity verified[/bold green]")
        else:
            console.print(f"[bold red]✗ Tampering detected at event: {result['tampered_event_id']}[/bold red]")

    asyncio.run(_run())


@app.command("demo-seed")
def demo_seed(
    replace_existing: bool = typer.Option(
        True,
        help="Replace the built-in demo dataset before seeding fresh records.",
    ),
):
    """Seed a repeatable demo org so the ACP console opens with meaningful data."""
    from acp.database import AsyncSessionLocal, create_all_tables
    from acp.demo import DEMO_ORG_ID, seed_demo_data

    async def _run():
        await create_all_tables()
        async with AsyncSessionLocal() as db:
            counts = await seed_demo_data(db, replace_existing=replace_existing)

        table = Table(title="ACP Demo Seed Complete")
        table.add_column("Resource", style="bold cyan")
        table.add_column("Count")
        table.add_row("Agents", str(counts["agents"]))
        table.add_row("Policies", str(counts["policies"]))
        table.add_row("Traces", str(counts["traces"]))
        table.add_row("Approvals", str(counts["approvals"]))
        console.print(table)
        console.print("[bold green]Console:[/bold green] http://localhost:8000/console/")
        console.print(f"[bold green]Demo Org:[/bold green] {DEMO_ORG_ID}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()

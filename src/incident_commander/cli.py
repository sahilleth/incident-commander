"""CLI for Incident Commander."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from incident_commander.config import get_settings
from incident_commander.orchestrator.commander import IncidentCommander
from incident_commander.state.store import IncidentStore

app = typer.Typer(
    name="incident-commander",
    help="Multi-agent incident commander for production incidents",
)
console = Console()


async def _get_commander() -> tuple[IncidentCommander, IncidentStore]:
    settings = get_settings()
    store = IncidentStore(settings.incident_db_path)
    await store.init()
    return IncidentCommander(settings, store), store


@app.command("open")
def open_incident(
    service: str = typer.Argument(..., help="Kubernetes Deployment name"),
    trigger: str = typer.Option("manual", help="Trigger source"),
    severity: str = typer.Option("SEV2", help="Severity"),
    namespace: str = typer.Option("default", help="K8s namespace"),
) -> None:
    """Open and investigate a new incident against a live cluster."""
    asyncio.run(_open(service, trigger, severity, namespace))


async def _open(service: str, trigger: str, severity: str, namespace: str) -> None:
    commander, _ = await _get_commander()
    incident = await commander.open_incident(
        service=service,
        trigger=trigger,
        severity=severity,
        namespace=namespace,
    )
    _print_incident(incident)


@app.command("show")
def show(incident_id: str) -> None:
    """Show incident details."""
    asyncio.run(_show(incident_id))


async def _show(incident_id: str) -> None:
    _, store = await _get_commander()
    incident = await store.get(incident_id)
    if incident is None:
        console.print(f"[red]Incident {incident_id} not found[/red]")
        raise typer.Exit(1)
    _print_incident(incident)


@app.command("list")
def list_incidents() -> None:
    """List recent incidents."""
    asyncio.run(_list())


async def _list() -> None:
    _, store = await _get_commander()
    incidents = await store.list_recent()
    table = Table(title="Recent Incidents")
    table.add_column("ID")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Severity")
    table.add_column("Opened")
    for i in incidents:
        table.add_row(
            i.incident_id,
            i.service,
            i.status.value,
            i.severity,
            i.opened_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@app.command("approve")
def approve(incident_id: str, approval_id: str) -> None:
    """Approve a pending mitigation action."""
    asyncio.run(_approve(incident_id, approval_id))


async def _approve(incident_id: str, approval_id: str) -> None:
    commander, _ = await _get_commander()
    incident = await commander.approve_action(incident_id, approval_id)
    _print_incident(incident)


@app.command("eval")
def run_eval(
    fixtures: str | None = typer.Option(
        None,
        help="Directory containing eval scenario JSON files (default: packaged fixtures)",
    ),
) -> None:
    """Run eval/replay scenarios and score hypothesis quality."""
    asyncio.run(_run_eval(fixtures))


async def _run_eval(fixtures: str | None) -> None:
    from pathlib import Path

    from incident_commander.eval.paths import default_fixtures_dir
    from incident_commander.eval.runner import EvalRunner

    settings = get_settings()
    runner = EvalRunner(settings)
    fixtures_dir = Path(fixtures) if fixtures else default_fixtures_dir()
    report = await runner.run_directory(fixtures_dir)

    table = Table(title="Eval Report")
    table.add_column("Scenario")
    table.add_column("Passed")
    table.add_column("Score")
    for result in report.results:
        table.add_row(
            result.scenario_id,
            "yes" if result.passed else "no",
            f"{result.score:.0%}",
        )
    console.print(table)
    console.print(
        f"\nTotal: {report.total}  Passed: {report.passed}  Failed: {report.failed}"
    )
    if report.failed:
        for result in report.results:
            if not result.passed:
                console.print(f"\n[red]{result.scenario_id}[/red]")
                for line in result.details:
                    console.print(f"  {line}")


@app.command("record")
def record_incident(
    incident_id: str,
    out: str = typer.Option(
        "eval/fixtures/recorded.json",
        help="Output fixture path",
    ),
) -> None:
    """Record an incident timeline as an eval fixture for replay."""
    asyncio.run(_record(incident_id, out))


async def _record(incident_id: str, out: str) -> None:
    from pathlib import Path

    from incident_commander.eval.runner import EvalRunner

    _, store = await _get_commander()
    incident = await store.get(incident_id)
    if incident is None:
        console.print(f"[red]Incident {incident_id} not found[/red]")
        raise typer.Exit(1)

    settings = get_settings()
    runner = EvalRunner(settings)
    path = await runner.record_incident(
        incident, Path(out), description=f"Recorded from {incident_id}"
    )
    console.print(f"[green]Recorded eval fixture:[/green] {path}")


@app.command("export")
def export_incident(
    incident_id: str,
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: postmortems/<INC-ID>.md)",
    ),
) -> None:
    """Export incident postmortem as Markdown."""
    asyncio.run(_export(incident_id, output))


async def _export(incident_id: str, output: str | None) -> None:
    from pathlib import Path

    from incident_commander.export.postmortem import write_postmortem_markdown

    _, store = await _get_commander()
    incident = await store.get(incident_id)
    if incident is None:
        console.print(f"[red]Incident {incident_id} not found[/red]")
        raise typer.Exit(1)

    out_path = Path(output or f"postmortems/{incident_id}.md")
    path = write_postmortem_markdown(incident, out_path)
    console.print(f"[green]Postmortem written:[/green] {path}")


@app.command("doctor")
def doctor() -> None:
    """Check kubectl, Prometheus, and Loki connectivity."""
    asyncio.run(_doctor())


async def _doctor() -> None:
    settings = get_settings()
    console.print(Panel.fit("Incident Commander — environment check", style="bold blue"))

    table = Table()
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    try:
        from incident_commander.tools.kubectl import Kubectl

        k = Kubectl(settings)
        out = await k.run(["cluster-info"])
        first_line = out.splitlines()[0][:60]
        table.add_row("kubectl", "ok", first_line)
    except Exception as exc:
        table.add_row("kubectl", "fail", str(exc)[:80])

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.prometheus_url.rstrip('/')}/-/ready")
            if r.status_code == 200:
                table.add_row("prometheus", "ok", settings.prometheus_url)
            else:
                table.add_row("prometheus", "optional", "not ready — metrics worker will skip")
    except Exception:
        table.add_row(
            "prometheus",
            "optional",
            "not running — metrics worker skips Prom queries",
        )

    if settings.log_backend == "loki":
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{settings.loki_url.rstrip('/')}/ready")
                table.add_row("loki", "ok" if r.status_code == 200 else "warn", settings.loki_url)
        except Exception as exc:
            table.add_row("loki", "fail", str(exc)[:80])
    else:
        table.add_row("logs", "kubectl", f"LOG_BACKEND={settings.log_backend}")

    if settings.llm_is_configured():
        key_detail = f"{settings.llm_provider_label()} — {settings.resolved_llm_model()}"
        if settings.groq_api_key_fallback.strip():
            key_detail += " (+ Groq fallback key)"
        table.add_row("llm", "configured", key_detail)
    else:
        table.add_row(
            "llm",
            "skipped",
            "No LLM — set GROQ_API_KEY or LLM_PROVIDER=ollama + Ollama running",
        )

    console.print(table)


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8080, help="Bind port"),
    reload: bool = typer.Option(False, help="Auto-reload"),
) -> None:
    """Start the API server."""
    import uvicorn

    uvicorn.run(
        "incident_commander.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


def _print_incident(incident) -> None:
    console.print()
    status_style = "green" if incident.status.value == "resolved" else "cyan"
    title = f"Incident {incident.incident_id} [{incident.status.value}]"
    console.print(Panel(incident.summary, title=title, border_style=status_style))

    if incident.worker_runs:
        table = Table(title="Worker Runs")
        table.add_column("Worker")
        table.add_column("Status")
        table.add_column("Summary")
        for run in incident.worker_runs:
            table.add_row(run.worker, run.status, run.summary[:80])
        console.print(table)


if __name__ == "__main__":
    app()

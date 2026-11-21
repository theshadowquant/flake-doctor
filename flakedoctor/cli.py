"""Flake Doctor CLI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .engine import diagnose

app = typer.Typer()
console = Console()


@app.callback()
def _callback() -> None:
    """Flake Doctor: diagnose flaky tests automatically."""


VERDICT_COLORS = {
    "BROKEN_BUILD": "bold red",
    "FLAKY_PRNG": "bold yellow",
    "FLAKY_TIMING": "bold yellow",
    "ORDER_DEPENDENT": "bold magenta",
    "POLLUTER": "bold dark_orange",
    "STABLE": "bold green",
}


@app.command()
def scan(
    test_file: Path = typer.Argument(
        "demo_sick_repo/test_patient_zero.py",
        help="Path to the test file to diagnose.",
    ),
    json_out: Optional[Path] = typer.Option(
        None, "--json", help="Write JSON report to this path."
    ),
) -> None:
    """Scan a test file and produce a Forensic Autopsy report."""
    console.print(f"\n[bold cyan]Flake Doctor[/bold cyan] scanning: {test_file}\n")

    reports = diagnose(test_file)

    table = Table(title="Forensic Autopsy", show_lines=True)
    table.add_column("Test Function", style="bold", min_width=28)
    table.add_column("Verdict", min_width=16)
    table.add_column("Root Cause & Culprit Predecessor", min_width=38)
    table.add_column("AST Line & Code Prescription", min_width=36)
    table.add_column("99% Confidence Run Count", min_width=12)

    for r in reports:
        color = VERDICT_COLORS.get(r.verdict, "white")
        verdict_cell = f"[{color}]{r.verdict}[/{color}]"

        # Root cause + culprit
        root_cause_cell = r.root_cause
        if r.culprit:
            root_cause_cell += f"\nCulprit: {r.culprit}"

        # AST findings
        if r.findings:
            ast_parts = []
            for f in r.findings[:2]:  # show up to 2 findings
                ast_parts.append(f"L{f.line} [{f.category}]\n{f.prescription}")
            ast_cell = "\n---\n".join(ast_parts)
        else:
            ast_cell = "N/A"

        # Confidence
        if r.confidence_runs is not None:
            conf_cell = str(r.confidence_runs)
        else:
            conf_cell = "N/A"

        table.add_row(r.name, verdict_cell, root_cause_cell, ast_cell, conf_cell)

    console.print(table)

    if json_out is not None:
        data = [r.to_dict() for r in reports]
        json_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"\n[green]JSON report written to:[/green] {json_out}")


if __name__ == "__main__":
    app()

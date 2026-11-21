"""Flake Doctor CLI."""
from __future__ import annotations

import datetime
import difflib
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from .engine import diagnose, TestReport

app = typer.Typer()
console = Console(width=140)


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


def _render_table(reports: list[TestReport], title: str = "Forensic Autopsy") -> Table:
    table = Table(title=title, show_lines=True, width=140)
    table.add_column("Test Function", style="bold", no_wrap=True, min_width=30)
    table.add_column("Verdict", min_width=16)
    table.add_column("Root Cause & Culprit Predecessor", min_width=35)
    table.add_column("AST Line & Code Prescription", min_width=32)
    table.add_column("Est. clean runs (99%, conservative)", min_width=10)

    for r in reports:
        color = VERDICT_COLORS.get(r.verdict, "white")
        verdict_cell = f"[{color}]{r.verdict}[/{color}]"

        root_cause_cell = r.root_cause
        if r.culprit:
            root_cause_cell += f"\nCulprit: {r.culprit}"

        if r.verdict in ("FLAKY_PRNG", "FLAKY_TIMING") and r.ci_low is not None and r.ci_high is not None:
            pct = int(round(r.sweep_fail_rate * 100))
            low_pct = int(round(r.ci_low * 100))
            high_pct = int(round(r.ci_high * 100))
            root_cause_cell += f"\nest. {pct}% fail (95% CI {low_pct}%-{high_pct}%)"

        if r.findings:
            ast_parts = []
            for f in r.findings[:2]:
                if r.verdict == "ORDER_DEPENDENT" and r.culprit:
                    prefix = f"(in culprit {r.culprit}) "
                else:
                    prefix = ""
                ast_parts.append(f"{prefix}L{f.line} [{f.category}]\n{f.prescription}")
            ast_cell = "\n---\n".join(ast_parts)
        else:
            ast_cell = "N/A"

        conf_cell = str(r.conservative_clean_runs) if r.conservative_clean_runs is not None else "N/A"

        table.add_row(r.name, verdict_cell, root_cause_cell, ast_cell, conf_cell)

    return table


@app.command()
def scan(
    test_file: Path = typer.Argument(
        "demo_sick_repo/test_patient_zero.py",
        help="Path to the test file to diagnose.",
    ),
    json_out: Optional[Path] = typer.Option(
        None, "--json", help="Write JSON report to this path."
    ),
    patch: bool = typer.Option(False, "--patch", help="Generate and display unified diff of fixes."),
    verify_fix: bool = typer.Option(False, "--verify-fix", help="Apply fixes to temp copy and show Before/After table."),
    fail_on_flaky: bool = typer.Option(False, "--fail-on-flaky", help="Exit code 1 if any test is not STABLE."),
) -> None:
    """Scan a test file and produce a Forensic Autopsy report."""
    console.print(f"\n[bold cyan]Flake Doctor[/bold cyan] scanning: {test_file}\n")

    reports = diagnose(test_file)

    # Pull scan stats attached by engine
    elapsed = getattr(reports[0], "_scan_elapsed", 0.0) if reports else 0.0
    sub_count = getattr(reports[0], "_subprocess_count", 0) if reports else 0

    table = _render_table(reports)
    console.print(table)

    console.print(
        f"\n[dim]Scan completed in {elapsed:.1f}s | {sub_count} subprocess calls[/dim]"
    )

    timings = getattr(reports[0], "_timings", None) if reports else None
    if timings:
        from .engine import format_timings_table
        console.print("\n[bold]Phase Timings:[/bold]")
        console.print(format_timings_table(timings))

    if json_out is not None:
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data = {
            "generated_at": generated_at,
            "test_file": Path(test_file).as_posix(),
            "results": [r.to_dict() for r in reports],
        }
        json_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]JSON report written to:[/green] {json_out}")

    if patch or verify_fix:
        from .patcher import build_patch, verify_fix as do_verify_fix
        patched_src, udiff = build_patch(Path(test_file), reports)

        console.print("\n[bold cyan]--- Unified Diff (fixes.patch) ---[/bold cyan]")
        syntax = Syntax(udiff, "diff", theme="monokai", line_numbers=False)
        console.print(syntax)
        with open("fixes.patch", "w", encoding="utf-8", newline="\n") as f:
            f.write(udiff)
        console.print("[green]Diff written to fixes.patch[/green]")

        if verify_fix:
            after_reports = do_verify_fix(Path(test_file), patched_src)
            after_map = {r.name: r for r in after_reports}

            after_table = Table(title="After Fix", show_lines=True, width=140)
            after_table.add_column("Test Function", no_wrap=True, min_width=30)
            after_table.add_column("Before Verdict", min_width=16)
            after_table.add_column("After Verdict", min_width=16)

            healed = 0
            for r in reports:
                before_color = VERDICT_COLORS.get(r.verdict, "white")
                before_cell = f"[{before_color}]{r.verdict}[/{before_color}]"
                after_r = after_map.get(r.name)
                if after_r:
                    after_v = after_r.verdict
                else:
                    after_v = "UNKNOWN"
                improved = (r.verdict != "STABLE" and r.verdict != "BROKEN_BUILD" and after_v == "STABLE") or \
                           (r.verdict == "BROKEN_BUILD" and after_v == "BROKEN_BUILD")
                if r.verdict != after_v and after_v == "STABLE":
                    healed += 1
                after_color = VERDICT_COLORS.get(after_v, "white")
                if improved or after_v == "STABLE":
                    after_cell = f"[bold green]{after_v}[/bold green]"
                else:
                    after_cell = f"[{after_color}]{after_v}[/{after_color}]"
                after_table.add_row(r.name, before_cell, after_cell)

            console.print(after_table)
            remaining_bugs = sum(1 for r in after_reports if r.verdict == "BROKEN_BUILD")
            bug_word = "bug remains" if remaining_bugs == 1 else "bugs remain"
            console.print(
                f"\n[bold]{healed} of {len(reports)} tests healed, "
                f"{remaining_bugs} genuine {bug_word}[/bold]"
            )


@app.command()
def web(
    port: int = typer.Option(8080, "--port", "-p", help="Port to run web console on"),
) -> None:
    """Launch the interactive Flake Doctor Web Console."""
    from .web import run_server
    run_server(port=port)


if __name__ == "__main__":
    app()

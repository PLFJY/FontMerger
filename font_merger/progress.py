from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table


class ProgressReporter:
    def __init__(self, total_jobs: int, stages_per_job: int = 8) -> None:
        self.total_jobs = total_jobs
        self.stages_per_job = stages_per_job
        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[bright_black]{task.fields[status]}"),
            TimeElapsedColumn(),
            console=self.console,
        )
        self.overall_task: TaskID | None = None
        self.current_task: TaskID | None = None

    def __enter__(self) -> "ProgressReporter":
        self.progress.__enter__()
        self.overall_task = self.progress.add_task(
            "Overall",
            total=self.total_jobs,
            status="Waiting",
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.progress.__exit__(exc_type, exc, tb)

    def start_job(self, index: int, label: str) -> None:
        if self.current_task is not None:
            self.progress.remove_task(self.current_task)
        self.current_task = self.progress.add_task(
            f"[{index}/{self.total_jobs}] {label}",
            total=self.stages_per_job,
            status="Starting",
        )
        if self.overall_task is not None:
            self.progress.update(self.overall_task, status=label)

    def advance(self, message: str) -> None:
        if self.current_task is not None:
            self.progress.advance(self.current_task, 1)
            self.progress.update(self.current_task, status=message)

    def finish_job(self, output_path: Path, added: int) -> None:
        if self.current_task is not None:
            self.progress.update(self.current_task, completed=self.stages_per_job, status="Done")
        if self.overall_task is not None:
            self.progress.advance(self.overall_task, 1)

        table = Table.grid(padding=(0, 1))
        table.add_column(style="bright_black")
        table.add_column()
        table.add_row("Added", f"{added} fallback Unicode mappings")
        table.add_row("Wrote", str(output_path))
        self.console.print(table)

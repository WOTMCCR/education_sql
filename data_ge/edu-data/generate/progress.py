"""Rich-based progress helpers with a plain-text fallback."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from typing import Any


def _load_rich() -> tuple[Any, Any, Any, Any, Any, Any]:
    console_module = import_module("rich.console")
    progress_module = import_module("rich.progress")
    return (
        console_module.Console,
        progress_module.Progress,
        progress_module.ProgressColumn,
        progress_module.SpinnerColumn,
        progress_module.TextColumn,
        progress_module.TimeElapsedColumn,
    )


try:
    (
        Console,
        Progress,
        ProgressColumn,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    ) = _load_rich()
except ModuleNotFoundError:
    Console = None
    Progress = None
    ProgressColumn = None
    SpinnerColumn = None
    TextColumn = None
    TimeElapsedColumn = None


_console = Console() if Console is not None else None
_progress: Any | None = None
_task_ids: dict[str, int] = {}
_completed_tables: set[str] = set()
_progress_column_base: Any = ProgressColumn if ProgressColumn is not None else object


class RowsPerSecondColumn(_progress_column_base):
    def render(self, task: Any) -> str:
        speed = task.speed or 0
        if speed >= 1000:
            return f"{speed / 1000:,.1f}k rows/s"
        return f"{speed:,.0f} rows/s"


def console_print(message: str) -> None:
    if _console is not None:
        _console.print(message)
    else:
        print(message)


@contextmanager
def progress_context():
    global _progress
    if Progress is None:
        yield
        return
    assert ProgressColumn is not None
    assert SpinnerColumn is not None
    assert TextColumn is not None
    assert TimeElapsedColumn is not None

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        TextColumn("{task.completed:,.0f} rows"),
        RowsPerSecondColumn(),
        TimeElapsedColumn(),
        console=_console,
        refresh_per_second=4,
        transient=False,
    )
    with progress:
        _progress = progress
        try:
            yield
        finally:
            _progress = None
            _task_ids.clear()
            _completed_tables.clear()


def start_table_progress(table_name: str, total_rows: int) -> None:
    if _progress is None or table_name in _task_ids:
        return
    _completed_tables.discard(table_name)
    _task_ids[table_name] = _progress.add_task(table_name, total=total_rows or None)


def advance_table_progress(table_name: str, completed_rows: int) -> None:
    if _progress is None or completed_rows <= 0:
        return
    task_id = _task_ids.get(table_name)
    if task_id is not None:
        _progress.advance(task_id, completed_rows)


def finish_table_progress(table_name: str, completed_rows: int | None = None) -> None:
    if _progress is None:
        _task_ids.pop(table_name, None)
        if completed_rows is not None:
            _completed_tables.add(table_name)
            console_print(f"  [OK] {table_name}: {completed_rows} rows")
        return
    task_id = _task_ids.pop(table_name, None)
    if task_id is not None:
        _progress.stop_task(task_id)
        _progress.remove_task(task_id)
    if completed_rows is not None and table_name not in _completed_tables:
        _completed_tables.add(table_name)
        console_print(f"  [OK] {table_name}: {completed_rows} rows")


def is_table_completed(table_name: str) -> bool:
    return table_name in _completed_tables


def reset_progress_tasks() -> None:
    if _progress is None:
        _task_ids.clear()
        _completed_tables.clear()
        return
    for task_id in list(_task_ids.values()):
        _progress.remove_task(task_id)
    _task_ids.clear()
    _completed_tables.clear()


def complete_progress_tasks() -> None:
    reset_progress_tasks()

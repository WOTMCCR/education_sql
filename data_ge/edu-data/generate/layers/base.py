"""Base class for data generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import LAYERS
from ..progress import (
    complete_progress_tasks,
    console_print,
    is_table_completed,
    reset_progress_tasks,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


class BaseGenerator(ABC):
    layer: int = 0
    layer_name: str = ""

    def local_now(self) -> datetime:
        """Return the current Asia/Shanghai local time as a naive datetime."""
        return datetime.now(LOCAL_TZ).replace(tzinfo=None, microsecond=0)

    def log(self, message: str) -> None:
        console_print(message)

    def header(self) -> None:
        reset_progress_tasks()
        name = self.layer_name or LAYERS[self.layer]["name"]
        console_print(f"\n{'=' * 64}")
        console_print(f"Layer {self.layer}: {name}")
        console_print(f"{'=' * 64}")

    def log_table_counts(self, counts: dict[str, int]) -> None:
        for table in LAYERS[self.layer]["tables"]:
            if not is_table_completed(table):
                console_print(f"  [OK] {table}: {counts.get(table, 0)} rows")
        complete_progress_tasks()

    @abstractmethod
    def run(self) -> None:
        """Run generator."""

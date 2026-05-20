from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphError(Exception):
    stage: str
    code: str
    message: str
    retryable: bool = False

    def as_dict(self) -> dict[str, str]:
        return {"stage": self.stage, "code": self.code, "message": self.message}


class DataQaError(GraphError):
    pass


class MetaQaError(GraphError):
    pass


NON_RETRYABLE_CODES = {
    "METRIC_NOT_DEFINED",
    "DIMENSION_NOT_ALLOWED",
    "SQL_UNSAFE",
    "LLM_OUTPUT_INVALID",
}


def is_retryable_error(error: dict[str, str] | GraphError | None) -> bool:
    if error is None:
        return False
    if isinstance(error, GraphError):
        return error.retryable and error.code not in NON_RETRYABLE_CODES
    return str(error.get("code") or "") not in NON_RETRYABLE_CODES and str(error.get("retryable") or "").lower() == "true"

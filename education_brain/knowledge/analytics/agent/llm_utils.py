from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from knowledge.analytics.agent.llm_schema import StructuredIntent, parse_model
from knowledge.core.structured_llm import StructuredLlmClient


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class LlmNodeResult:
    parsed: BaseModel | None
    raw_response: str
    stage: dict[str, Any]
    error: dict[str, str] | None = None


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def summarize_for_trace(value: Any, *, max_chars: int = 8000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "chars": len(text), "preview": text[:max_chars]}


def call_structured_llm(
    *,
    stage: str,
    prompt_name: str,
    response_model: type[BaseModel],
    user_payload: dict[str, Any],
    max_tokens: int = 1200,
    timeout: float = 45.0,
) -> LlmNodeResult:
    client_result = StructuredLlmClient(prompt_dir=PROMPT_DIR).invoke_schema(
        stage=stage,
        prompt_name=prompt_name,
        response_model=response_model,
        payload=user_payload,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    stage_trace = client_result.trace.as_stage()
    if client_result.error:
        return LlmNodeResult(
            parsed=None,
            raw_response=client_result.raw_response,
            error=client_result.error,
            stage={**stage_trace, "message": client_result.error["message"]},
        )
    return LlmNodeResult(parsed=client_result.parsed, raw_response=client_result.raw_response, stage=stage_trace)


def parse_llm_schema(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_llm_json(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_structured_output(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_pydantic_json(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)

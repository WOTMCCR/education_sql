from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from knowledge.analytics.agent.llm_schema import parse_model
from knowledge.core import llm as core_llm
from knowledge.core.config import get_settings


@dataclass(frozen=True)
class LlmTrace:
    stage: str
    status: str
    duration_ms: int
    provider: str
    model: str
    output_mode: str = ""
    usage: dict[str, Any] | None = None
    errors: list[str] | None = None
    prompt_name: str = ""

    def as_stage(self) -> dict[str, Any]:
        return {
            "name": self.stage,
            "status": self.status,
            "durationMs": self.duration_ms,
            "llm_called": self.status != "skipped",
            "provider": self.provider,
            "model": self.model,
            "promptSummary": {"name": self.prompt_name, "outputMode": self.output_mode},
            "outputSummary": {"mode": self.output_mode, "schemaValidated": self.status == "ok"},
            "usage": self.usage or {"usageUnavailable": True},
            "llm": {
                "called": self.status != "skipped",
                "provider": self.provider,
                "model": self.model,
                "outputMode": self.output_mode,
                "usage": self.usage or {"usageUnavailable": True},
                **({"errors": self.errors} if self.errors else {}),
            },
        }


@dataclass(frozen=True)
class StructuredLlmResult:
    parsed: BaseModel | None
    raw_response: str
    trace: LlmTrace
    error: dict[str, str] | None = None


class StructuredLlmClient:
    def __init__(self, *, prompt_dir: Path, settings: Any | None = None):
        self.prompt_dir = prompt_dir
        self.settings = settings

    def invoke_schema(
        self,
        *,
        stage: str,
        prompt_name: str,
        response_model: type[BaseModel],
        payload: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int = 1200,
        timeout: float = 45.0,
        purpose: str | None = None,
    ) -> StructuredLlmResult:
        started = time.perf_counter()
        settings = self.settings or get_settings()
        if not settings.openai_api_key or not settings.llm_model:
            trace = LlmTrace(stage, "error", _elapsed(started), "openai-compatible", settings.llm_model or "", "unavailable", prompt_name=prompt_name)
            return StructuredLlmResult(
                parsed=None,
                raw_response="",
                trace=trace,
                error={"stage": stage, "code": "LLM_UNAVAILABLE", "message": "需要配置 OPENAI_API_KEY 和 LLM_MODEL。"},
            )

        prompt = (self.prompt_dir / f"{prompt_name}.md").read_text(encoding="utf-8")
        errors: list[str] = []
        for mode in ("json_schema", "json_object", "json_prompt"):
            messages = _messages(prompt, payload, mode)
            response_format = _response_format(response_model, stage, mode)
            result = core_llm.chat_completion_text(
                model=settings.llm_model,
                messages=messages,
                purpose=purpose or f"analytics.{stage}",
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                trigger_cooldown=False,
                response_format=response_format,
                return_metadata=True,
            )
            if result is None:
                errors.append(f"{mode}: empty or failed response")
                continue
            raw = result.text if isinstance(result, core_llm.ChatCompletionTextResult) else str(result)
            usage = result.usage if isinstance(result, core_llm.ChatCompletionTextResult) else {"usageUnavailable": True}
            model = result.model if isinstance(result, core_llm.ChatCompletionTextResult) else settings.llm_model
            try:
                parsed = parse_model(raw, response_model)
            except ValueError as e:
                errors.append(f"{mode}: {e}")
                continue
            trace = LlmTrace(stage, "ok", _elapsed(started), "openai-compatible", model, mode, usage, prompt_name=prompt_name)
            return StructuredLlmResult(parsed=parsed, raw_response=raw, trace=trace)

        unavailable = errors and all("empty or failed response" in error for error in errors)
        code = "LLM_UNAVAILABLE" if unavailable else "LLM_OUTPUT_INVALID"
        message = "LLM 不可用或返回空内容。" if unavailable else "LLM 输出不可用或无法通过结构化 schema 校验。"
        trace = LlmTrace(stage, "error", _elapsed(started), "openai-compatible", settings.llm_model, "unavailable", errors=errors, prompt_name=prompt_name)
        return StructuredLlmResult(parsed=None, raw_response="", trace=trace, error={"stage": stage, "code": code, "message": message})


def _elapsed(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _messages(system_prompt: str, payload: dict[str, Any], mode: str) -> list[dict[str, str]]:
    suffix = "\n\n只输出一个 JSON object，不要输出 markdown、解释或额外文本。" if mode == "json_prompt" else ""
    return [
        {"role": "system", "content": system_prompt + suffix},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2, default=str)},
    ]


def _response_format(model: type[BaseModel], stage: str, mode: str) -> dict[str, Any] | None:
    if mode == "json_object":
        return {"type": "json_object"}
    if mode == "json_prompt":
        return None
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{stage}_schema",
            "strict": True,
            "schema": _strict_schema(model.model_json_schema()),
        },
    }


def _strict_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_strict_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "default":
            continue
        if key in {"properties", "$defs", "definitions"} and isinstance(value, dict):
            result[key] = {prop_name: _strict_schema(prop_schema) for prop_name, prop_schema in value.items()}
        else:
            result[key] = _strict_schema(value)
    if result.get("type") == "object" or "properties" in result:
        properties = result.get("properties") or {}
        result["additionalProperties"] = False
        result["required"] = list(properties.keys())
    if not any(key in result for key in ("type", "anyOf", "oneOf", "allOf", "$ref", "enum", "const")):
        result["anyOf"] = [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]}},
            {"type": "null"},
        ]
    return result

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from knowledge.analytics.agent.llm_schema import StructuredIntent, parse_model
from knowledge.core import llm as core_llm
from knowledge.core.config import get_settings


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
STRUCTURED_MODES = ("json_schema", "json_object", "json_prompt")


@dataclass(frozen=True)
class LlmNodeResult:
    parsed: BaseModel | None
    raw_response: str
    stage: dict[str, Any]
    error: dict[str, str] | None = None


def llm_config_error(stage: str) -> dict[str, str] | None:
    settings = get_settings()
    if not settings.openai_api_key or not settings.llm_model:
        return {
            "stage": stage,
            "code": "LLM_UNAVAILABLE",
            "message": "Iteration 03 LLM NL2SQL 需要配置 OPENAI_API_KEY 和 LLM_MODEL。",
        }
    return None


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def summarize_for_trace(value: Any, *, max_chars: int = 8000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "chars": len(text), "preview": text[:max_chars]}


def _json_schema_response_format(model: type[BaseModel], name: str) -> dict[str, Any]:
    def make_strict(schema: Any) -> Any:
        if isinstance(schema, list):
            return [make_strict(item) for item in schema]
        if not isinstance(schema, dict):
            return schema
        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "default":
                continue
            if key in {"properties", "$defs", "definitions"} and isinstance(value, dict):
                result[key] = {prop_name: make_strict(prop_schema) for prop_name, prop_schema in value.items()}
            else:
                result[key] = make_strict(value)
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

    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": make_strict(model.model_json_schema()),
        },
    }


def _json_object_response_format() -> dict[str, str]:
    return {"type": "json_object"}


def _messages(system_prompt: str, user_payload: dict[str, Any], mode: str) -> list[dict[str, str]]:
    user_json = json.dumps(user_payload, ensure_ascii=False, indent=2, default=str)
    suffix = ""
    if mode == "json_prompt":
        suffix = "\n\n只输出一个 JSON object，不要输出 markdown、解释或额外文本。"
    return [
        {"role": "system", "content": system_prompt + suffix},
        {"role": "user", "content": user_json},
    ]


def call_structured_llm(
    *,
    stage: str,
    prompt_name: str,
    response_model: type[BaseModel],
    user_payload: dict[str, Any],
    max_tokens: int = 1200,
    timeout: float = 45.0,
) -> LlmNodeResult:
    config_error = llm_config_error(stage)
    started = time.perf_counter()
    settings = get_settings()
    prompt = load_prompt(prompt_name)

    if config_error:
        return LlmNodeResult(
            parsed=None,
            raw_response="",
            error=config_error,
            stage={
                "name": stage,
                "status": "error",
                "durationMs": round((time.perf_counter() - started) * 1000),
                "llm": {
                    "called": False,
                    "provider": "openai-compatible",
                    "model": settings.llm_model or "",
                    "errorCode": "LLM_UNAVAILABLE",
                    "usage": {"usageUnavailable": True},
                },
                "message": config_error["message"],
            },
        )

    errors: list[str] = []
    for mode in STRUCTURED_MODES:
        messages = _messages(prompt, user_payload, mode)
        response_format = None
        if mode == "json_schema":
            response_format = _json_schema_response_format(response_model, f"{stage}_schema")
        elif mode == "json_object":
            response_format = _json_object_response_format()

        result = core_llm.chat_completion_text(
            model=settings.llm_model,
            messages=messages,
            purpose=f"analytics.{stage}",
            temperature=0.0,
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
        usage = (
            result.usage
            if isinstance(result, core_llm.ChatCompletionTextResult)
            else {"usageUnavailable": True}
        )
        try:
            parsed = parse_model(raw, response_model)
        except ValueError as e:
            errors.append(f"{mode}: {e}")
            continue

        llm_trace = {
            "called": True,
            "provider": "openai-compatible",
            "model": result.model if isinstance(result, core_llm.ChatCompletionTextResult) else settings.llm_model,
            "outputMode": mode,
            "prompt": summarize_for_trace(messages),
            "rawResponse": raw[:12000],
            "usage": usage or {"usageUnavailable": True},
            **({"degradedFrom": list(STRUCTURED_MODES[: STRUCTURED_MODES.index(mode)])} if mode != "json_schema" else {}),
        }
        stage_trace = {
            "name": stage,
            "status": "ok",
            "durationMs": round((time.perf_counter() - started) * 1000),
            "llm_called": True,
            "provider": llm_trace["provider"],
            "model": llm_trace["model"],
            "prompt": llm_trace["prompt"],
            "rawResponse": llm_trace["rawResponse"],
            "usage": llm_trace["usage"],
            "llm": llm_trace,
        }
        return LlmNodeResult(parsed=parsed, raw_response=raw, stage=stage_trace)

    unavailable = errors and all("empty or failed response" in error for error in errors)
    message = "LLM 不可用或返回空内容。" if unavailable else "LLM 输出不可用或无法通过结构化 schema 校验。"
    code = "LLM_UNAVAILABLE" if unavailable else "LLM_OUTPUT_INVALID"
    return LlmNodeResult(
        parsed=None,
        raw_response="",
        error={"stage": stage, "code": code, "message": message},
        stage={
            "name": stage,
            "status": "error",
            "durationMs": round((time.perf_counter() - started) * 1000),
            "llm": {
                "called": True,
                "provider": "openai-compatible",
                "model": settings.llm_model,
                "outputMode": "unavailable",
                "prompt": summarize_for_trace(_messages(prompt, user_payload, "json_prompt")),
                "rawResponse": "",
                "usage": {"usageUnavailable": True},
                "errors": errors,
            },
            "message": message,
        },
    )


def parse_llm_schema(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_llm_json(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_structured_output(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)


def parse_pydantic_json(raw: str, model: type[BaseModel]) -> BaseModel:
    return parse_model(raw, model)

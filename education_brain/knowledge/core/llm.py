"""统一的 LLM 调用包装。

负责：
1. 统一走 knowledge.core.clients.get_openai()
2. 将异常转换为 warning 日志，避免调用方各自散落 try/except
3. 在本地兼容接口不可用时快速失败并返回 None
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from knowledge.core.clients import get_openai
from knowledge.core.config import get_settings

logger = logging.getLogger(__name__)

_llm_unavailable_until = 0.0


@dataclass(frozen=True)
class ChatCompletionTextResult:
    text: str
    usage: dict[str, Any]
    model: str


def _mark_llm_temporarily_unavailable(seconds: float) -> None:
    global _llm_unavailable_until
    _llm_unavailable_until = max(_llm_unavailable_until, time.monotonic() + seconds)


def _llm_is_temporarily_unavailable() -> bool:
    return time.monotonic() < _llm_unavailable_until


def _is_local_ollama_base_url(base_url: str) -> bool:
    if not base_url:
        return False
    parsed = urlparse(base_url)
    return (parsed.hostname or "").lower() in {"localhost", "127.0.0.1"} and parsed.path.rstrip("/").endswith("/v1")


def _chat_via_ollama_api(
    *,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
    max_tokens: int | None,
) -> str | None:
    settings = get_settings()
    parsed = urlparse(settings.openai_base_url)
    ollama_api_url = f"{parsed.scheme}://{parsed.netloc}/api/chat"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
    }
    if max_tokens is not None:
        payload["options"] = {"num_predict": max_tokens}

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(ollama_api_url, json=payload)
            resp.raise_for_status()
        data = resp.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        return content or None
    except Exception as e:
        logger.warning("Ollama /api/chat no-think 回退失败: %s", e)
        return None


def chat_completion_text(
    *,
    model: str,
    messages: list[dict[str, str]],
    purpose: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float | None = None,
    trigger_cooldown: bool = True,
    response_format: dict[str, Any] | None = None,
    return_metadata: bool = False,
) -> str | ChatCompletionTextResult | None:
    """统一的 chat completion 文本调用。

    返回：
    - 成功：去首尾空白后的文本
    - 失败或空响应：None
    """
    settings = get_settings()
    if _llm_is_temporarily_unavailable():
        logger.warning("%s 跳过: LLM 暂时不可用", purpose)
        return None

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout if timeout is not None else settings.openai_timeout_seconds,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if response_format is not None:
        kwargs["response_format"] = response_format

    try:
        client = get_openai()
        resp = client.chat.completions.create(**kwargs)
        message = resp.choices[0].message
        text = (message.content or "").strip()
        if not text and getattr(message, "reasoning", None) and _is_local_ollama_base_url(settings.openai_base_url):
            logger.warning("%s 返回空 content，尝试走 Ollama /api/chat no-think 回退", purpose)
            text = _chat_via_ollama_api(
                model=model,
                messages=messages,
                timeout=kwargs["timeout"],
                max_tokens=max_tokens,
            ) or ""
        if not text:
            logger.warning("%s 返回空内容", purpose)
            return None
        global _llm_unavailable_until
        _llm_unavailable_until = 0.0
        if return_metadata:
            usage_obj = getattr(resp, "usage", None)
            usage = {}
            if usage_obj is not None:
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                }
            else:
                usage = {"usageUnavailable": True}
            return ChatCompletionTextResult(text=text, usage=usage, model=getattr(resp, "model", model) or model)
        return text
    except Exception as e:
        logger.warning("%s 失败: %s", purpose, e)
        if trigger_cooldown:
            _mark_llm_temporarily_unavailable(settings.llm_failure_cooldown_seconds)
        return None

import asyncio
from collections.abc import AsyncGenerator

import httpx as _httpx  # 用于 Ollama 原生流式回退

@dataclass
class StreamChunk:
    """流式输出的最小单元
    kind 取值：
    - "thinking":模型推理过程(deepseek-r1 的 reasoning 输出)
    - "content"：最终回答正文的增量文本

    为什么用 dataclass 而不是 dict?
    类型安全 + IDE 自动补全。后续拼接逻辑只需判断 chunk.kind == "content",
    不用担心 dict key 拼错。
    """
    kind : str   # "thinking" | "content"
    text : str

async def chat_completion_stream(
    *,
    model: str,
    messages: list[dict[str, str]],
    purpose: str,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> AsyncGenerator[StreamChunk, None]:
    """异步流式 chat completion — 逐 chunk 产出 thinking/content。

    这是流式路径的核心函数。与同步版 chat_completion_text() 的区别：

    1. 返回 AsyncGenerator 而非 str，调用方用 async for 消费
    2. 区分 thinking 和 content 两种 chunk 类型
    3. 不做全局 cooldown（流式场景失败时直接抛异常，由上层处理）

    thinking 识别策略（优先级从高到低）：
    1. delta 中有 reasoning_content 字段 → thinking(deepseek-r1 通过 OpenAI 兼容 API)
    2. delta 中有 reasoning 字段 → thinking(某些 Ollama 版本)
    3. delta.content → content(所有模型通用)
    4. 以上都没有 → 跳过该 chunk

    如果 OpenAI 兼容流式返回为空（deepseek-r1 已知问题），
    回退到 Ollama 原生 /api/chat 流式接口。
    """
    settings = get_settings()

    # 快速失败:LLM处于冷却期
    if _llm_is_temporarily_unavailable():
        logger.warning("%s 流式跳过: LLM 暂时不可用", purpose)
        return
    
    effective_timeout = timeout if timeout is not None else settings.answer_timeout_seconds

    # ── 策略1：走 OpenAI 兼容流式 ──
    got_content = False
    try :
        from knowledge.core.clients import get_async_openai
        client = get_async_openai()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "timeout": effective_timeout,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = await client.chat.completions.create(**kwargs)

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            # 1) 检查 reasoning/thinking 字段（deepseek-r1）
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if reasoning:
                yield StreamChunk(kind="thinking", text=reasoning)
            
            # 2)检查 content 字段
            if delta.content:
                got_content = True
                yield StreamChunk(kind="content", text=delta.content)
    
    except Exception as e:
        logger.warning("%s OpenAI 兼容流式失败: %s", purpose, e)
        # 不在这里 return，尝试 Ollama 回退
    
    # ── 策略2：Ollama 原生 /api/chat 流式回退 ──
    # 条件：本地 Ollama + OpenAI 兼容流式没有产出正文内容
    # reasoning/thinking 不能视为最终回答，否则会错过原生回退。
    if not got_content and _is_local_ollama_base_url(settings.openai_base_url):
        logger.info("%s 回退到 Ollama 原生流式 /api/chat", purpose)
        async for chunk in _stream_via_ollama_api(
            model=model,
            messages=messages,
            timeout=effective_timeout,
            max_tokens=max_tokens,
        ):
            yield chunk

async def _stream_via_ollama_api(
    *,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
    max_tokens: int | None,
) -> AsyncGenerator[StreamChunk, None]:
    """Ollama 原生 /api/chat 流式回退。

    Ollama 的 /api/chat 流式响应格式：
    每行一个 JSON 对象，结构为：
    {"message": {"role": "assistant", "content": "...", "thinking": "..."}, "done": false}

    最后一行 done=true 时结束。

    为什么需要这个回退？
    deepseek-r1 通过 Ollama 的 OpenAI 兼容层 (/v1/chat/completions) 流式输出时，
    有时 content 字段为空（reasoning 被吞掉）。直接调原生 API 可以拿到完整输出。
    """
    settings = get_settings()
    parsed = urlparse(settings.openai_base_url)
    ollama_api_url = f"{parsed.scheme}://{parsed.netloc}/api/chat"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,       # 关键：开启流式
        # 对回答生成优先关闭 thinking，避免只收到推理流却没有正文。
        "think": False,
    }

    if max_tokens is not None:
        payload["options"] = {"num_predict": max_tokens}

    try:
        async with _httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
            # stream=True 让 httpx 逐行读取而非等全部完成
            async with client.stream("POST", ollama_api_url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    import json
                    data = json.loads(line)

                    msg = data.get("message", {})

                    # thinking 字段（Ollama 原生）
                    thinking_text = msg.get("thinking", "")
                    if thinking_text:
                        yield StreamChunk(kind="thinking", text=thinking_text)

                    # content 字段
                    content_text = msg.get("content", "")
                    if content_text:
                        yield StreamChunk(kind="content", text=content_text)

                    if data.get("done", False):
                        break
    except Exception as e:
        logger.warning("Ollama 原生流式回退失败: %s", e)



from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knowledge.core.clients import probe_milvus, probe_minio, probe_mongodb
from knowledge.core.config import get_settings

# 把一个 async 生成器函数变成一个异步上下文管理器。
# with 语句进入时执行 yield 之前，退出时执行 yield 之后。yield 本身是控制权交还的那一刻。

"""
span , yield 把整个函数的执行时间线切成了三段：
时间轴 ──────────────────────────────────────────────────────►

  [Span 1: 启动区间]   [Span 2: 运行区间]   [Span 3: 关闭区间]
  ┌───────────────┐   ┌───────────────────┐   ┌──────────────┐
  │ yield 之前代码 │──►│  yield (挂起等待)  │──►│ yield 之后代码│
  └───────────────┘   └───────────────────┘   └──────────────┘
        │                      │                      │
   uvicorn 启动            接收 HTTP 请求          进程退出前
   端口绑定前              无限期等待信号           释放资源
"""

@asynccontextmanager
async def lifespan(app : FastAPI):
    # ── yield 之前：应用启动时执行 ──
    # 比如：预加载模型、预热连接池、打印启动日志
    # 当前我们用懒加载，所以这里什么都不做
    yield
    # ── yield 之后：应用关闭时执行 ──
    # 比如：关闭连接、释放 GPU 显存

settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )


from knowledge.api.routes.ingest import router as ingest_router
from knowledge.api.routes.search import router as search_router
from knowledge.api.routes.chat import router as chat_router
from knowledge.api.routes.analytics import router as analytics_router

app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(analytics_router)



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 健康检测
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _run_health_check(
    name: str,
    check,
    timeout_seconds: float,
) -> tuple[str, str]:
    try:
        check(timeout_seconds)
        return name, "ok"
    except Exception as e:
        return name, f"error: {e}"


@app.get("/health")
def health_check():
    settings = get_settings()
    timeout_seconds = settings.health_check_timeout_seconds
    available_checks = {
        "mongodb": probe_mongodb,
        "milvus": probe_milvus,
        "minio": probe_minio,
    }
    required = settings.health_required_dependencies or ["mongodb"]
    results = [
        _run_health_check(name, available_checks[name], timeout_seconds)
        for name in required
        if name in available_checks
    ]
    checks = dict(results)

    all_ok = all( v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "components": checks,
        "required": list(checks.keys()),
    }

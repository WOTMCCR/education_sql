"""
统一配置管理

使用 pydantic-settings 自动从 .env 和环境变量读取,
自动类型转换和校验 , 缺少必需字段时报清晰错误
"""
import json
from functools import cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parent
_ENV_FILE = PACKAGE_DIR / ".env"


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── FastAPI ──
    app_name: str = "Wode-education-knowledge"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    health_check_timeout_seconds: float = 1.0
    health_required_dependencies: Annotated[list[str], NoDecode] = ["mongodb"]
    cors_allow_origins: Annotated[list[str], NoDecode] = []
    cors_allow_methods: Annotated[list[str], NoDecode] = ["*"]
    cors_allow_headers: Annotated[list[str], NoDecode] = ["*"]
    cors_allow_credentials: bool = False

    # ── LLM ──
    openai_api_key: str = Field("", repr=False)
    openai_base_url: str = ""
    openai_timeout_seconds: float = 30.0
    answer_timeout_seconds: float = 120.0
    llm_failure_cooldown_seconds: float = 3
    # 意图分类、查询改写、HyDE 生成等通用场景
    llm_model: str = ""
    # 答案生成（可以用更强的模型），为空时 fallback 到 llm_model
    answer_model: str = ""

    # ── MongoDB ──
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "education_knowledge"

    # ── 教育问数依赖 ──
    analytics_mysql_host: str = "127.0.0.1"
    analytics_mysql_port: int = 3306
    analytics_mysql_user: str = "root"
    analytics_mysql_password: str = Field("123321", repr=False)
    analytics_mysql_database: str = "edu"
    analytics_mysql_timeout_seconds: float = 2.0

    analytics_qdrant_url: str = "http://127.0.0.1:6333"
    analytics_qdrant_column_collection: str = "edu_column_info"
    analytics_qdrant_metric_collection: str = "edu_metric_info"
    analytics_qdrant_timeout_seconds: float = 2.0

    analytics_es_url: str = "http://127.0.0.1:9200"
    analytics_es_dimension_values_index: str = "edu_dimension_values"
    analytics_es_timeout_seconds: float = 2.0

    analytics_embedding_url: str = "http://127.0.0.1:8081"
    analytics_embedding_timeout_seconds: float = 5.0
    analytics_embedding_mode: str = "tei"

    # ── Milvus ──
    milvus_uri: str = "http://localhost:19530"
    milvus_user: str = ""
    milvus_password: str = Field("", repr=False)
    milvus_token: str = Field("", repr=False)
    milvus_db_name: str = ""
    # 文档 chunk 向量检索的 collection
    milvus_collection: str = "edu_chunks"

    # ── MinIO ──
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = Field("minioadmin", repr=False)
    minio_bucket: str = "education-knowledge"
    minio_secure: bool = False

    # ── BGE 模型 ──
    bge_m3_path: str = "BAAI/bge-m3"
    bge_reranker_path: str = "BAAI/bge-reranker-v2-m3"
    bge_device: str = "cuda"
    bge_fp16: bool = True
    embedding_dim: int = 1024

    # ── 文档分块参数 ──
    max_content_length: int = 2000
    min_content_length: int = 500
    overlap_sentences: int = 1
    embedding_batch_size: int = 8

    # ── 向量检索 ──
    query_dense_weight: float = 0.5
    query_sparse_weight: float = 0.5
    query_search_limit: int = 5

    # ── HyDE ──
    # 为空时 fallback 到 llm_model
    hyde_model: str = ""
    enable_hyde: bool = True


    # ── RRF 融合 ──
    rrf_k: int = 60
    rrf_max_results: int = 10

    # ── Rerank ──
    rerank_min_top_k: int = 3
    rerank_max_top_k: int = 10
    rerank_gap_abs: float = 0.5
    rerank_gap_ratio: float = 0.25
    rerank_min_score: float | None = None
    enable_rerank: bool = False

    # ── 答案生成 ──
    max_context_chars: int = 12000
    answer_max_context_chars: int = 3000
    answer_max_tokens: int = 512

    # ── 流式输出 ──
    stream_timeout_seconds: float = 180.0       # 单个流式任务总超时
    stream_keepalive_seconds: float = 15.0      # SSE 空闲心跳间隔
    stream_task_ttl_seconds: float = 300.0      # 已完成任务的清理 TTL


    # ── 数据路径 ──
    data_dir: str = "data/数据"

    # ── docx 转换 ──
    # markitdown 失败时是否自动尝试 pandoc
    docx_fallback_pandoc: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off", "release", "prod", "production", "warn", "warning", "info", "error", "critical"}:
                return False
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
        return value

    @field_validator("data_dir", mode="before")
    @classmethod
    def normalize_data_dir(cls, value: object) -> object:
        if isinstance(value, (str, Path)):
            return str(_resolve_project_path(value))
        return value

    @field_validator("health_required_dependencies", "cors_allow_origins", "cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def parse_list_settings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def minio_base_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"

    @property
    def analytics_mysql_connect_kwargs(self) -> dict[str, object]:
        return {
            "host": self.analytics_mysql_host,
            "port": self.analytics_mysql_port,
            "user": self.analytics_mysql_user,
            "password": self.analytics_mysql_password,
            "database": self.analytics_mysql_database,
            "charset": "utf8mb4",
        }

    @property
    def effective_answer_model(self) -> str:
        return self.answer_model or self.llm_model

    @property
    def effective_hyde_model(self) -> str:
        return self.hyde_model or self.llm_model

    @property
    def effective_milvus_token(self) -> str:
        if self.milvus_token:
            return self.milvus_token
        if self.milvus_user and self.milvus_password:
            return f"{self.milvus_user}:{self.milvus_password}"
        return ""

    @property
    def data_dir_path(self) -> Path:
        return Path(self.data_dir)

    def resolve_path(self, value: str | Path) -> Path:
        return _resolve_project_path(value)

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})


@cache
def get_settings() -> Settings:
    return Settings()

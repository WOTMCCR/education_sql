"""
统一配置管理

使用 pydantic-settings 自动从 .env 和环境变量读取,
自动类型转换和校验 , 缺少必需字段时报清晰错误
"""
import json
from functools import cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = PACKAGE_DIR / ".env"

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
    analytics_mysql_user: str = ""
    analytics_mysql_password: str = Field("", repr=False)
    analytics_mysql_database: str = ""
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

    embedding_dim: int = 1024


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

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})


@cache
def get_settings() -> Settings:
    return Settings()

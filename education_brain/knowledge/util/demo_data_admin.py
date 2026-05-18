"""Deprecated old document RAG demo-data admin entrypoint.

Iteration 04 removes `/ingest`, `/search`, Milvus document chunks, and MinIO
document assets from the education data QA product path. This module remains as
a stable import target for older local tooling, but its old destructive
operations are intentionally disabled.
"""

from __future__ import annotations

import argparse


DEPRECATION_MESSAGE = (
    "旧文档 RAG 演示数据管理工具已停用。当前数据准备入口是 "
    "`data_ge/edu-data` 的 `uv run init_db.py`、"
    "`uv run -m generate.main --profile smoke`，以及 "
    "`education_brain` 的 `knowledge.analytics.build_meta --recreate`。"
)


def reset_demo_data(*, include_minio: bool = False) -> dict:
    del include_minio
    raise RuntimeError(DEPRECATION_MESSAGE)


def run_reimport_sequence(*args, **kwargs) -> list[dict]:
    del args, kwargs
    raise RuntimeError(DEPRECATION_MESSAGE)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deprecated old document RAG demo-data admin")
    parser.add_argument("command", nargs="?", choices=["reset", "reimport"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    parser.parse_args(argv)
    parser.error(DEPRECATION_MESSAGE)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

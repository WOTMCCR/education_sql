import pytest

from knowledge.util import demo_data_admin


def test_old_demo_data_admin_is_disabled():
    with pytest.raises(RuntimeError, match="旧文档 RAG 演示数据管理工具已停用"):
        demo_data_admin.reset_demo_data(include_minio=True)


def test_old_reimport_sequence_is_disabled():
    with pytest.raises(RuntimeError, match="旧文档 RAG 演示数据管理工具已停用"):
        demo_data_admin.run_reimport_sequence(api_base_url="http://127.0.0.1:8000")

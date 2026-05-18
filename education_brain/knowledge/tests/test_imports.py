import importlib


def test_knowledge_core_clients_imports_from_package_namespace():
    module = importlib.import_module("knowledge.core.clients")

    assert module.__name__ == "knowledge.core.clients"

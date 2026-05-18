from types import SimpleNamespace

from knowledge.api import app as app_module
from knowledge.core import clients


def _failing_check(timeout_seconds):
    raise TimeoutError(f"timeout after {timeout_seconds:.2f}s")


def test_health_check_defaults_to_mongodb_only(monkeypatch):
    seen = []

    def record_check(timeout_seconds):
        seen.append(timeout_seconds)

    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_name="test-app",
            health_check_timeout_seconds=0.25,
            health_required_dependencies=["mongodb"],
        ),
    )
    monkeypatch.setattr(app_module, "probe_mongodb", record_check)

    result = app_module.health_check()

    assert seen == [0.25]
    assert result["status"] == "healthy"
    assert result["required"] == ["mongodb"]
    assert result["components"] == {"mongodb": "ok"}


def test_health_check_ignores_removed_legacy_dependencies(monkeypatch):
    seen = []

    def record_check(timeout_seconds):
        seen.append(timeout_seconds)

    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_name="test-app",
            health_check_timeout_seconds=0.25,
            health_required_dependencies=["mongodb", "milvus", "minio"],
        ),
    )
    monkeypatch.setattr(app_module, "probe_mongodb", record_check)

    result = app_module.health_check()

    assert seen == [0.25]
    assert result["status"] == "healthy"
    assert result["required"] == ["mongodb"]
    assert result["components"] == {"mongodb": "ok"}


def test_probe_mongodb_uses_configured_client_timeouts(monkeypatch):
    captured = {}

    class FakeMongoAdmin:
        def command(self, name):
            captured["command"] = name

    class FakeMongoClient:
        def __init__(self, uri, **kwargs):
            captured["uri"] = uri
            captured["kwargs"] = kwargs
            self.admin = FakeMongoAdmin()

    monkeypatch.setattr(clients, "MongoClient", FakeMongoClient)
    monkeypatch.setattr(
        clients,
        "get_settings",
        lambda: SimpleNamespace(mongo_uri="mongodb://test"),
    )

    clients.probe_mongodb(0.25)

    assert captured["uri"] == "mongodb://test"
    assert captured["command"] == "ping"
    assert captured["kwargs"]["serverSelectionTimeoutMS"] == 250
    assert captured["kwargs"]["connectTimeoutMS"] == 250
    assert captured["kwargs"]["socketTimeoutMS"] == 250


def test_health_check_reports_dependency_failures(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_name="test-app",
            health_check_timeout_seconds=0.05,
            health_required_dependencies=["mongodb"],
        ),
    )
    monkeypatch.setattr(app_module, "probe_mongodb", _failing_check)

    result = app_module.health_check()

    assert result["status"] == "degraded"
    assert result["components"]["mongodb"].startswith("error: timeout after 0.05s")

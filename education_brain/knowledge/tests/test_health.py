import time
from types import SimpleNamespace

from knowledge.api import app as app_module
from knowledge.core import clients


def _slow_check(timeout_seconds):
    del timeout_seconds
    time.sleep(0.2)


def _failing_check(timeout_seconds):
    raise TimeoutError(f"timeout after {timeout_seconds:.2f}s")


def test_health_check_passes_timeout_to_all_checks(monkeypatch):
    seen = []

    def record_check(timeout_seconds):
        seen.append(timeout_seconds)

    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_name="test-app",
            minio_bucket="bucket",
            health_check_timeout_seconds=0.25,
        ),
    )
    monkeypatch.setattr(app_module, "probe_mongodb", record_check)
    monkeypatch.setattr(app_module, "probe_milvus", record_check)
    monkeypatch.setattr(app_module, "probe_minio", record_check)

    result = app_module.health_check()

    assert seen == [0.25, 0.25, 0.25]
    assert result["status"] == "healthy"


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


def test_probe_milvus_uses_configured_timeouts(monkeypatch):
    captured = {}

    class FakeMilvusClient:
        def __init__(self, *, uri, user="", password="", db_name="", token="", timeout):
            captured["uri"] = uri
            captured["user"] = user
            captured["password"] = password
            captured["db_name"] = db_name
            captured["token"] = token
            captured["init_timeout"] = timeout

        def list_collections(self, **kwargs):
            captured["list_timeout"] = kwargs["timeout"]

    monkeypatch.setattr(clients, "MilvusClient", FakeMilvusClient)
    monkeypatch.setattr(
        clients,
        "get_settings",
        lambda: SimpleNamespace(
            milvus_uri="http://milvus.test:19530",
            milvus_user="root",
            milvus_password="milvus",
            milvus_db_name="default",
            effective_milvus_token="root:milvus",
        ),
    )

    clients.probe_milvus(0.25)

    assert captured["uri"] == "http://milvus.test:19530"
    assert captured["user"] == "root"
    assert captured["password"] == "milvus"
    assert captured["db_name"] == "default"
    assert captured["token"] == "root:milvus"
    assert captured["init_timeout"] == 0.25
    assert captured["list_timeout"] == 0.25


def test_get_milvus_uses_configured_auth(monkeypatch):
    captured = {}

    class FakeMilvusClient:
        def __init__(self, *, uri, user="", password="", db_name="", token="", timeout=None):
            captured["uri"] = uri
            captured["user"] = user
            captured["password"] = password
            captured["db_name"] = db_name
            captured["token"] = token
            captured["timeout"] = timeout

    monkeypatch.setattr(clients, "MilvusClient", FakeMilvusClient)
    monkeypatch.setattr(
        clients,
        "get_settings",
        lambda: SimpleNamespace(
            milvus_uri="http://milvus.test:19530",
            milvus_user="root",
            milvus_password="milvus",
            milvus_db_name="default",
            effective_milvus_token="root:milvus",
        ),
    )
    monkeypatch.setattr(clients, "_milvus_client", None)

    client = clients.get_milvus()

    assert isinstance(client, FakeMilvusClient)
    assert captured["uri"] == "http://milvus.test:19530"
    assert captured["user"] == "root"
    assert captured["password"] == "milvus"
    assert captured["db_name"] == "default"
    assert captured["token"] == "root:milvus"
    assert captured["timeout"] is None


def test_probe_minio_builds_short_timeout_http_client(monkeypatch):
    captured = {}

    class FakeMinioClient:
        def __init__(self, endpoint, **kwargs):
            captured["endpoint"] = endpoint
            captured["kwargs"] = kwargs

        def bucket_exists(self, bucket_name):
            captured["bucket"] = bucket_name

    monkeypatch.setattr(clients, "Minio", FakeMinioClient)
    monkeypatch.setattr(
        clients,
        "get_settings",
        lambda: SimpleNamespace(
            minio_endpoint="127.0.0.1:9000",
            minio_access_key="key",
            minio_secret_key="secret",
            minio_secure=False,
            minio_bucket="bucket",
        ),
    )

    clients.probe_minio(0.25)

    http_client = captured["kwargs"]["http_client"]

    assert captured["endpoint"] == "127.0.0.1:9000"
    assert captured["bucket"] == "bucket"
    assert http_client.connection_pool_kw["retries"].total == 0
    assert http_client.connection_pool_kw["timeout"].connect_timeout == 0.25


def test_health_check_reports_dependency_failures(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            app_name="test-app",
            minio_bucket="bucket",
            health_check_timeout_seconds=0.05,
        ),
    )
    monkeypatch.setattr(app_module, "probe_mongodb", _failing_check)
    monkeypatch.setattr(app_module, "probe_milvus", _slow_check)
    monkeypatch.setattr(app_module, "probe_minio", _slow_check)

    result = app_module.health_check()

    assert result["status"] == "degraded"
    assert result["components"]["mongodb"].startswith("error: timeout after 0.05s")
    assert result["components"]["milvus"] == "ok"
    assert result["components"]["minio"] == "ok"

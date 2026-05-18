from pathlib import Path

from knowledge import main


def test_main_uses_package_app_with_root_app_dir(monkeypatch):
    called = {}

    def fake_run(app, **kwargs):
        called["app"] = app
        called["kwargs"] = kwargs

    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.main()

    package_dir = Path(main.__file__).resolve().parent
    project_root = package_dir.parent

    assert called["app"] == "knowledge.api.app:app"
    assert called["kwargs"]["app_dir"] == str(project_root)
    assert called["kwargs"]["reload_dirs"] == [str(package_dir)]

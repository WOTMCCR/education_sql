from pathlib import Path

import uvicorn


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent


def main():
    uvicorn.run(
        "knowledge.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=str(PROJECT_ROOT),
        reload_dirs=[str(PACKAGE_DIR)],
    )


if __name__ == "__main__":
    main()

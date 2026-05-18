from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge.analytics.meta_store import build_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build education data QA metadata indexes.")
    parser.add_argument(
        "--config",
        default="../data_ge/edu-data/meta/education_meta.yaml",
        help="Path to education_meta.yaml. Defaults to the repo layout used by Iteration 01.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate Qdrant collections and Elasticsearch index before indexing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    counts = build_all(config_path, recreate=args.recreate)
    print(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Data generation entrypoint."""

from __future__ import annotations

import argparse

from .config import GENERATION_DEFAULTS, generation_profile
from .db import close_db, init_db, interrupt_db
from .layers.layer1 import Layer1Generator
from .layers.layer2 import Layer2Generator
from .layers.layer3 import Layer3Generator
from .layers.layer4 import Layer4Generator
from .layers.layer5 import Layer5Generator
from .layers.layer6 import Layer6Generator
from .layers.layer7 import Layer7Generator
from .progress import console_print, progress_context

GENERATORS = (
    Layer1Generator,
    Layer2Generator,
    Layer3Generator,
    Layer4Generator,
    Layer5Generator,
    Layer6Generator,
    Layer7Generator,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Education data generator")
    parser.add_argument(
        "--profile",
        choices=("smoke", "full"),
        default="full",
        help="generation profile",
    )
    parser.add_argument(
        "--layers",
        default="1,2,3,4,5,6,7",
        help="comma-separated layer numbers",
    )
    return parser.parse_args()


def run_generators(layer_numbers: set[int]) -> None:
    for generator_cls in GENERATORS:
        if generator_cls.layer in layer_numbers:
            generator_cls().run()


def main() -> None:
    args = parse_args()
    layer_numbers = {int(item) for item in args.layers.split(",") if item.strip()}
    unsupported = layer_numbers - {generator.layer for generator in GENERATORS}
    if unsupported:
        raise SystemExit(f"unsupported layer(s): {sorted(unsupported)}")

    interrupted = False
    init_db()
    try:
        with generation_profile(args.profile):
            with progress_context():
                console_print(
                    f"Generation profile: {args.profile} -> {GENERATION_DEFAULTS}"
                )
                run_generators(layer_numbers)
    except KeyboardInterrupt:
        interrupted = True
        console_print(
            "\nGeneration interrupted by user, interrupting database connection..."
        )
        interrupt_db()
        raise SystemExit(130)
    finally:
        if not interrupted:
            close_db()


if __name__ == "__main__":
    main()

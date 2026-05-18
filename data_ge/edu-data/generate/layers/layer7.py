"""Layer7: final acceptance checks."""

from __future__ import annotations

from .base import BaseGenerator
from .validations import validate_layer7


class Layer7Generator(BaseGenerator):
    layer = 7
    layer_name = "最终验收"

    def run(self) -> None:
        self.header()
        for check in validate_layer7():
            self.log(f"  [OK] validation: {check}")

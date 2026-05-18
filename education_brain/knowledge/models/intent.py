from dataclasses import dataclass, field


@dataclass(slots=True)
class IntentResult:
    intent: str
    slots: dict[str, str] = field(default_factory=dict)
    confidence: str = "rule"

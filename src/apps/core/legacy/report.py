from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Report:
    counts: Counter = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)

    def add(self, label: str, n: int = 1) -> None:
        self.counts[label] += n

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def render(self) -> str:
        lines = ["Перенесено:", *(f"  {label}: {n}" for label, n in self.counts.items())]
        if self.warnings:
            lines += ["", f"Предупреждения ({len(self.warnings)}):", *(f"  - {w}" for w in self.warnings)]
        return "\n".join(lines)

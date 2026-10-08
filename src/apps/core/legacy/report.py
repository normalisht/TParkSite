from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Report:
    counts: Counter = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)
    used_files: set[Path] = field(default_factory=set)

    def add(self, label: str, n: int = 1) -> None:
        self.counts[label] += n

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def use(self, path: Path) -> None:
        """Файл из старой папки images разобран импортом (перенесён или отбракован с предупреждением)."""
        self.used_files.add(path.resolve())

    def render(self) -> str:
        lines = ["Перенесено:", *(f"  {label}: {n}" for label, n in self.counts.items())]
        if self.warnings:
            lines += ["", f"Предупреждения ({len(self.warnings)}):", *(f"  - {w}" for w in self.warnings)]
        return "\n".join(lines)

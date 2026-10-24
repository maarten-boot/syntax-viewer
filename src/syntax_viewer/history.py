"""Browser-style navigation history (FR-13). Qt-free so it can be unit-tested."""

from __future__ import annotations


class History:
    def __init__(self) -> None:
        self._back: list[str] = []
        self._forward: list[str] = []
        self.current: str | None = None

    def visit(self, name: str) -> None:
        if name == self.current:
            return
        if self.current is not None:
            self._back.append(self.current)
        self.current = name
        self._forward.clear()

    def can_back(self) -> bool:
        return bool(self._back)

    def can_forward(self) -> bool:
        return bool(self._forward)

    def back(self) -> str | None:
        if not self._back:
            return self.current
        self._forward.append(self.current)  # type: ignore[arg-type]
        self.current = self._back.pop()
        return self.current

    def forward(self) -> str | None:
        if not self._forward:
            return self.current
        self._back.append(self.current)  # type: ignore[arg-type]
        self.current = self._forward.pop()
        return self.current

    def clear(self) -> None:
        """Drop back/forward entries, keep the current symbol."""
        self._back.clear()
        self._forward.clear()

    def reset(self) -> None:
        """Forget everything (new file opened)."""
        self.clear()
        self.current = None

    def __len__(self) -> int:
        return len(self._back) + len(self._forward) + (self.current is not None)

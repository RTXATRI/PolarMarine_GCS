from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SequenceDisposition(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


@dataclass(slots=True)
class SequenceTracker:
    """Classify unsigned sequence numbers, including modular rollover."""

    bits: int = 32
    _last: dict[str, int] = field(default_factory=dict)

    def observe(self, stream_id: str, sequence: int) -> SequenceDisposition:
        modulus = 1 << self.bits
        if sequence < 0 or sequence >= modulus:
            raise ValueError(f"Sequence must be in [0, {modulus - 1}]")
        previous = self._last.get(stream_id)
        if previous is None:
            self._last[stream_id] = sequence
            return SequenceDisposition.NEW
        delta = (sequence - previous) % modulus
        if delta == 0:
            return SequenceDisposition.DUPLICATE
        if delta < modulus // 2:
            self._last[stream_id] = sequence
            return SequenceDisposition.NEW
        return SequenceDisposition.OUT_OF_ORDER

    def reset(self, stream_id: str) -> None:
        self._last.pop(stream_id, None)

    def clear(self) -> None:
        self._last.clear()

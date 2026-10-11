"""Byte-capped LRU with pin protection.

Semantics ported from ``Assets/FengChuanXiangFrames/Runtime/FengFrameLibrary.cs``:
move-to-front on hit (``:316``), eviction skips pinned entries (``:370``), an all-pinned cache
is allowed to run over capacity rather than destroy a frame that is on screen (``:433``),
capacity is clamped (``:415``) and a given key only ever reports one failure (``:538``).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable

MIN_CAPACITY = 1
MAX_CAPACITY = 256


@dataclass
class LruCache:
    capacity: int
    max_bytes: int | None = None
    weigh: Callable[[Any], int] = lambda _v: 0
    _data: "OrderedDict[Hashable, Any]" = field(default_factory=OrderedDict, init=False)
    _pinned: set = field(default_factory=set, init=False)
    _bytes: int = field(default=0, init=False)
    _misses: int = field(default=0, init=False)
    _evictions: int = field(default=0, init=False)
    _failures: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.capacity = max(MIN_CAPACITY, min(int(self.capacity), MAX_CAPACITY))

    def __len__(self) -> int:
        return len(self._data)

    @property
    def bytes(self) -> int:
        return self._bytes

    def get(self, key: Hashable) -> Any | None:
        if key not in self._data:
            self._misses += 1
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._bytes -= self.weigh(self._data[key])
            del self._data[key]
        self._data[key] = value
        self._data.move_to_end(key)
        self._bytes += self.weigh(value)
        self._evict()

    def pin(self, key: Hashable) -> None:
        self._pinned.add(key)

    def unpin(self, key: Hashable) -> None:
        self._pinned.discard(key)

    def evict_key(self, key: Hashable) -> None:
        if key in self._data:
            self._bytes -= self.weigh(self._data.pop(key))
        self._pinned.discard(key)

    def _over(self) -> bool:
        if len(self._data) > self.capacity:
            return True
        return self.max_bytes is not None and self._bytes > self.max_bytes

    def _evict(self) -> None:
        while self._over():
            victim = None
            keys = list(self._data)
            for k in keys[:-1]:               # oldest first; never evict what we just added
                if k not in self._pinned:
                    victim = k
                    break
            if victim is None:
                return                        # everything else is pinned -> run over capacity
            self._bytes -= self.weigh(self._data.pop(victim))
            self._evictions += 1

    def note_failure(self, key: Hashable) -> bool:
        """True the first time this key fails; later repeats are swallowed like the C# player does."""
        if key in self._failures:
            self._failures[key] += 1
            return False
        self._failures[key] = 1
        return True

    def report(self) -> str:
        return (f"size={len(self._data)}/{self.capacity} bytes={self._bytes} "
                f"misses={self._misses} evictions={self._evictions} pinned={len(self._pinned)} "
                f"failed_keys={len(self._failures)}")

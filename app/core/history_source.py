"""历史记录新写入来源契约."""

from typing import Literal, cast, get_args

HistoryWriteSource = Literal["farm_agent", "chat", "monitoring"]
_ALLOWED_HISTORY_WRITE_SOURCES = frozenset(get_args(HistoryWriteSource))


def validate_history_write_source(source: str) -> HistoryWriteSource:
    """校验新写入来源；历史记录读取不受此约束."""
    if source not in _ALLOWED_HISTORY_WRITE_SOURCES:
        raise ValueError(f"不允许写入历史记录来源: {source}")
    return cast(HistoryWriteSource, source)

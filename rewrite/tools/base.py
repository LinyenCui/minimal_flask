"""
工具的共用基礎型別
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """所有 tool 的統一回傳格式"""
    ok: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @classmethod
    def success(cls, data: Any = None, **meta) -> "ToolResult":
        return cls(ok=True, data=data, meta=meta)

    @classmethod
    def fail(cls, error: str, **meta) -> "ToolResult":
        return cls(ok=False, error=error, meta=meta)

    def __bool__(self):
        return self.ok

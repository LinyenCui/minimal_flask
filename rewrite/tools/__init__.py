"""
rewrite/tools/ — Atomic 純函數工具

每個工具：
  - 簽名 fn(*, session, **kwargs) -> ToolResult
  - 純函數，session 從參數傳入（修 N-6）
  - 不依賴 Flask globals
  - 可獨立測試 / 重用 / 包成 MCP server
"""

from rewrite.tools.base import ToolResult

__all__ = ['ToolResult']

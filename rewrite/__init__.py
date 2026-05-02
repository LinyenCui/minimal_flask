"""
rewrite/ — Rewrite v0.1 工作目錄

此目錄存放新版 LINE Bot 的程式碼，與既有 modules/ 並存。
依《rewrite_spec_v0.1.md》設計，可獨立測試、純函數、無 Flask globals 依賴。

結構：
  rewrite/
    tools/      — atomic 純函數工具（R-4）
    skills/     — AI 領域模組（將來）
    parsers/    — 快速命令 parsers（將來）
    views/      — Flex Message 渲染（將來）
"""

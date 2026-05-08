"""
rewrite v0.1 AI agent — Skill loader + Function Calling

對應 spec §6 設計：
  - LLMClient 抽象（spec §6.1）— 方便將來換 Provider（Gemini → Claude）
  - Skill 模式（spec §6.2）— 按意圖分類載入 prompt + tools 子集
  - 確認機制（spec §6.3）— mutation 提案 → 用戶確認 → 執行（後續 Phase 加）

v0.1 第一階段：單一 skill（trip_query），驗證整套架構能跑通。
之後再加 trip_mutation_skill / customer_skill / fixed_schedule_skill 等。
"""

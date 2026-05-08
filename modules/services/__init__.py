"""
服務模組初始化（Phase C 後）

Legacy AI / business services 全砍 — 業務邏輯走 rewrite/。
保留：ai_service / report_service / scheduler_service /
     incremental_sync_service / diagnosis_query_service
"""
from modules.services.report_service import handle_generate_weekly_report

__all__ = ['handle_generate_weekly_report']

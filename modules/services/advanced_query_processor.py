#!/usr/bin/env python3
"""
高級查詢處理器 - 處理AI生成的複雜查詢命令
支援複雜條件解析和動態SQL生成
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.conversation_context import get_conversation_context

logger = logging.getLogger(__name__)

class AdvancedQueryProcessor:
    """高級查詢處理器 - 將AI命令轉換為實際資料庫查詢"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_complex_query(self, ai_command: str, user_id: str) -> Dict:
        """處理AI生成的複雜查詢命令"""
        try:
            self.logger.info(f"🔍 處理複雜查詢: {ai_command}")
            
            # 🔥 新增：檢查是否為聚合查詢（總和、統計）
            is_aggregation = any(keyword in ai_command for keyword in ['總和', '總計', '統計金額', '統計'])
            
            # 解析命令類型
            if ai_command.startswith("統計金額") or (ai_command.startswith("查已完成") and is_aggregation):
                return self._process_completed_trips_query(ai_command, user_id, is_aggregation=True)
            elif ai_command.startswith("查已完成"):
                return self._process_completed_trips_query(ai_command, user_id, is_aggregation=False)
            elif ai_command.startswith("查詢班次"):
                return self._process_current_trips_query(ai_command, user_id)
            elif ai_command.startswith("查詢司機"):
                return self._process_driver_query(ai_command, user_id)
            else:
                # 回退到傳統處理
                return {"type": "fallback", "command": ai_command}
                
        except Exception as e:
            self.logger.error(f"❌ 複雜查詢處理失敗: {e}")
            return {"type": "error", "message": f"查詢處理失敗: {str(e)}"}
    
    def _process_completed_trips_query(self, command: str, user_id: str, is_aggregation: bool = False) -> Dict:
        """處理已完成班次的複雜查詢"""
        try:
            # 解析查詢條件
            conditions = self._parse_query_conditions(command)
            
            # 構建SQL查詢
            base_query = """
                SELECT 
                    ct.id,
                    ct.date,
                    ct.start_point,
                    ct.end_point,
                    ct.category,
                    ct.driver_id,
                    ct.meter_fare,
                    ct.extra_fare,
                    (ct.meter_fare + ct.extra_fare) as total_amount,
                    d.name as driver_name
                FROM completed_trips ct
                LEFT JOIN drivers d ON ct.driver_id = d.id
                WHERE 1=1
            """
            
            where_conditions = []
            params = {}
            
            # 添加日期條件
            if conditions.get('date'):
                date_condition, date_params = self._build_date_condition(conditions['date'])
                where_conditions.append(date_condition)
                params.update(date_params)
            
            # 添加類別條件
            if conditions.get('category'):
                where_conditions.append("ct.category = :category")
                params['category'] = conditions['category']
            
            # 添加司機條件
            if conditions.get('driver_id'):
                where_conditions.append("ct.driver_id = :driver_id")
                params['driver_id'] = conditions['driver_id']
            
            # 添加金額條件
            if conditions.get('amount_condition'):
                amount_condition = self._build_amount_condition(conditions['amount_condition'])
                if amount_condition:
                    where_conditions.append(amount_condition['sql'])
                    params.update(amount_condition['params'])
            
            # 組合完整查詢
            if where_conditions:
                full_query = base_query + " AND " + " AND ".join(where_conditions)
            else:
                full_query = base_query
                
            full_query += " ORDER BY ct.date DESC, ct.id DESC LIMIT 50"
            
            self.logger.info(f"📊 執行SQL: {full_query}")
            self.logger.info(f"📊 參數: {params}")
            
            # 執行查詢
            result = db.session.execute(text(full_query), params)
            trips = result.fetchall()
            
            # 保存查詢結果供翻頁使用
            context = get_conversation_context(user_id)
            context.save_query_result('completed_trips', command, trips, conditions)
            
            # 🔥 新增：聚合查詢處理
            if is_aggregation:
                return self._format_aggregation_result(trips, command, conditions)
            else:
                # 格式化結果
                return self._format_completed_trips_result(trips, command, conditions)
            
        except Exception as e:
            self.logger.error(f"❌ 已完成班次查詢失敗: {e}")
            return {"type": "error", "message": f"查詢失敗: {str(e)}"}
    
    def _process_current_trips_query(self, command: str, user_id: str) -> Dict:
        """處理當前班次的複雜查詢"""
        try:
            conditions = self._parse_query_conditions(command)
            
            # 檢查是否有無效狀態
            if conditions.get('invalid_status'):
                invalid_status = conditions['invalid_status']
                known_statuses = ['待派', '準備', '已完成', '取消']
                return {
                    "type": "invalid_status",
                    "message": f"❌ 狀態「{invalid_status}」不存在\n\n💡 可用的狀態：\n• {', '.join(known_statuses)}\n\n🔍 建議查詢：\n• 狀態為準備的班次\n• 狀態為已完成的班次",
                    "command": command,
                    "invalid_status": invalid_status,
                    "valid_statuses": known_statuses
                }
            
            base_query = """
                SELECT 
                    t.trip_id,
                    t.date,
                    t.time,
                    t.start_point,
                    t.end_point,
                    t.category,
                    t.driver_id,
                    t.status,
                    d.name as driver_name
                FROM trips t
                LEFT JOIN drivers d ON t.driver_id = d.id
                WHERE 1=1
            """
            
            where_conditions = []
            params = {}
            
            # 添加日期條件
            if conditions.get('date'):
                date_condition, date_params = self._build_date_condition(conditions['date'], 't')
                where_conditions.append(date_condition)
                params.update(date_params)
            
            # 添加狀態條件
            if conditions.get('status'):
                where_conditions.append("t.status = :status")
                params['status'] = conditions['status']
            
            # 添加類別條件
            if conditions.get('category'):
                if conditions['category'] == '東洋':
                    where_conditions.append("t.category IN ('東洋', '臨時')")
                else:
                    where_conditions.append("t.category = :category")
                    params['category'] = conditions['category']
            
            # 添加司機條件
            if conditions.get('driver_id'):
                where_conditions.append("t.driver_id = :driver_id")
                params['driver_id'] = conditions['driver_id']
            
            # 組合查詢
            if where_conditions:
                full_query = base_query + " AND " + " AND ".join(where_conditions)
            else:
                full_query = base_query
                
            full_query += " ORDER BY t.date, t.time"
            
            self.logger.info(f"📊 執行SQL: {full_query}")
            
            # 執行查詢
            result = db.session.execute(text(full_query), params)
            trips = result.fetchall()
            
            # 保存查詢結果供翻頁使用
            context = get_conversation_context(user_id)
            context.save_query_result('current_trips', command, trips, conditions)
            
            return self._format_current_trips_result(trips, command, conditions)
            
        except Exception as e:
            self.logger.error(f"❌ 當前班次查詢失敗: {e}")
            return {"type": "error", "message": f"查詢失敗: {str(e)}"}
    
    def _process_driver_query(self, command: str, user_id: str) -> Dict:
        """處理司機相關查詢（暫時回退到傳統處理）"""
        return {"type": "fallback", "command": command}
    
    def _parse_query_conditions(self, command: str) -> Dict:
        """解析查詢命令中的條件"""
        conditions = {}
        
        # 解析日期條件
        date_patterns = {
            '今天': 'today',
            '昨天': 'yesterday', 
            '明天': 'tomorrow',
            '本週': 'this_week',
            '上週': 'last_week'
        }
        
        for date_text, date_type in date_patterns.items():
            if date_text in command:
                conditions['date'] = date_type
                break
        
        # 解析類別條件
        if '診所' in command:
            conditions['category'] = '診所'
        elif '東洋' in command:
            conditions['category'] = '東洋'
        elif '臨時' in command:
            conditions['category'] = '臨時'
        
        # 解析司機條件
        driver_match = re.search(r'司機(\d+)', command)
        if driver_match:
            conditions['driver_id'] = int(driver_match.group(1))
        
        # 解析狀態條件 - 先嘗試精確匹配已知狀態
        known_statuses = ['待派', '準備', '已完成', '取消', '衝突']  # 🔥 新增：添加衝突狀態
        status_found = False
        
        for status in known_statuses:
            if status in command:
                conditions['status'] = status
                status_found = True
                break
        
        # 如果沒找到已知狀態，嘗試通用狀態提取
        if not status_found:
            # 提取"狀態為X"、"狀態=X"或"X狀態"的模式
            status_patterns = [
                r'狀態=(.+?)(?:\s|$)',      # 新增：匹配"狀態=衝突"格式
                r'狀態為(.+?)的',
                r'狀態為(.+?)班次',
                r'狀態(.+?)的班次',
                r'(.+?)狀態的班次'
            ]
            
            for pattern in status_patterns:
                match = re.search(pattern, command)
                if match:
                    extracted_status = match.group(1).strip()
                    # 檢查是否為無效狀態
                    if extracted_status not in known_statuses:
                        conditions['invalid_status'] = extracted_status
                    else:
                        conditions['status'] = extracted_status
                    break
        
        # 解析金額條件
        amount_match = re.search(r'金額([><=]+)(\d+)', command)
        if amount_match:
            operator = amount_match.group(1)
            amount = int(amount_match.group(2))
            conditions['amount_condition'] = {'operator': operator, 'amount': amount}
        
        return conditions
    
    def _build_date_condition(self, date_type: str, table_prefix: str = "ct") -> Tuple[str, Dict]:
        """構建日期條件SQL - 支援不同表前綴"""
        if date_type == 'today':
            return f"{table_prefix}.date = :today", {'today': get_taiwan_date()}
        elif date_type == 'yesterday':
            yesterday = get_taiwan_date() - timedelta(days=1)
            return f"{table_prefix}.date = :yesterday", {'yesterday': yesterday}
        elif date_type == 'tomorrow':
            tomorrow = get_taiwan_date() + timedelta(days=1)
            return f"{table_prefix}.date = :tomorrow", {'tomorrow': tomorrow}
        else:
            # 預設今天
            return f"{table_prefix}.date = :today", {'today': get_taiwan_date()}
    
    def _build_amount_condition(self, amount_condition: Dict) -> Optional[Dict]:
        """構建金額條件SQL"""
        if not amount_condition:
            return None
            
        operator = amount_condition['operator']
        amount = amount_condition['amount']
        
        if operator == '>':
            return {
                'sql': "(ct.meter_fare + ct.extra_fare) > :amount",
                'params': {'amount': amount}
            }
        elif operator == '<':
            return {
                'sql': "(ct.meter_fare + ct.extra_fare) < :amount", 
                'params': {'amount': amount}
            }
        elif operator == '=':
            return {
                'sql': "(ct.meter_fare + ct.extra_fare) = :amount",
                'params': {'amount': amount}
            }
        
        return None
    
    def _format_aggregation_result(self, trips: List, command: str, conditions: Dict) -> Dict:
        """格式化聚合查詢結果 - 返回總金額而不是班次列表"""
        if not trips:
            return {
                "type": "no_results",
                "message": f"沒有找到符合條件的已完成班次",
                "command": command,
                "conditions": conditions
            }
        
        # 計算總金額
        total_amount = sum(float(trip.total_amount or 0) for trip in trips)
        
        # 🔥 關鍵：返回簡潔的總和結果，就像用戶期望的那樣
        result_text = f"🔍 AI智能搜索結果\n\n"
        result_text += f"💬 {command}\n"
        result_text += f"📊 找到 {len(trips)} 個匹配班次，總金額：{total_amount:.0f}元"
        
        return {
            "type": "aggregation_success",
            "message": result_text,
            "count": len(trips),
            "total_amount": total_amount,
            "trips": trips  # 保留原始數據供後續使用
        }
    
    def _format_completed_trips_result(self, trips: List, command: str, conditions: Dict) -> Dict:
        """格式化已完成班次查詢結果"""
        if not trips:
            return {
                "type": "no_results",
                "message": f"沒有找到符合條件的已完成班次",
                "command": command,
                "conditions": conditions
            }
        
        # 生成結果摘要
        total_amount = sum(float(trip.total_amount or 0) for trip in trips)
        
        result_text = f"🔍 AI智能搜索結果\n\n"
        result_text += f"💬 {command}\n"
        result_text += f"📊 找到 {len(trips)} 個匹配班次，總金額：{total_amount:.0f}元\n\n"
        
        # 顯示前10筆結果
        for i, trip in enumerate(trips[:10], 1):
            # 🚨 修復：安全處理可能為None的欄位，避免格式化錯誤
            driver_id = getattr(trip, 'driver_id', None)
            driver_name = getattr(trip, 'driver_name', None)
            
            driver_info = f"司機#{driver_id}" if driver_id else "未指派"
            if driver_name:
                driver_info += f"({driver_name})"
            
            # 安全處理可能為None的欄位
            trip_id = getattr(trip, 'id', '未知')
            category = getattr(trip, 'category', '未分類') or '未分類'
            start_point = getattr(trip, 'start_point', '未知') or '未知'
            end_point = getattr(trip, 'end_point', '未知') or '未知'
            total_amount = getattr(trip, 'total_amount', 0) or 0
                
            result_text += f"📍 {i}. #{trip_id} ({category}) - "
            result_text += f"{start_point} → {end_point} | "
            result_text += f"{driver_info} | "
            result_text += f"💰 {total_amount:.0f}元\n"
        
        if len(trips) > 10:
            result_text += f"\n... 還有 {len(trips) - 10} 筆結果\n"
            result_text += f"💡 輸入「更多」或「下一頁」查看完整結果"
        
        return {
            "type": "success",
            "message": result_text,
            "count": len(trips),
            "total_amount": total_amount,
            "trips": trips
        }
    
    def _format_current_trips_result(self, trips: List, command: str, conditions: Dict) -> Dict:
        """格式化當前班次查詢結果"""
        if not trips:
            return {
                "type": "no_results", 
                "message": f"沒有找到符合條件的當前班次",
                "command": command,
                "conditions": conditions
            }
        
        result_text = f"🔍 AI智能搜索結果\n\n"
        result_text += f"💬 {command}\n"
        result_text += f"📊 找到 {len(trips)} 個匹配班次\n\n"
        
        # 按狀態分組顯示
        status_groups = {}
        for trip in trips:
            status = trip.status or '未知'
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(trip)
        
        for status, status_trips in status_groups.items():
            result_text += f"🎯 {status} ({len(status_trips)}個)：\n"
            
            for trip in status_trips[:5]:  # 每個狀態最多顯示5個
                # 🚨 修復：安全處理可能為None的欄位，避免格式化錯誤
                driver_id = getattr(trip, 'driver_id', None)
                driver_name = getattr(trip, 'driver_name', None)
                
                driver_info = f"司機#{driver_id}" if driver_id else "未指派"
                if driver_name:
                    driver_info += f"({driver_name})"
                
                # 安全處理可能為None的欄位
                trip_id = getattr(trip, 'trip_id', '未知')
                start_point = getattr(trip, 'start_point', '未知') or '未知'
                end_point = getattr(trip, 'end_point', '未知') or '未知'
                    
                result_text += f"  📍 #{trip_id} - {start_point} → {end_point}"
                result_text += f" | {driver_info}\n"
            
            if len(status_trips) > 5:
                result_text += f"  ... 還有 {len(status_trips) - 5} 個{status}班次\n"
            result_text += "\n"
        
        # 如果總數超過顯示數量，提示翻頁功能
        total_displayed = sum(min(5, len(trips)) for trips in status_groups.values())
        if len(trips) > total_displayed:
            result_text += f"💡 輸入「更多」或「下一頁」查看完整結果"
        
        return {
            "type": "success",
            "message": result_text,
            "count": len(trips),
            "status_summary": {status: len(trips) for status, trips in status_groups.items()},
            "trips": trips
        }

# 全域實例
advanced_query_processor = AdvancedQueryProcessor()

def process_ai_complex_query(ai_command: str, user_id: str) -> Dict:
    """處理AI生成的複雜查詢命令的便捷函數"""
    return advanced_query_processor.process_complex_query(ai_command, user_id) 
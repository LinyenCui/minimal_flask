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
from modules.utils.helpers import parse_date_input

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
            self.logger.info(f"🔍 解析查詢條件: {conditions}")
            
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
                self.logger.info(f"🗓️ 添加日期條件: {date_condition}, 參數: {date_params}")
            else:
                self.logger.warning(f"⚠️ 沒有解析到日期條件！命令: {command}")
            
            # 添加類別條件
            if conditions.get('category'):
                where_conditions.append("ct.category = :category")
                params['category'] = conditions['category']
                self.logger.info(f"🏷️ 添加類別條件: {conditions['category']}")
            
            # 添加司機條件
            if conditions.get('driver_id'):
                where_conditions.append("ct.driver_id = :driver_id")
                params['driver_id'] = conditions['driver_id']
                self.logger.info(f"👨‍💼 添加司機條件: {conditions['driver_id']}")
            
            # 添加金額條件
            if conditions.get('amount_condition'):
                amount_condition = self._build_amount_condition(conditions['amount_condition'])
                if amount_condition:
                    where_conditions.append(amount_condition['sql'])
                    params.update(amount_condition['params'])
                    self.logger.info(f"💰 添加金額條件: {amount_condition}")
            
            # 組合完整查詢
            if where_conditions:
                full_query = base_query + " AND " + " AND ".join(where_conditions)
            else:
                full_query = base_query
                
            full_query += " ORDER BY ct.date DESC, ct.id DESC LIMIT 50"
            
            self.logger.info(f"📊 完整SQL查詢: {full_query}")
            self.logger.info(f"📊 查詢參數: {params}")
            
            # 執行查詢
            result = db.session.execute(text(full_query), params)
            trips = result.fetchall()
            
            self.logger.info(f"📊 查詢結果數量: {len(trips)}")
            
            # 🔥 新增：記錄結果的日期分布
            if trips:
                date_counts = {}
                for trip in trips:
                    date_str = str(trip.date)
                    date_counts[date_str] = date_counts.get(date_str, 0) + 1
                
                self.logger.info(f"📊 結果日期分布: {date_counts}")
                
                # 檢查是否有異常的日期分布
                if len(date_counts) > 5:
                    self.logger.warning(f"⚠️ 查詢結果跨越了太多日期，可能日期條件沒有正確應用!")
            
            # 🔥 修復：將SQLAlchemy Row對象轉換為字典，避免保存後失效
            trips_dict_list = []
            for trip in trips:
                trip_dict = {
                    'id': trip.id,
                    'date': trip.date,
                    'start_point': trip.start_point, 
                    'end_point': trip.end_point,
                    'category': trip.category,
                    'driver_id': trip.driver_id,
                    'meter_fare': trip.meter_fare,
                    'extra_fare': trip.extra_fare,
                    'total_amount': trip.total_amount,
                    'driver_name': trip.driver_name
                }
                trips_dict_list.append(trip_dict)
            
            # 保存查詢結果供翻頁使用（保存字典格式）
            context = get_conversation_context(user_id)
            context.save_query_result('completed_trips', command, trips_dict_list, conditions)
            self.logger.info(f"💾 保存查詢結果供翻頁使用: {len(trips_dict_list)} 個結果")
            
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
                    t.trip_type,
                    t.custom_start_point,
                    t.custom_end_point,
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
            
            # 🔥 修復：將SQLAlchemy Row對象轉換為字典，避免保存後失效
            trips_dict_list = []
            for trip in trips:
                trip_dict = {
                    'trip_id': trip.trip_id,
                    'date': trip.date,
                    'time': trip.time,
                    'start_point': trip.start_point,
                    'end_point': trip.end_point,
                    'category': trip.category,
                    'driver_id': trip.driver_id,
                    'status': trip.status,
                    'trip_type': trip.trip_type,
                    'custom_start_point': trip.custom_start_point,
                    'custom_end_point': trip.custom_end_point,
                    'driver_name': trip.driver_name
                }
                trips_dict_list.append(trip_dict)
            
            # 保存查詢結果供翻頁使用（保存字典格式）
            context = get_conversation_context(user_id)
            context.save_query_result('current_trips', command, trips_dict_list, conditions)
            self.logger.info(f"💾 保存查詢結果供翻頁使用: {len(trips_dict_list)} 個結果")
            
            # 格式化結果
            return self._format_current_trips_result(trips_dict_list, command, conditions, user_id)
            
        except Exception as e:
            self.logger.error(f"❌ 當前班次查詢失敗: {e}")
            return {"type": "error", "message": f"查詢失敗: {str(e)}"}
    
    def _process_driver_query(self, command: str, user_id: str) -> Dict:
        """處理司機相關查詢（暫時回退到傳統處理）"""
        # TODO: 實現司機查詢邏輯
        return {"type": "fallback", "command": command}
    
    def _parse_query_conditions(self, command: str) -> Dict:
        """解析查詢命令中的條件"""
        conditions = {}
        
        # 🔥 修復：解析日期條件 - 支援具體日期格式
        date_found = False
        
        # 1. 先檢查相對日期
        relative_date_patterns = {
            '今天': 'today',
            '昨天': 'yesterday',
            '前天': 'day_before_yesterday',  # 🔥 新增前天支援
            '明天': 'tomorrow',
            '後天': 'day_after_tomorrow',    # 🔥 新增後天支援
            '本週': 'this_week',
            '上週': 'last_week'
        }
        
        for date_text, date_type in relative_date_patterns.items():
            if date_text in command:
                conditions['date'] = date_type
                date_found = True
                break
        
        # 2. 🔥 新增：如果沒找到相對日期，嘗試解析具體日期格式
        if not date_found:
            # 各種日期格式的正則表達式
            date_patterns = [
                r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD
                r'\d{1,2}/\d{1,2}',         # MM/DD 或 M/D  
                r'\d{1,2}-\d{1,2}',         # MM-DD 或 M-D
                r'\d{1,2}月\d{1,2}日?',     # MM月DD日
                r'(?<!\d)\d{3,4}(?!\d)'     # MMDD格式（避免被司機ID誤判）
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, command)
                for match in matches:
                    try:
                        # 🔥 關鍵：使用統一的日期解析器
                        parsed_date = parse_date_input(match)
                        if parsed_date:
                            # 將解析出的具體日期轉換為字符串格式
                            conditions['date'] = parsed_date.strftime('%Y-%m-%d')
                            date_found = True
                            self.logger.info(f"🗓️ 解析具體日期: '{match}' → '{conditions['date']}'")
                            break
                    except Exception as e:
                        self.logger.warning(f"日期解析失敗: {match}, 錯誤: {e}")
                        continue
                
                if date_found:
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
        """構建日期條件SQL - 支援不同表前綴和具體日期"""
        if date_type == 'today':
            return f"{table_prefix}.date = :today", {'today': get_taiwan_date()}
        elif date_type == 'yesterday':
            yesterday = get_taiwan_date() - timedelta(days=1)
            return f"{table_prefix}.date = :yesterday", {'yesterday': yesterday}
        elif date_type == 'day_before_yesterday':  # 🔥 新增前天支援
            day_before_yesterday = get_taiwan_date() - timedelta(days=2)
            return f"{table_prefix}.date = :day_before_yesterday", {'day_before_yesterday': day_before_yesterday}
        elif date_type == 'tomorrow':
            tomorrow = get_taiwan_date() + timedelta(days=1)
            return f"{table_prefix}.date = :tomorrow", {'tomorrow': tomorrow}
        elif date_type == 'day_after_tomorrow':  # 🔥 新增後天支援
            day_after_tomorrow = get_taiwan_date() + timedelta(days=2)
            return f"{table_prefix}.date = :day_after_tomorrow", {'day_after_tomorrow': day_after_tomorrow}
        elif date_type and re.match(r'^\d{4}-\d{2}-\d{2}$', date_type):
            # 🔥 新增：處理具體日期格式 (YYYY-MM-DD)
            self.logger.info(f"🗓️ 構建具體日期條件: {date_type}")
            return f"{table_prefix}.date = :specific_date", {'specific_date': date_type}
        else:
            # 🔥 修復：如果無法識別，記錄警告並使用今天作為fallback
            self.logger.warning(f"⚠️ 無法識別的日期類型: {date_type}，使用今天作為fallback")
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
            
            # 🎨 優化顯示：使用小黃車圖示+編號，去掉姓名讓結果更清爽
            driver_info = f"🚕{driver_id}" if driver_id else "未指派"
            
            # 安全處理可能為None的欄位
            trip_id = getattr(trip, 'id', '未知')
            category = getattr(trip, 'category', '未分類') or '未分類'
            start_point = getattr(trip, 'start_point', '未知') or '未知'
            end_point = getattr(trip, 'end_point', '未知') or '未知'
            total_amount = getattr(trip, 'total_amount', 0) or 0
            
            # 🔥 新增：添加日期顯示，與第二頁格式保持一致
            trip_date = getattr(trip, 'date', None)
            date_str = str(trip_date) if trip_date else 'N/A'
                
            # 🔥 修復：統一格式，添加日期顯示
            result_text += f"📍 {i}. #{trip_id} - {start_point} → {end_point}"
            result_text += f" | {driver_info} | {date_str}"
            result_text += f" | 💰 {total_amount:.0f}元\n"
        
        if len(trips) > 10:
            result_text += f"\n... 還有 {len(trips) - 10} 筆結果\n"
            
            # 🔥 修復：使用正確的Quick Reply格式
            pagination_quick_reply_dict = {
                "items": [
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "📄 下一頁",
                            "text": "下一頁"
                        }
                    },
                    {
                        "type": "action", 
                        "action": {
                            "type": "message",
                            "label": "💰 統計金額",
                            "text": f"統計金額 {command.replace('查已完成', '').strip()}"
                        }
                    },
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "🔍 重新查詢",
                            "text": "查已完成"
                        }
                    },
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "❌ 放棄",
                            "text": "放棄"
                        }
                    }
                ]
            }
            
            return {
                "type": "success_with_pagination",
                "message": result_text + f"💡 點擊下方按鈕或輸入命令查看更多",
                "count": len(trips),
                "total_amount": total_amount,
                "trips": trips,
                "quick_reply": pagination_quick_reply_dict
            }
        
        return {
            "type": "success",
            "message": result_text,
            "count": len(trips),
            "total_amount": total_amount,
            "trips": trips
        }
    
    def _format_current_trips_result(self, trips: List, command: str, conditions: Dict, user_id: str) -> Dict:
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
        
        # 🔥 新增：如果結果太多，實施分頁
        if len(trips) > 10:
            # 只顯示前10筆結果
            displayed_trips = trips[:10]
            
            # 按狀態分組顯示
            status_groups = {}
            for trip in displayed_trips:
                status = trip.get('status') or '未知'
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(trip)
            
            for status, status_trips in status_groups.items():
                result_text += f"🎯 {status} ({len(status_trips)}個)：\n"
                
                for trip in status_trips:
                    # 🚨 修復：安全處理可能為None的欄位，避免格式化錯誤
                    driver_id = trip.get('driver_id')
                    driver_name = trip.get('driver_name')
                    
                    # 🎨 優化顯示：使用小黃車圖示+編號，去掉姓名讓結果更清爽
                    driver_info = f"🚕{driver_id}" if driver_id else "未指派"
                    
                    # 安全處理可能為None的欄位
                    trip_id = trip.get('trip_id', '未知')
                    trip_type = trip.get('trip_type', 'fixed')
                    
                    # 🔥 新增：根據trip_type決定使用哪個起點終點
                    if trip_type == 'temp':
                        # 臨時班次使用custom欄位
                        start_point = trip.get('custom_start_point') or trip.get('start_point') or '未知'
                        end_point = trip.get('custom_end_point') or trip.get('end_point') or '未知'
                    else:
                        # 固定班次使用標準欄位
                        start_point = trip.get('start_point') or '未知'
                        end_point = trip.get('end_point') or '未知'
                        
                    result_text += f"  📍 #{trip_id} - {start_point} → {end_point}"
                    result_text += f" | {driver_info}\n"
                result_text += "\n"
            
            result_text += f"\n... 還有 {len(trips) - 10} 筆結果\n"
            
            # 🔥 新增：為分頁結果添加Quick Reply支持
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            # 🔥 修復：直接使用字典格式構建Quick Reply，避免to_dict()轉換問題
            quick_reply_items = [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "📄 下一頁",
                        "text": "下一頁"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message", 
                        "label": "🔍 查看全部",
                        "text": "查看全部結果"
                    }
                }
            ]
            
            return {
                "type": "success_with_pagination",
                "message": result_text,
                "count": len(trips),
                "quick_reply": {"items": quick_reply_items}
            }
        
        # 原來的邏輯：結果不多時的處理
        # 按狀態分組顯示
        status_groups = {}
        for trip in trips:
            status = trip.get('status') or '未知'
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(trip)
        
        for status, status_trips in status_groups.items():
            result_text += f"🎯 {status} ({len(status_trips)}個)：\n"
            
            for trip in status_trips:
                # 🚨 修復：安全處理可能為None的欄位，避免格式化錯誤
                driver_id = trip.get('driver_id')
                driver_name = trip.get('driver_name')
                
                # 🎨 優化顯示：使用小黃車圖示+編號，去掉姓名讓結果更清爽
                driver_info = f"🚕{driver_id}" if driver_id else "未指派"
                
                # 安全處理可能為None的欄位
                trip_id = trip.get('trip_id', '未知')
                trip_type = trip.get('trip_type', 'fixed')
                
                # 🔥 新增：根據trip_type決定使用哪個起點終點
                if trip_type == 'temp':
                    # 臨時班次使用custom欄位
                    start_point = trip.get('custom_start_point') or trip.get('start_point') or '未知'
                    end_point = trip.get('custom_end_point') or trip.get('end_point') or '未知'
                else:
                    # 固定班次使用標準欄位
                    start_point = trip.get('start_point') or '未知'
                    end_point = trip.get('end_point') or '未知'
                    
                result_text += f"  📍 #{trip_id} - {start_point} → {end_point}"
                result_text += f" | {driver_info}\n"
            result_text += "\n"

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
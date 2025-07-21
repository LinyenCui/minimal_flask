"""
AI增強的車資修改服務
支持自然語言查詢和智能匹配已完成班次
🔥 新增：對話上下文管理，支持多輪對話連續性
"""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.utils.helpers import parse_date_input  # 🔥 修復：使用系統統一的日期解析器
from modules.utils.conversation_context import conversation_manager  # 🔥 重新啟用：對話上下文管理
# from modules.utils.enhanced_date_parser import EnhancedDateParser
from sqlalchemy import text
import traceback

logger = logging.getLogger(__name__)

def should_use_ai_query(message_text: str) -> bool:
    """
    🔥 修復：嚴格判斷是否應該使用AI車資查詢
    只有真正的車資相關查詢才使用，避免攔截一般班次查詢
    """
    message_lower = message_text.lower()
    
    # 🔥 修復：必須包含車資關鍵詞的查詢才使用AI服務
    fare_keywords = ['車資', '錶價', '加成', '費用', '金額', '價格', '收費']
    modification_keywords = ['修改', '更改', '調整', '設定', '改成']
    action_verbs = ['查詢', '查看', '查', '顯示', '統計']
    trip_keywords = ['班次', '趟次', '行程']
    location_keywords = ['診所', '東洋', '臨時', '固定']
    time_keywords = ['今天', '昨天', '明天', '本周', '上周', '這週', '7/', '07/', '6/', '06/']
    driver_keywords = ['司機', '駕駛']
    
    # 🔥 關鍵修復：必須包含車資相關詞彙
    has_fare = any(keyword in message_lower for keyword in fare_keywords)
    
    # 🚫 如果沒有車資關鍵詞，直接返回False
    if not has_fare:
        return False
    
    # 檢查其他關鍵詞
    has_action = any(verb in message_lower for verb in action_verbs)
    has_trip = any(keyword in message_lower for keyword in trip_keywords)
    has_location = any(keyword in message_lower for keyword in location_keywords)
    has_time = any(keyword in message_lower for keyword in time_keywords)
    has_driver = any(keyword in message_lower for keyword in driver_keywords)
    has_modification = any(keyword in message_lower for keyword in modification_keywords)
    
    # 檢查是否有班次ID模式
    has_trip_id = bool(re.search(r'班次#?\d+|#\d+', message_text))
    
    # 檢查是否有數字模式（可能是費用或ID）
    has_numbers = bool(re.search(r'\d+', message_text))
    
    # 🔥 修復：只有真正的車資查詢才返回True
    # 1. 明確的車資相關查詢
    if has_fare and (has_action or has_modification):
        return True
    
    # 2. 有班次ID的車資操作
    if has_trip_id and has_fare:
        return True
    
    # 3. 車資修改意圖
    if has_modification and has_numbers and has_fare:
        return True
    
    # 4. 車資相關的地點+時間查詢
    if has_location and has_time and has_action and has_fare:
        return True
    
    # 5. 司機車資查詢
    if has_driver and (has_action or has_time) and has_numbers and has_fare:
        return True
    
    return False

class CompletedTripMatcher:
    """已完成班次智能匹配器"""
    
    def __init__(self):
        self.time_patterns = {
            r'早上|上午': (6, 12),
            r'中午|午間': (11, 14), 
            r'下午|午後': (12, 18),
            r'晚上|夜間': (18, 23),
            r'(\d{1,2})[點時:]': self._extract_hour,
            r'(\d{1,2}):(\d{1,2})': self._extract_time
        }
        
        self.sequence_patterns = {
            r'第一|第1|首|第一趟': 1,
            r'第二|第2|第二趟': 2,
            r'第三|第3|第三趟': 3,
            r'最後|最後一|最後一趟': -1,
            r'倒數第二|倒二': -2
        }
        
        self.location_keywords = [
            '醫院', '火車站', '住家', '市區'  # 🔥 移除'診所'和'東洋' - 避免類別與地點衝突
        ]
    
    def _extract_hour(self, match):
        """提取小時"""
        hour = int(match.group(1))
        return (hour, hour + 1)
    
    def _extract_time(self, match):
        """提取具體時間"""
        hour = int(match.group(1))
        minute = int(match.group(2))
        return (hour + minute/60, hour + minute/60 + 0.1)
    
    def _is_likely_driver_id(self, number: str, query: str) -> bool:
        """
        🔥 智能判斷數字是否更可能是司機ID而非日期
        考慮位置、上下文和其他線索
        """
        # 基本司機上下文檢查
        driver_context_patterns = [
            rf'司機\s*{re.escape(number)}',     # 司機123
            rf'{re.escape(number)}\s*號司機',   # 123號司機
            rf'司機.?{re.escape(number)}',      # 司機 123
        ]
        
        # 檢查是否在司機上下文中
        is_in_driver_context = any(re.search(pattern, query) for pattern in driver_context_patterns)
        
        if not is_in_driver_context:
            # 不在司機上下文中，不太可能是司機ID
            return False
        
        # 🔥 智能判斷：如果多個數字都在司機上下文中，選擇最合理的
        
        # 查找所有可能的司機ID候選
        all_numbers = re.findall(r'(?<!\d)\d{3,4}(?!\d)', query)
        driver_candidates = []
        
        for num in all_numbers:
            # 檢查每個數字與「司機」關鍵字的距離和位置
            for pattern in driver_context_patterns:
                match = re.search(pattern, query)
                if match:
                    # 計算與「司機」關鍵字的距離
                    driver_pos = query.find('司機')
                    num_pos = query.find(num)
                    distance = abs(driver_pos - num_pos)
                    
                    # 檢查是否是直接緊跟的模式（更可能是司機ID）
                    is_direct = bool(re.search(rf'司機\s*{re.escape(num)}', query))
                    
                    driver_candidates.append({
                        'number': num,
                        'distance': distance,
                        'is_direct': is_direct,
                        'position': num_pos
                    })
                    break
        
        if len(driver_candidates) <= 1:
            # 只有一個候選，按原邏輯處理
            return is_in_driver_context
        
        # 🔥 多個候選時的智能選擇
        # 優先級：1. 直接跟在「司機」後面的  2. 距離最近的  3. 位置靠後的（通常司機ID在後面）
        
        # 找到最佳的司機ID候選
        best_candidate = None
        for candidate in driver_candidates:
            if candidate['number'] == number:
                # 當前數字是候選之一
                
                # 檢查是否有更好的候選
                for other in driver_candidates:
                    if other['number'] != number:
                        # 如果其他候選更直接（緊跟司機關鍵字）
                        if other['is_direct'] and not candidate['is_direct']:
                            return False  # 當前數字不是最佳司機ID
                        
                        # 如果當前數字更像日期格式（MMDD）且其他候選距離更近
                        if (re.match(r'^[01]\d[0-3]\d$', number) and  # 當前是MMDD格式
                            other['distance'] < candidate['distance']):  # 其他距離更近
                            return False  # 當前數字更可能是日期
                
                return True  # 當前數字是最佳司機ID候選
        
        return False  # 當前數字不在司機候選中
    
    def parse_natural_query(self, query: str) -> Dict:
        """解析自然語言查詢"""
        criteria = {
            'date': None,
            'time_range': None,
            'locations': [],
            'sequence': None,
            'driver_id': None,
            'category': None,
            'trip_id': None,  # 🔥 新增：班次ID解析
            'raw_query': query,  # 保存原始查詢
            'confidence': 'high'  # 解析信心度
        }
        
        query_lower = query.lower()
        
        # 🔥 新增：解析班次ID - 最優先，因為如果有班次ID就不需要其他條件
        trip_id_patterns = [
            r'班次#?(\d+)',
            r'#(\d+)',
            r'修改班次#?(\d+)',
            r'ID\s*#?(\d+)',
            r'編號#?(\d+)'
        ]
        
        for pattern in trip_id_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    criteria['trip_id'] = int(match.group(1))
                    criteria['confidence'] = 'high'  # 有明確班次ID，信心度高
                    return criteria  # 🔥 有班次ID直接返回，不需要其他解析
                except (ValueError, IndexError):
                    continue
        
        # 🔥 使用統一的增強日期解析器
        date_extracted = False
        
        # 先嘗試提取所有可能的日期字符串
        possible_dates = []
        
        # 相對日期
        for relative_word in ['今天', '今日', '昨天', '昨日', '前天', '明天', '明日', '後天']:
            if relative_word in query:
                possible_dates.append(relative_word)
        
        # 星期幾（🔥 修復：精確匹配星期詞，避免誤判）
        for weekday in ['一', '二', '三', '四', '五', '六', '日']:
            # 🔥 修復：只匹配真正的星期表達，避免"查一下"等詞被誤判
            weekday_patterns = [
                f'星期{weekday}',   # 星期一
                f'週{weekday}',     # 週一  
                f'禮拜{weekday}',   # 禮拜一
            ]
            # 🔥 特殊處理：對於單字星期詞，需要更嚴格的上下文檢查
            if weekday in ['一', '二', '三', '四', '五', '六', '日']:
                # 只有在明確的時間上下文中才認為是星期詞
                strict_patterns = [
                    f'(^|\\s){weekday}(\\s|$)',           # 獨立的一個字
                    f'下{weekday}',                       # 下一/下二等
                    f'這{weekday}',                       # 這一/這二等  
                    f'上{weekday}',                       # 上一/上二等
                ]
                # 但排除明顯不是星期的用法
                false_positive_patterns = [
                    f'查{weekday}',                       # 查一、查二等
                    f'第{weekday}',                       # 第一、第二等
                    f'{weekday}下',                       # 一下、二下等
                    f'{weekday}起',                       # 一起、二起等
                    f'{weekday}般',                       # 一般、二般等
                    f'{weekday}些',                       # 一些、二些等
                ]
                
                # 檢查是否有假陽性模式
                has_false_positive = any(re.search(pattern, query) for pattern in false_positive_patterns)
                if has_false_positive:
                    continue  # 跳過這個星期詞
                
                # 檢查是否有嚴格的星期模式
                has_strict_match = any(re.search(pattern, query) for pattern in strict_patterns)
                if not has_strict_match:
                    continue  # 沒有明確星期上下文，跳過
            
            # 檢查基本星期模式
            if any(pattern in query for pattern in weekday_patterns):
                possible_dates.append(weekday)
        
        # 各種數字日期格式
        date_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD, YYYY/MM/DD
            r'\d{1,2}[-/]\d{1,2}',           # MM-DD, MM/DD
            r'\d{1,2}月\d{1,2}日?',          # MM月DD日
            r'(?<!\d)\d{3,4}(?!\d)'          # 🔥 修復：MMDD格式，使用前後非數字字符
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                # 🔥 修復：對於3-4位數字，檢查是否在司機上下文中
                if re.match(r'^\d{3,4}$', match):
                    # 🔥 新增：智能司機ID檢測 - 避免日期被錯誤識別
                    is_driver_id = self._is_likely_driver_id(match, query)
                    if is_driver_id:
                        continue
                
                possible_dates.append(match)
        
        # 嘗試解析找到的日期
        for date_str in possible_dates:
            try:
                parsed_date = parse_date_input(date_str)  # 🔥 修復：使用統一日期解析器
                if parsed_date:
                    criteria['date'] = parsed_date
                    # parse_date_input 總是返回高信心度，因為它經過充分測試
                    date_extracted = True
                    break
            except Exception:
                continue
        
        # 解析時間範圍
        for pattern, time_range in self.time_patterns.items():
            match = re.search(pattern, query)
            if match:
                if callable(time_range):
                    criteria['time_range'] = time_range(match)
                else:
                    criteria['time_range'] = time_range
                break
        
        # 解析順序
        for pattern, sequence in self.sequence_patterns.items():
            if re.search(pattern, query):
                criteria['sequence'] = sequence
                break
        
        # 解析地點
        for keyword in self.location_keywords:
            if keyword in query:
                criteria['locations'].append(keyword)
        
        # 解析司機 - 增強版
        driver_patterns = [
            r'司機(\d+)',
            r'(\d+)號司機',
            r'司機.?(\d+)',
            r'driver\s*(\d+)',
            r'(\d+)\s*司機',
        ]
        
        for pattern in driver_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    criteria['driver_id'] = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
        
        # 解析類別
        if '診所' in query:
            criteria['category'] = '診所'
        elif '東洋' in query:
            criteria['category'] = '東洋'
        elif '臨時' in query:
            criteria['category'] = '臨時'
        
        # 🔥 修改：信心度計算 - 包含班次ID
        parsed_criteria_count = sum([
            1 if criteria['date'] else 0,
            1 if criteria['driver_id'] else 0,
            1 if criteria['category'] else 0,
            1 if criteria['locations'] else 0,
            1 if criteria['sequence'] else 0,
            1 if criteria['time_range'] else 0,
            1 if criteria['trip_id'] else 0  # 🔥 新增班次ID計數
        ])
        
        if parsed_criteria_count == 0:
            criteria['confidence'] = 'very_low'
        elif parsed_criteria_count == 1:
            criteria['confidence'] = 'low'
        elif parsed_criteria_count >= 2:
            criteria['confidence'] = 'high'
        
        return criteria
    
    def search_completed_trips(self, criteria: Dict) -> List[Dict]:
        """根據條件搜索已完成班次"""
        try:
            # 🔥 新增：如果有班次ID，直接查詢
            if criteria.get('trip_id'):
                query = """
                SELECT 
                    id, date, start_point, end_point,
                    meter_fare, extra_fare, driver_id, 
                    category, created_at
                FROM completed_trips
                WHERE id = :trip_id
                """
                
                result = db.session.execute(text(query), {'trip_id': criteria['trip_id']}).fetchall()
                
                trips = []
                for row in result:
                    trips.append({
                        'id': row[0],
                        'date': row[1],
                        'start_point': row[2],
                        'end_point': row[3],
                        'meter_fare': row[4] or 0,
                        'extra_fare': row[5] or 0,
                        'driver_id': row[6],
                        'category': row[7],
                        'created_at': row[8]
                    })
                
                return trips
            
            # 構建基礎查詢
            query_base = """
            SELECT 
                id, date, start_point, end_point,
                meter_fare, extra_fare, driver_id, 
                category, created_at
            FROM completed_trips
            WHERE 1=1
            """
            params = {}
            
            # 添加日期條件
            if criteria['date']:
                query_base += " AND date = :date"
                params['date'] = criteria['date']
            else:
                # 默認搜索最近3天
                query_base += " AND date >= :start_date"
                params['start_date'] = get_taiwan_date() - timedelta(days=2)
            
            # 添加類別條件
            if criteria['category']:
                query_base += " AND category = :category"
                params['category'] = criteria['category']
            
            # 添加司機條件
            if criteria['driver_id']:
                query_base += " AND driver_id = :driver_id"
                params['driver_id'] = criteria['driver_id']
            
            # 添加地點條件
            if criteria['locations']:
                location_conditions = []
                for i, location in enumerate(criteria['locations']):
                    location_conditions.append(f"(start_point LIKE :loc{i} OR end_point LIKE :loc{i})")
                    params[f'loc{i}'] = f'%{location}%'
                
                if location_conditions:
                    query_base += f" AND ({' OR '.join(location_conditions)})"
            
            query_base += " ORDER BY date DESC, id DESC"
            
            result = db.session.execute(text(query_base), params).fetchall()
            
            # 轉換為字典列表
            trips = []
            for row in result:
                trips.append({
                    'id': row[0],
                    'date': row[1],
                    'start_point': row[2],
                    'end_point': row[3],
                    'meter_fare': row[4] or 0,
                    'extra_fare': row[5] or 0,
                    'driver_id': row[6],
                    'category': row[7],
                    'created_at': row[8]
                })
            
            # 應用時間和順序篩選
            trips = self._filter_by_time_and_sequence(trips, criteria)
            
            return trips
            
        except Exception as e:
            logger.error(f"搜索已完成班次時出錯: {e}")
            return []
    
    def _filter_by_time_and_sequence(self, trips: List[Dict], criteria: Dict) -> List[Dict]:
        """根據時間和順序篩選班次"""
        filtered_trips = trips
        
        # 時間篩選（需要額外的時間信息，這裡簡化處理）
        if criteria['time_range']:
            # 簡化：根據created_at時間篩選
            start_hour, end_hour = criteria['time_range']
            filtered_trips = [
                trip for trip in filtered_trips
                if trip['created_at'] and start_hour <= trip['created_at'].hour < end_hour
            ]
        
        # 順序篩選
        if criteria['sequence'] and filtered_trips:
            sequence = criteria['sequence']
            if sequence > 0:
                # 正序：第1、2、3...
                if sequence <= len(filtered_trips):
                    filtered_trips = [filtered_trips[sequence - 1]]
                else:
                    filtered_trips = []
            else:
                # 倒序：最後一個、倒數第二個...
                index = sequence
                if abs(index) <= len(filtered_trips):
                    filtered_trips = [filtered_trips[index]]
                else:
                    filtered_trips = []
        
        return filtered_trips

def handle_smart_fare_query(message_text: str, user_id: str, use_flex=True, parsed_command=None, skip_parsing=False):
    """
    🔥 智能車資查詢和修改服務 - 增強版
    支持自然語言理解、多輪對話、智能修改確認
    
    Args:
        message_text: 用戶輸入的原始查詢
        user_id: 用戶ID
        use_flex: 是否使用Flex消息
        parsed_command: 智能助手已解析的標準命令（可選）
        skip_parsing: 是否跳過重新解析，直接執行parsed_command
    """
    try:
        logger.info(f"🔍 AI車資查詢開始: '{message_text}', user_id: {user_id}")
        if parsed_command:
            logger.info(f"🎯 接收到已解析命令: '{parsed_command}'")
        if skip_parsing:
            logger.info(f"⚡ 跳過解析，直接執行命令: '{parsed_command}'")
        
        # 🔥 如果跳過解析，直接執行已解析的標準命令，但使用AI車資服務格式
        if skip_parsing and parsed_command:
            try:
                logger.info(f"🎯 跳過解析，直接執行查詢並返回Flex Message: {parsed_command}")
                
                # 🔥 關鍵修復：解析已確認的命令，提取查詢條件
                matcher = CompletedTripMatcher()
                criteria = matcher.parse_natural_query(parsed_command)
                
                # 🔥 直接搜索，不再進行信心度評估
                trips = matcher.search_completed_trips(criteria)
                
                # 🔥 格式化AI理解的條件（用於顯示）
                understood_criteria = format_understood_criteria(criteria)
                
                # 🔥 使用AI車資服務的Flex Message格式返回結果
                if not trips:
                    if use_flex:
                        from modules.flex_designs.ai_fare_query_flex import create_ai_search_result_flex
                        search_info = {
                            'query': message_text,
                            'criteria_text': understood_criteria.replace('\n', ', ').replace('  ', '')
                        }
                        return create_ai_search_result_flex(search_info, [], 'high')
                    else:
                        return {
                            'type': 'text',
                            'message': f"❌ 找不到符合條件的班次記錄\n\n💡 建議使用「查已完成」查看完整列表"
                        }
                else:
                    # 🔥 返回可點擊的Flex Message
                    if use_flex:
                        from modules.flex_designs.ai_fare_query_flex import create_ai_search_result_flex
                        search_info = {
                            'query': message_text,
                            'criteria_text': understood_criteria.replace('\n', ', ').replace('  ', '')
                        }
                        return create_ai_search_result_flex(search_info, trips, 'high')
                    else:
                        trips_summary = format_multiple_trips_summary(trips)
                        return {
                            'type': 'text', 
                            'message': f"🔍 查詢結果：\n\n{trips_summary}"
                        }
                        
            except Exception as e:
                logger.error(f"跳過解析執行失敗: {e}")
                return {
                    'type': 'text',
                    'message': f"❌ 執行查詢時出現錯誤: {str(e)}"
                }
        
        # 🔥 首先檢查用戶是否在回答修改原因
        pending_modification = conversation_manager.get_pending_modification(user_id)
        if pending_modification:
            logger.info(f"🔍 檢測到待執行修改，檢查用戶是否在回答原因: {message_text}")
            
            # 檢查用戶輸入是否是修改原因的回答
            reason_indicators = ['原因', '因為', '由於', '要求', '調整', '客戶', '等候', '等待', '夜班', '加班', '延誤', '來不及', '臨時', '不適', '有事', '路況', '塞車']
            
            # 檢查是否包含原因關鍵詞，或者是簡單的原因描述
            is_reason_response = False
            if any(keyword in message_text for keyword in reason_indicators):
                is_reason_response = True
            elif len(message_text.strip()) > 3 and not any(num in message_text for num in ['0','1','2','3','4','5','6','7','8','9']):
                # 如果沒有數字且長度大於3，可能是原因描述
                is_reason_response = True
            
            if is_reason_response:
                logger.info(f"🎯 用戶正在回答修改原因: {message_text}")
                
                # 提取原因
                extracted_reason = message_text.strip()
                
                # 清理原因文本（移除"原因："等前綴）
                cleaned_reason = re.sub(r'^原因[：:]\s*', '', extracted_reason)
                cleaned_reason = re.sub(r'^因為\s*', '', cleaned_reason)
                cleaned_reason = re.sub(r'^由於\s*', '', cleaned_reason)
                cleaned_reason = cleaned_reason.strip()
                
                if len(cleaned_reason) > 0:
                    # 更新pending_modification中的原因
                    pending_modification['reason'] = cleaned_reason
                    
                    # 直接執行修改
                    trip_id = pending_modification['trip_id']
                    new_meter = pending_modification['meter_fare'] 
                    new_extra = pending_modification['extra_fare']
                    
                    logger.info(f"🔥 執行AI智能修改: trip_id={trip_id}, meter={new_meter}, extra={new_extra}, reason='{cleaned_reason}'")
                    
                    # 執行修改
                    from modules.handlers.trip_handler import handle_record_fare
                    modify_command = f"記錄車資 {trip_id} {new_meter} {new_extra} {cleaned_reason}"
                    result = handle_record_fare(modify_command, user_id=user_id)
                    
                    # 清除待執行狀態
                    conversation_manager.clear_pending_modification(user_id)
                    
                    if "需要說明原因" in result or "修改原因" in result:
                        return f"❌ 修改被系統拒絕：{result}"
                    else:
                        return f"""✅ AI智能修改執行成功！

📋 班次：#{trip_id}
💰 新費用：{new_meter}+{new_extra} = {new_meter + new_extra}元
📝 修改原因：{cleaned_reason}

{result}"""
                else:
                    return "⚠️ 修改原因不能為空，請重新輸入修改原因"
            else:
                logger.info(f"💭 用戶輸入不像是原因回答，繼續正常AI處理: {message_text}")
        
        # 如果沒有待執行修改，或用戶輸入不是原因回答，繼續正常AI查詢流程
        
        # 🔥 新增：首先嘗試使用對話上下文解析不完整查詢
        # context_resolution = conversation_manager.try_resolve_incomplete_query(user_id, message_text)
        
        # if context_resolution:
        #     if context_resolution.get('resolved'):
        #         # 成功通過上下文解析到具體班次
        #         trip = context_resolution['trip']
        #         context_info = context_resolution['context_info']
                
        #         # 檢查是否有修改意圖
        #         modification_intent = parse_fare_modification_intent(message_text)
                
        #         if modification_intent:
        #             # 🔥 核心修复：检查是否有明确原因
        #             reason = modification_intent.get('reason', '')
                    
        #             # 🔥 判断原因是否是AI推断的默认原因（需要追问）
        #             default_reasons = ['透過AI智能修改', '錶價260加成', '費用調整要求']
        #             is_default_reason = not reason or reason in default_reasons or len(reason.strip()) < 3
                    
        #             if is_default_reason:
        #                 # 需要追问原因，不直接执行修改
        #                 meter_change = modification_intent.get('meter_fare', trip['meter_fare'])
        #                 extra_change = modification_intent.get('extra_fare', trip['extra_fare'])
                        
        #                 # 保存待执行的修改到上下文
        #                 conversation_manager.set_pending_modification(user_id, {
        #                     'trip_id': trip['id'],
        #                     'meter_fare': meter_change,
        #                     'extra_fare': extra_change,
        #                     'trip': trip
        #                 })
                        
        #                 return f"""✅ 已理解要修改的内容：

        # 📋 班次：#{trip['id']} ({trip['category']})
        # 📍 路線：{trip['start_point']} → {trip['end_point']}
        # 💰 費用變更：{trip['meter_fare']}+{trip['extra_fare']} → {meter_change}+{extra_change}
        # 📊 總計變化：{(meter_change + extra_change) - (trip['meter_fare'] + trip['extra_fare']):+d} 元

        # ❓ 請說明修改原因：
        # （例如：客戶要求調整、等候時間過長、夜班費用等）"""
        #             else:
        #                 # 有明确原因，直接执行修改
        #                 result = execute_fare_modification(trip, modification_intent, user_id)
                        
        #                 # 🔥 修復：正確處理字典格式的返回結果
        #                 if isinstance(result, dict) and 'flex_message' in result:
        #                     # 返回Flex格式結果
        #                     return result
        #                 else:
        #                     # 降級為文字結果
        #                     return f"""🎯 智能上下文解析

        # 💬「{message_text}」
        # 🧠 {context_info}

        # {result}"""
        #         else:
        #             # 只是查詢，詢問如何修改
        #             meter_fare = trip['meter_fare'] or 0
        #             extra_fare = trip['extra_fare'] or 0
                    
        #             if extra_fare >= 0:
        #                 fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"
        #             else:
        #                 fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"
                    
        #             return f"""🎯 智能解析結果

        # 💬「{message_text}」
        # 🧠 {context_info}

        # 📋 班次 #{trip['id']} ({trip['category']})
        # 📍 {trip['start_point']} → {trip['end_point']}
        # 🚕 {trip['driver_id']} | 💰 {fare_display}

        # 請告訴我要如何調整費用？
        # 例如：「改成錶價400加成80，客戶要求調整」"""
            
        #         elif context_resolution.get('needs_clarification'):
        #             # 需要用戶澄清
        #             message = context_resolution['message']
        #             available_trips = context_resolution['available_trips']
        #             trips_summary = format_multiple_trips_summary(available_trips)
                
        #             if use_flex:
        #                 from modules.flex_designs.ai_fare_query_flex import create_ai_clarification_flex
        #                 search_info = {'query': message_text}
        #                 return create_ai_clarification_flex(search_info, message, available_trips)
        #             else:
        #                 return f"""🤔 需要您澄清

        # 💬「{message_text}」
        # ⚠️ {message}

        # {trips_summary}

        # 💡 操作提示：
        # • 修改第1個費用為400加成80
        # • 修改班次#{available_trips[0]['id']}"""
        
        #         # 🔥 检查是否是对之前追问的回复（用户提供原因）
        #         pending_modification = conversation_manager.get_pending_modification(user_id)
        #         if pending_modification:
        #             # 🔥 修復：檢查用戶是否想要開始新的查詢而不是回覆原因
        #             # 如果輸入包含新的車資查詢關鍵詞，清除舊的pending並重新處理
        #             new_query_indicators = [
        #                 '查詢', '查', '找', '搜尋', '顯示', '看',  # 查詢動詞
        #                 '修改班次#', '班次#', '#',  # 新的班次ID
        #                 '今天', '明天', '昨天', '月', '日',  # 時間詞
        #                 '台中', '彰化', '診所', '醫院'  # 地點詞
        #             ]
                
        #             is_new_query = any(indicator in message_text for indicator in new_query_indicators)
                
        #             # 🔥 新增：檢查是否包含新的修改意圖（不同的班次或費用）
        #             current_modification = parse_fare_modification_intent(message_text)
        #             is_new_modification = False
                
        #             if current_modification:
        #                 # 如果有新的費用意圖，檢查是否與待執行的不同
        #                 pending_trip_id = pending_modification.get('trip_id')
        #                 new_meter = current_modification.get('meter_fare')
        #                 new_extra = current_modification.get('extra_fare')
                
        #                 # 檢查班次ID或費用是否不同
        #                 trip_id_in_text = re.search(r'班次#?(\d+)|#(\d+)', message_text)
        #                 if trip_id_in_text:
        #                     mentioned_trip_id = int(trip_id_in_text.group(1) or trip_id_in_text.group(2))
        #                     if mentioned_trip_id != pending_trip_id:
        #                         is_new_modification = True
                
        #                 # 檢查費用是否不同
        #                 if new_meter and new_meter != pending_modification.get('meter_fare'):
        #                     is_new_modification = True
        #                 if new_extra and new_extra != pending_modification.get('extra_fare'):
        #                     is_new_modification = True
            
        #             if is_new_query or is_new_modification:
        #                 # 用戶想要開始新的查詢或修改，清除舊的pending
        #                 logger.info(f"用戶開始新查詢，清除待執行修改: {message_text}")
        #                 conversation_manager.clear_pending_modification(user_id)
        #                 # 重新處理這個消息（遞歸調用）
        #                 return handle_smart_fare_query(message_text, user_id)
            
        #             # 確實是在回覆原因
        #             reason = message_text.strip()
            
        #             # 🔥 增強原因驗證：更寬鬆的判斷邏輯
        #             if len(reason) > 1 and not reason.isdigit():
        #                 # 🔥 過濾明顯不是原因的回覆
        #                 not_reason_patterns = [
        #                     r'^錶價\d+',         # 錶價數字
        #                     r'^加成[+-]?\d+',    # 加成數字
        #                     r'^\d+$',            # 純數字
        #                     r'^[+-]?\d+$',       # 帶符號的純數字
        #                 ]
                
        #                 is_not_reason = any(re.match(pattern, reason) for pattern in not_reason_patterns)
                
        #                 if not is_not_reason:
        #                     # 执行之前暂停的修改
        #                     trip = pending_modification['trip']
        #                     modification_intent = {
        #                         'meter_fare': pending_modification['meter_fare'],
        #                         'extra_fare': pending_modification['extra_fare'],
        #                         'reason': reason
        #                     }
                    
        #                     # 清除待执行修改
        #                     conversation_manager.clear_pending_modification(user_id)
                    
        #                     result = execute_fare_modification(trip, modification_intent, user_id)
                    
        #                     # 🔥 修復：正確處理字典格式的返回結果
        #                     if isinstance(result, dict) and 'flex_message' in result:
        #                         # 返回Flex格式結果
        #                         return result
        #                     else:
        #                         # 降級為文字結果
        #                         return f"""✅ 修改原因已记录

        # 📝 修改原因：{reason}

        # {result}"""
            
        #             # 原因無效，繼續要求
        #             return f"""❓ 请提供更具体的修改原因：

        # 当前输入：「{reason}」
        # ❌ 原因过于简短或可能不是原因描述

        # 💡 请说明为什么要修改费用，例如：
        # • 客戶要求調整價格
        # • 等候時間過長  
        # • 夜班服務費
        # • 路線變更

        # 💭 如果要查詢其他班次，請直接說「查詢...」開始新查詢。"""
        
        # 🔥 如果上下文無法解析，繼續原有的智能解析流程
        modification_intent = parse_fare_modification_intent(message_text)
        
        matcher = CompletedTripMatcher()
        criteria = matcher.parse_natural_query(message_text)
        
        logger.info(f"解析條件: {criteria}")
        logger.info(f"修改意圖: {modification_intent}")
        
        # 🔥 新增：信心度檢查和條件顯示
        confidence = criteria.get('confidence', 'high')
        
        # 格式化AI理解的條件
        understood_criteria = format_understood_criteria(criteria)
        
        # 🔥 新增：對低信心度查詢的智能處理
        if confidence == 'very_low':
            logger.info(f"⚠️ 查詢信心度極低，啟動澄清對話: {message_text}")
            
            # 啟動澄清對話
            clarification_message = f"""🤔 抱歉，我無法理解您的查詢條件

💬 「{message_text}」

💡 請選擇下一步操作："""
            
            conversation_manager.start_conversation(
                user_id=user_id,
                conversation_type='query_clarification',
                current_step='waiting_clarification',
                context_data={'original_query': message_text},
                prompt_message=clarification_message,
                duration_minutes=2  # 🔥 縮短為2分鐘
            )
            
            # 🔥 新增：提供Quick Reply選項讓用戶明確選擇
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            
            quick_reply_items = [
                QuickReplyItem(
                    action=MessageAction(
                        label="🔍 重新描述查詢",
                        text="我想查詢具體的班次資料"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="📋 查看範例格式", 
                        text="查詢範例"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="📊 查看所有班次",
                        text="查已完成"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="❌ 取消查詢",
                        text="取消"
                    )
                )
            ]
            
            quick_reply = QuickReply(items=quick_reply_items)
            
            return {
                "type": "text_with_quick_reply",
                "text": f"""{clarification_message}

🔍 **常用查詢格式：**
• 日期：「7/15」、「今天」、「昨天」
• 司機：「司機533」、「533號司機」  
• 類別：「診所」、「東洋」、「臨時」
• 修改：「修改班次#2014車資280加成-50」

⏰ 請在 2 分鐘內回覆，否則將自動取消""",
                "quick_reply": quick_reply
            }
        
        elif confidence == 'low':
            logger.info(f"⚠️ 查詢信心度較低，請求確認: {message_text}")
            
            # 請求確認理解
            confirmation_message = f"""⚠️ 請確認我的理解是否正確

💬 「{message_text}」

{understood_criteria}

💡 請確認理解是否正確，或提供更準確的描述
⏰ 此對話將在 3 分鐘後自動過期"""
            
            # 🔥 修復：使用統一的確認對話框格式
            conversation_manager.start_conversation(
                user_id=user_id,
                conversation_type='query_confirmation',
                current_step='waiting_confirmation',
                context_data={
                    'original_query': message_text,
                    'parsed_criteria': criteria,
                    'modification_intent': modification_intent,
                    'parsed_command': parsed_command  # 保存已解析的標準命令
                },
                prompt_message=confirmation_message,
                duration_minutes=3
            )
            
            # 🔥 統一格式：使用標準的Quick Reply按鈕
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="✅ 確認正確", text="確認")),
                QuickReplyItem(action=MessageAction(label="❌ 理解錯誤", text="不對")),
                QuickReplyItem(action=MessageAction(label="🔍 重新查詢", text="重新查詢")),
                QuickReplyItem(action=MessageAction(label="🚫 取消查詢", text="取消"))
            ])
            
            return {
                "type": "text_with_quick_reply",
                "message": confirmation_message,
                "quick_reply": quick_reply
            }
        
        # 信心度足夠，直接執行查詢
        # 搜索匹配的班次
        matcher = CompletedTripMatcher()
        criteria = matcher.parse_natural_query(message_text)
        logger.info(f"解析條件: {criteria}")
        logger.info(f"修改意圖: {modification_intent}")
        logger.info(f"信心度: {confidence}")
        logger.info(f"AI理解的搜索條件: {understood_criteria}")
        
        # 🔥 新增：總是顯示搜索條件，提高透明度
        search_header = f"""🔍 AI智能搜索

💬 {message_text}
{understood_criteria}

"""
        
        if not matcher.search_completed_trips(criteria):
            if use_flex:
                from modules.flex_designs.ai_fare_query_flex import create_ai_search_result_flex
                search_info = {
                    'query': message_text,
                    'criteria_text': understood_criteria.replace('\n', ', ').replace('  ', '')
                }
                return create_ai_search_result_flex(search_info, [], confidence)
            else:
                return f"""{search_header}❌ 找不到符合條件的班次記錄

💡 建議：
• 嘗試更寬泛的條件（如「今天的診所班次」）
• 使用「查已完成」查看完整列表
• 確認日期和關鍵詞是否正確
• 檢查司機ID是否存在"""
        
        elif len(matcher.search_completed_trips(criteria)) == 1:
            trip = matcher.search_completed_trips(criteria)[0]
            
            # 🔥 修復：正確格式化費用顯示
            meter_fare = trip['meter_fare'] or 0
            extra_fare = trip['extra_fare'] or 0
            
            if extra_fare >= 0:
                fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"
            else:
                fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"  # 負數自帶負號
            
            # 🔥 如果有修改意圖，检查是否需要追问原因
            if modification_intent:
                reason = modification_intent.get('reason', '')
                default_reasons = ['透過AI智能修改', '錶價260加成', '費用調整要求']
                is_default_reason = not reason or reason in default_reasons or len(reason.strip()) < 3
                
                if is_default_reason:
                    # 🔥 使用新的統一對話系統替代舊的pending_modification
                    logger.info(f"🎯 AI需要詢問修改原因，啟動統一對話系統")
                    
                    # 🔥 修復：先獲取修改後的費用值
                    meter_change = modification_intent.get('meter_fare', meter_fare)
                    extra_change = modification_intent.get('extra_fare', extra_fare)
                    
                    # 準備對話上下文數據
                    context_data = {
                        'trip_id': trip['id'],
                        'meter_fare': meter_change,
                        'extra_fare': extra_change,
                        'trip': trip,
                        'original_meter': meter_fare,
                        'original_extra': extra_fare
                    }
                    
                    # 構建詳細的提示消息
                    prompt_message = f"""✅ 已理解要修改的内容：

📋 班次：#{trip['id']} ({trip['category']})
📍 路線：{trip['start_point']} → {trip['end_point']}
💰 費用變更：{meter_fare}+{extra_fare} → {meter_change}+{extra_change}
📊 總計變化：{(meter_change + extra_change) - (meter_fare + extra_fare):+d} 元

❓ 請說明修改原因：
例如：客戶要求調整、等候時間過長、夜班費用等"""
                    
                    # 啟動對話
                    conversation_manager.start_conversation(
                        user_id=user_id,
                        conversation_type='fare_modification',
                        current_step='waiting_reason',
                        context_data=context_data,
                        prompt_message=prompt_message,
                        duration_minutes=5
                    )
                    
                    # 🔥 新增：修改原因Quick Reply選項
                    from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                    
                    reason_quick_reply_items = [
                        QuickReplyItem(
                            action=MessageAction(
                                label="🚗 前一班延誤",
                                text="前一班延誤，導致無法搭載"
                            )
                        ),
                        QuickReplyItem(
                            action=MessageAction(
                                label="⏰ 等候時間過長",
                                text="等候時間過長"
                            )
                        ),
                        QuickReplyItem(
                            action=MessageAction(
                                label="👨‍💼 客戶要求調整",
                                text="客戶要求調整"
                            )
                        ),
                        QuickReplyItem(
                            action=MessageAction(
                                label="🌙 夜班費用",
                                text="夜班費用"
                            )
                        ),
                        QuickReplyItem(
                            action=MessageAction(
                                label="❌ 取消修改",
                                text="取消修改"
                            )
                        )
                    ]
                    
                    reason_quick_reply = QuickReply(items=reason_quick_reply_items)
                    
                    # 構建完整的回覆消息
                    time_reminder = "⏰ 此對話將在 5 分鐘後自動過期"
                    cancel_reminder = "💡 選擇原因或輸入自定義原因"
                    
                    return {
                        "type": "text_with_quick_reply",
                        "text": f"""{search_header}{prompt_message}

{cancel_reminder}
{time_reminder}""",
                        "quick_reply": reason_quick_reply
                    }
                else:
                    # 有明确原因，直接执行修改
                    result = execute_fare_modification(trip, modification_intent, user_id)
                    
                    # 🔥 修復：正確處理字典格式的返回結果
                    if isinstance(result, dict) and 'flex_message' in result:
                        # 返回Flex格式結果
                        return result
                    else:
                        # 降級為文字結果
                        return f"{search_header}✅ 找到唯一匹配班次並執行修改：\n\n{result}"
            
            # 只是查詢，詢問如何修改
            if use_flex:
                from modules.flex_designs.ai_fare_query_flex import create_ai_search_result_flex
                search_info = {
                    'query': message_text,
                    'criteria_text': understood_criteria.replace('\n', ', ').replace('  ', '')
                }
                return create_ai_search_result_flex(search_info, [trip], confidence)
            else:
                return f"""{search_header}🎯 找到唯一匹配的班次：

📋 班次 #{trip['id']} ({trip['category']})
📍 路線：{trip['start_point']} → {trip['end_point']}
🚕 {trip['driver_id']}
💰 當前費用：{fare_display}

請告訴我要如何調整費用？
例如：「改成錶價400加成80，客戶要求調整」

或使用傳統格式：記錄車資 {trip['id']} [錶價] [加成] [原因]

💡 提示：現在您可以直接說「改成錶價XXX加成XXX」，我會記住這個班次！"""
        
        else:
            # 多個匹配的情況 - 🔥 修復：直接顯示所有結果，不使用分頁
            if use_flex:
                from modules.flex_designs.ai_fare_query_flex import create_ai_search_result_flex
                search_info = {
                    'query': message_text,
                    'criteria_text': understood_criteria.replace('\n', ', ').replace('  ', '')
                }
                return create_ai_search_result_flex(search_info, matcher.search_completed_trips(criteria), confidence)
            else:
                trips_summary = format_multiple_trips_summary(matcher.search_completed_trips(criteria))
                
                if modification_intent:
                    return f"""{search_header}⚠️ 找到 {len(matcher.search_completed_trips(criteria))} 個匹配班次，請選擇：

{trips_summary}"""
                
                # 只是查詢多個結果
                return f"""{search_header}{trips_summary}"""
            
    except Exception as e:
        logger.error(f"處理智能車資查詢時出錯: {e}")
        traceback.print_exc()
        return f"❌ 處理查詢時出錯: {str(e)}"

def execute_fare_modification(trip: Dict, modification_intent: Dict, user_id: str) -> str:
    """準備車資修改確認界面（參考預約叫車邏輯 - 收集信息，暫停等待確認）"""
    try:
        trip_id = trip['id']
        current_meter = trip['meter_fare']
        current_extra = trip['extra_fare']
        
        # 從修改意圖中獲取新的費用
        new_meter = modification_intent.get('meter_fare', current_meter)
        new_extra = modification_intent.get('extra_fare', current_extra)
        reason = modification_intent.get('reason', '透過AI智能修改')
        
        # 🔥 确保原因不为空
        if not reason or reason.strip() == '':
            reason = '透過AI智能修改'
        
        logger.info(f"📋 準備AI修改確認界面: trip_id={trip_id}, meter={current_meter}->{new_meter}, extra={current_extra}->{new_extra}, reason='{reason}'")
        
        # 🔥 參考預約叫車：保存待執行的修改到上下文（關鍵步驟！）
        conversation_manager.set_pending_modification(user_id, {
            'trip_id': trip_id,
            'meter_fare': new_meter,
            'extra_fare': new_extra,
            'reason': reason,
            'trip': trip
        })
        
        logger.info(f"✅ 已保存待執行修改到上下文: trip_id={trip_id}")
        
        # 🔥 參考預約叫車：收集信息，顯示確認界面，不執行數據庫操作
        modification_info = {
            'trip_id': trip_id,
            'category': trip.get('category', '未分類'),
            'route': f"{trip.get('start_point', '?')} → {trip.get('end_point', '?')}",
            'driver_id': trip.get('driver_id', 'N/A'),
            'old_meter': current_meter,
            'old_extra': current_extra,
            'new_meter': new_meter,
            'new_extra': new_extra,
            'reason': reason,
            'total_change': (new_meter + new_extra) - (current_meter + current_extra)
        }
        
        from modules.flex_designs.ai_fare_query_flex import create_ai_modification_confirm_flex
        flex_result = create_ai_modification_confirm_flex(modification_info)
        
        if flex_result and isinstance(flex_result, dict):
            # 🔥 返回確認界面（像預約叫車一樣暫停等待用戶響應）
            logger.info(f"✅ 已顯示確認界面，等待用戶響應")
            return flex_result
        else:
            # 如果Flex Message創建失敗，使用文本備用
            confirmation_text = f"""🤖 AI智能修改確認

📊 修改詳情：
• 班次：#{trip_id} ({trip['category']})
• 路線：{trip['start_point']} → {trip['end_point']}
• 費用變更：{current_meter}+{current_extra} → {new_meter}+{new_extra}
• 總計變化：{(new_meter + new_extra) - (current_meter + current_extra):+d} 元
• 修改原因：{reason}

⚠️ 請確認是否執行此修改？
回覆「確認AI修改 {trip_id} {new_meter} {new_extra} {reason}」執行修改
回覆「取消AI修改」取消修改"""
            
            return confirmation_text
        
    except Exception as e:
        logger.error(f"準備車資修改確認時出錯: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ 準備修改確認失敗: {str(e)}"

# 🔥 注意：execute_confirmed_ai_modification 函數已移除
# 確認邏輯現在直接在 text_message_handler.py 中處理，照搬預約叫車的模式

def format_multiple_trips_summary(trips: List[Dict]) -> str:
    """格式化多個班次的摘要 - 简洁版"""
    if not trips:
        return "❌ 沒有找到班次"
    
    total_trips = len(trips)
    result = f"🎯 找到 {total_trips} 個班次:\n\n"
    
    # 显示所有班次
    for i, trip in enumerate(trips, 1):
        meter_fare = trip['meter_fare'] or 0
        extra_fare = trip['extra_fare'] or 0
        
        # 正確處理負加成顯示
        if extra_fare >= 0:
            fare_display = f"{meter_fare}+{extra_fare}"
        else:
            fare_display = f"{meter_fare}{extra_fare}"  # 負數自帶負號
        
        # 添加更詳細的信息，格式更紧凑
        result += f"📍 {i}. 班次#{trip['id']} ({trip['category']})\n"
        result += f"   📅 {trip['date'].strftime('%m-%d')}\n"
        result += f"   🚩 {trip['start_point']} → {trip['end_point']}\n"
        result += f"   🚕{trip['driver_id']} | 💰 {fare_display} = {meter_fare + extra_fare}元\n\n"
    
    # 简化操作提示
    result += "💡 操作提示:\n"
    result += "  修改#[ID] [錶價] [加成]\n"
    result += "  修改第[N]個 [錶價] [加成]\n"
    result += "  查看[ID]"
    
    return result

def format_understood_criteria(criteria: Dict) -> str:
    """格式化AI理解的搜索條件"""
    conditions = []
    
    # 🔥 新增：班次ID條件顯示
    if criteria.get('trip_id'):
        conditions.append(f"📋 #{criteria['trip_id']}")
    
    if criteria.get('date'):
        date_str = criteria['date'].strftime('%m/%d')
        conditions.append(f"📅 {date_str}")
    
    if criteria.get('driver_id'):
        conditions.append(f"🚕 {criteria['driver_id']}")  
    
    if criteria.get('category'):
        conditions.append(f"🏷️ {criteria['category']}")
    
    if criteria.get('locations'):
        conditions.append(f"📍 {', '.join(criteria['locations'])}")
    
    if criteria.get('sequence'):
        if criteria['sequence'] > 0:
            conditions.append(f"🔢 第{criteria['sequence']}個")
        else:
            conditions.append(f"🔢 倒數第{abs(criteria['sequence'])}個")
    
    if criteria.get('time_range'):
        start, end = criteria['time_range']
        conditions.append(f"⏰ {start}:00-{end}:00")
    
    if not conditions:
        conditions.append("❓ 未識別到條件")
    
    # 添加信心度指示
    confidence = criteria.get('confidence', 'high')
    confidence_emoji = {
        'high': '🟢',
        'low': '🟡', 
        'very_low': '🔴'
    }
    
    conditions.append(f"{confidence_emoji.get(confidence, '⚪')} {confidence}")
    
    return '🧠 ' + ' | '.join(conditions)

def parse_fare_modification_intent(message_text: str) -> Optional[Dict]:
    """解析車資修改意圖（增強版）"""
    try:
        result = {}
        
        # 🔥 新增：檢測簡單數字格式 (班次ID 錶價 加成 原因)
        # 例如：修改班次1505 270 -40 怡平路沒搭車
        # 🔥 修复：支持$符号格式，如：修改班次1560$400 +100
        simple_format_patterns = [
            r'修改班次#?(\d+)\s+(\d+)\s+([+-]?\d+)',        # 空格分隔：修改班次1505 270 -40
            r'修改班次#?(\d+)\$(\d+)\s+([+-]?\d+)',        # $符号格式：修改班次1560$400 +100
            r'修改班次#?(\d+)\s+\$(\d+)\s+([+-]?\d+)',     # 空格+$格式
        ]
        
        simple_format_match = None
        for pattern in simple_format_patterns:
            simple_format_match = re.search(pattern, message_text)
            if simple_format_match:
                result['meter_fare'] = int(simple_format_match.group(2))
                result['extra_fare'] = int(simple_format_match.group(3))
                # 檢查是否有原因在數字後面
                after_numbers = message_text[simple_format_match.end():].strip()
                if after_numbers and not after_numbers.isdigit() and len(after_numbers) > 2:
                    # 🔥 过滤掉纯数字或过短的内容
                    result['reason'] = after_numbers
                logger.info(f"簡單格式解析成功 (模式: {pattern}): 錶價{result['meter_fare']}, 加成{result['extra_fare']}, 原因'{result.get('reason', '無')}'")
                break
        
        # 提取錶價 - 增強版本
        if 'meter_fare' not in result:  # 如果簡單格式沒有解析到，才使用複雜模式
            meter_patterns = [
                r'錶價\s*(\d+)',
                r'改成\s*錶價?\s*(\d+)',
                r'錶價?\s*改成?\s*(?:為|到|成)?\s*(\d+)',
                r'錶價?\s*調整?\s*(?:為|到|成)?\s*(\d+)',
                r'車資\s*(\d+)',
                r'費用\s*(\d+)',
                r'\$\s*(\d+)',         # $符號
                r'(\d+)\s*元',         # 數字+元
                r'改成\s*(\d+)\s*元',
                r'調整為\s*(\d+)',
                r'變成\s*(\d+)'
            ]
            
            for pattern in meter_patterns:
                match = re.search(pattern, message_text)
                if match:
                    result['meter_fare'] = int(match.group(1))
                    break
        
        # 提取加成 - 增強版本
        if 'extra_fare' not in result:  # 如果簡單格式沒有解析到，才使用複雜模式
            extra_patterns = [
                r'加成\s*([+-]?\d+)',  # 🔥 修复：支持负数加成
                r'加收\s*([+-]?\d+)',
                r'額外\s*([+-]?\d+)',
                r'夜班費?\s*([+-]?\d+)',
                r'加費\s*([+-]?\d+)',
                r'補貼\s*([+-]?\d+)', 
                r'折扣\s*([+-]?\d+)',
                r'優惠\s*([+-]?\d+)',
                r'調整\s*([+-]?\d+)',
                r'\+\s*([+-]?\d+)',     # +符號
                r'另加\s*([+-]?\d+)'
            ]
            
            for pattern in extra_patterns:
                match = re.search(pattern, message_text)
                if match:
                    result['extra_fare'] = int(match.group(1))
                    break
        
        # 如果只有一個數字，根據上下文判斷
        if not result:
            single_number = re.search(r'(?:改成|調整為|變成)\s*(\d+)', message_text)
            if single_number:
                number = int(single_number.group(1))
                if number >= 200:  # 大於200的數字通常是錶價
                    result['meter_fare'] = number
                else:  # 小於200的數字通常是加成
                    result['extra_fare'] = number
        
        # 🔥 增强原因提取：支持更多格式（但避免重複提取）
        if 'reason' not in result:  # 如果簡單格式沒有提取到原因，才使用複雜模式
            reason_patterns = [
                r'，\s*([^0-9]+.+?)(?:\s*$|[。，])',      # 🔥 修复：逗号后非数字开头的内容
                r'因為\s*(.+?)(?:\s*$|[。，])',      # "因為..."
                r'原因[是:：]\s*(.+?)(?:\s*$|[。，])',  # "原因是..."、"原因："
                r'客戶\s*(.+?)(?:\s*$|[。，])',      # "客戶..."
                r'[\s，](.+要求.+?)(?:\s*$|[。，])', # 包含"要求"的內容
                r'等候\s*(.+?)(?:\s*$|[。，])',      # 🔥 新增："等候..."
                r'等待\s*(.+?)(?:\s*$|[。，])',      # 🔥 新增："等待..."
                r'夜班\s*(.+?)(?:\s*$|[。，])',      # 🔥 新增："夜班..."
                r'加班\s*(.+?)(?:\s*$|[。，])',      # 🔥 新增："加班..."
                r'[\s，](.+小時.+?)(?:\s*$|[。，])', # 🔥 新增：包含"小時"的内容
                r'[\s，](.+調整.+?)(?:\s*$|[。，])', # 🔥 新增：包含"調整"的内容
            ]
            
            reason = None
            for i, pattern in enumerate(reason_patterns):
                match = re.search(pattern, message_text)
                if match:
                    potential_reason = match.group(1).strip()
                    # 过滤掉纯数字和太短的内容
                    if len(potential_reason) > 1 and not potential_reason.isdigit():
                        # 🔥 进一步清理原因文本
                        # 移除可能的车资相关数字
                        cleaned_reason = re.sub(r'^\d+\s*', '', potential_reason)  # 移除开头的数字
                        cleaned_reason = re.sub(r'\s*\d+\s*$', '', cleaned_reason)  # 移除结尾的数字
                        
                        # 🔥 新增：过滤掉明显是费用描述的内容
                        fee_patterns = [
                            r'^錶價\d+',           # 錶價260
                            r'^加成\d+',           # 加成100  
                            r'^錶價\d+加成\d*$',   # 錶價260加成, 錶價260加成100
                            r'^\d+加成\d*$',       # 260加成, 260加成100
                            r'^\d+錶價\d*$',       # 260錶價
                        ]
                        
                        is_fee_description = any(re.match(pattern, cleaned_reason) for pattern in fee_patterns)
                        
                        if not is_fee_description and len(cleaned_reason.strip()) > 2:
                            reason = cleaned_reason.strip()
                            logger.info(f"原因提取成功 (模式{i+1}): '{reason}' 来自输入: '{message_text}'")
                            break
            
            if reason:
                result['reason'] = reason
        
        # 🔥 如果常规模式没有提取到原因，尝试更宽松的提取
        if 'reason' not in result and result:  # 只有當result有內容但沒有原因時才執行
            # 查找逗号或空格后的非数字内容，且不是费用描述
            loose_patterns = [
                r'[，,]\s*([^0-9錶價加成$+\-]+.+?)(?:\s*$|[。，])',    # 逗号后的非费用内容，排除数字、$、+、-符号
                r'\s+([^0-9錶價加成$+\-]+.+?)(?:\s*$|[。，])',        # 空格后的非费用内容，排除数字、$、+、-符号
            ]
            
            for pattern in loose_patterns:
                match = re.search(pattern, message_text)
                if match:
                    potential_reason = match.group(1).strip()
                    # 🔥 增强过滤：排除纯数字、带符号的数字、费用相关词汇
                    exclude_words = ['加成', '錶價', '修改', '班次', '車資', '費用', '+', '-', '$']
                    is_number_like = re.match(r'^[+\-]?\d+$', potential_reason)  # 匹配 +100, -50, 100 等
                    
                    if (len(potential_reason) > 2 and 
                        not is_number_like and
                        not any(word in potential_reason for word in exclude_words)):
                        result['reason'] = potential_reason
                        logger.info(f"宽松原因提取成功: '{result['reason']}' 来自输入: '{message_text}'")
                        break
        
        # 如果沒有明確原因但有修改意圖，生成通用原因
        if 'reason' not in result and result:
            if '夜班' in message_text or '晚上' in message_text:
                result['reason'] = "夜班服務費"
            elif '等候' in message_text or '等待' in message_text:
                result['reason'] = "等候時間調整"
            elif '加班' in message_text:
                result['reason'] = "加班費調整"
            elif '客戶' in message_text:
                result['reason'] = "客戶要求調整"
            elif '要求' in message_text or '需要' in message_text:
                result['reason'] = "費用調整要求"
            else:
                result['reason'] = "透過AI智能修改"
            
        # 🔥 添加调试日志
        logger.info(f"AI修改意图解析结果: {result} (输入: '{message_text}')")
            
        return result if result else None
        
    except Exception as e:
        logger.error(f"解析車資修改意圖時出錯: {e}")
        return None 
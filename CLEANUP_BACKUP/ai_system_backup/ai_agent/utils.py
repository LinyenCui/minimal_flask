

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.helpers import parse_date_input

logger = logging.getLogger(__name__)

class NaturalQueryParser:
    """
    自然語言查詢解析器，用於從用戶輸入中提取實體。
    """
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
            '醫院', '火車站', '住家', '市區', '診所', '東洋', '臨時' # 重新加入診所和東洋，因為這裡只做提取，不影響類別判斷
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
        智能判斷數字是否更可能是司機ID而非日期
        考慮位置、上下文和其他線索
        """
        driver_context_patterns = [
            rf'司機\s*{re.escape(number)}',     # 司機123
            rf'{re.escape(number)}\s*號司機',   # 123號司機
            rf'司機.?{re.escape(number)}',      # 司機 123
        ]
        
        is_in_driver_context = any(re.search(pattern, query) for pattern in driver_context_patterns)
        
        if not is_in_driver_context:
            return False
        
        all_numbers = re.findall(r'(?<!\d)\d{3,4}(?!\d)', query)
        driver_candidates = []
        
        for num in all_numbers:
            for pattern in driver_context_patterns:
                match = re.search(pattern, query)
                if match:
                    driver_pos = query.find('司機')
                    num_pos = query.find(num)
                    distance = abs(driver_pos - num_pos)
                    is_direct = bool(re.search(rf'司機\s*{re.escape(num)}', query))
                    
                    driver_candidates.append({
                        'number': num,
                        'distance': distance,
                        'is_direct': is_direct,
                        'position': num_pos
                    })
                    break
        
        if len(driver_candidates) <= 1:
            return is_in_driver_context
        
        best_candidate = None
        for candidate in driver_candidates:
            if candidate['number'] == number:
                for other in driver_candidates:
                    if other['number'] != number:
                        if other['is_direct'] and not candidate['is_direct']:
                            return False
                        
                        if (re.match(r'^[01]\d[0-3]\d$', number) and 
                            other['distance'] < candidate['distance']):
                            return False
                
                return True
        
        return False

    def parse_natural_query(self, query: str) -> Dict:
        """解析自然語言查詢"""
        criteria = {
            'date': None,
            'time_range': None,
            'locations': [],
            'sequence': None,
            'driver_id': None,
            'category': None,
            'trip_id': None,
            'raw_query': query,
            'confidence': 'high'
        }
        
        query_lower = query.lower()
        
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
                    criteria['confidence'] = 'high'
                    return criteria
                except (ValueError, IndexError):
                    continue
        
        date_extracted = False
        possible_dates = []
        
        for relative_word in ['今天', '今日', '昨天', '昨日', '前天', '明天', '明日', '後天']:
            if relative_word in query:
                possible_dates.append(relative_word)
        
        for weekday in ['一', '二', '三', '四', '五', '六', '日']:
            weekday_patterns = [
                f'星期{weekday}',
                f'週{weekday}',
                f'禮拜{weekday}',
            ]
            if weekday in ['一', '二', '三', '四', '五', '六', '日']:
                strict_patterns = [
                    f'(^|\\s){weekday}(\\s|$)',
                    f'下{weekday}',
                    f'這{weekday}',
                    f'上{weekday}',
                ]
                false_positive_patterns = [
                    f'查{weekday}',
                    f'第{weekday}',
                    f'{weekday}下',
                    f'{weekday}起',
                    f'{weekday}般',
                    f'{weekday}些',
                ]
                
                has_false_positive = any(re.search(pattern, query) for pattern in false_positive_patterns)
                if has_false_positive:
                    continue
                
                has_strict_match = any(re.search(pattern, query) for pattern in strict_patterns)
                if not has_strict_match:
                    continue
            
            if any(pattern in query for pattern in weekday_patterns):
                possible_dates.append(weekday)
        
        date_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'\d{1,2}[-/]\d{1,2}',
            r'\d{1,2}月\d{1,2}日?',
            r'(?<!\d)\d{3,4}(?!\d)'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                if re.match(r'^\d{3,4}$', match):
                    is_driver_id = self._is_likely_driver_id(match, query)
                    if is_driver_id:
                        continue
                
                possible_dates.append(match)
        
        for date_str in possible_dates:
            try:
                parsed_date = parse_date_input(date_str)
                if parsed_date:
                    criteria['date'] = parsed_date
                    date_extracted = True
                    break
            except Exception:
                continue
        
        for pattern, time_range in self.time_patterns.items():
            match = re.search(pattern, query)
            if match:
                if callable(time_range):
                    criteria['time_range'] = time_range(match)
                else:
                    criteria['time_range'] = time_range
                break
        
        for pattern, sequence in self.sequence_patterns.items():
            if re.search(pattern, query):
                criteria['sequence'] = sequence
                break
        
        for keyword in self.location_keywords:
            if keyword in query:
                criteria['locations'].append(keyword)
        
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
        
        if '診所' in query:
            criteria['category'] = '診所'
        elif '東洋' in query:
            criteria['category'] = '東洋'
        elif '臨時' in query:
            criteria['category'] = '臨時'
        
        parsed_criteria_count = sum([
            1 if criteria['date'] else 0,
            1 if criteria['driver_id'] else 0,
            1 if criteria['category'] else 0,
            1 if criteria['locations'] else 0,
            1 if criteria['sequence'] else 0,
            1 if criteria['time_range'] else 0,
            1 if criteria['trip_id'] else 0
        ])
        
        if parsed_criteria_count == 0:
            criteria['confidence'] = 'very_low'
        elif parsed_criteria_count == 1:
            criteria['confidence'] = 'low'
        elif parsed_criteria_count >= 2:
            criteria['confidence'] = 'high'
        
        return criteria

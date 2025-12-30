"""
查詢分類器 - 區分「一般查詢」與「狀態篩選」與「狀態詢問/操作請求」

設計原則（2025-12-17 修正）：
三條路徑：
1. 一般查詢：「明天新建路」「12/7司機5386」→ advanced_query_processor（地點/司機條件）
2. 狀態篩選：「待派班次」「請假班次」→ advanced_query_processor（status=xxx）
3. 狀態詢問/操作請求：「明天新建路狀態」「明天新建路請假」→ 智能助手（clarify_user_intent）

核心規則：
- 有「狀態」「狀況」字眼 → 走智能助手（clarify_user_intent，問用戶想做什麼）
- 有「狀態詞+班次」（如「待派班次」）但無「狀態」字眼 → 狀態篩選查詢
- 有「日期+地點+狀態詞」（如「明天新建路請假」）→ 走智能助手（操作請求）
- 純「日期+地點/司機」→ 一般查詢
"""

import logging
import re

logger = logging.getLogger(__name__)

# 實際狀態詞（用於判斷操作請求或狀態篩選）
STATUS_WORDS = {'待派', '準備', '已完成', '註銷', '衝突', '請假', '取消'}

# 操作動詞（表示用戶想做某事，不是查詢）
ACTION_VERBS = {'要', '想', '幫', '給', '設', '改', '變', '修', '更', '刪', '除', '置'}


def is_status_filter_query(text: str) -> bool:
    """
    判斷是否為狀態篩選查詢（用 status=xxx 條件篩選班次）
    
    這類查詢應該走 advanced_query_processor，用 SQL 的 status 條件篩選。
    
    規則：
    - 操作性狀態詞 + 班次/列表語氣（無「狀態」「狀況」字眼）→ True
    - 包含「狀態」「狀況」字眼 → False（這是狀態詢問，應該走智能助手 clarify）
    - 🔥 「已完成班次」+ 日期/司機 → False（這是查詢已完成的班次，不是狀態篩選）
    
    🔥 2025-12-18 重要修復：
    - 「已完成」不是操作性狀態詞，它是一個查詢修飾詞
    - 「今天司機61553已完成班次」應該走直接查詢流程，不是狀態篩選
    
    Examples:
        "查待派班次" → True（狀態篩選）
        "列出請假班次" → True（狀態篩選）
        "有哪些衝突班次" → True（狀態篩選）
        "今天司機61553已完成班次" → False（🔥 已完成班次查詢，不是狀態篩選）
        "明天新建路的狀態" → False（狀態詢問，走智能助手）
        "今天新建路狀態" → False（狀態詢問，走智能助手）
        "明天新建路" → False（一般查詢）
    """
    # 🔥 關鍵：有「狀態」「狀況」字眼 → 不是狀態篩選，是狀態詢問
    # 狀態詢問應該走智能助手的 clarify_user_intent
    if '狀態' in text or '狀況' in text:
        logger.info(f"🤖 狀態詢問，走智能助手: {text}")
        return False
        
    # 🔥 2025-12-30 修復：明確的修改/設置命令不應該被視為查詢
    # 例如：修改#5513$140-140（班次衝突...）雖然包含「衝突」，但是是用來描述原因的
    if text.startswith(('修改', '設為', '改', '更新', '設置')):
        logger.info(f"🤖 明確的操作命令（修改/設為...），走智能助手: {text}")
        return False
    
    # 🔥 2025-12-18：「已完成班次」+ 日期或司機 → 不是狀態篩選，是查詢已完成的班次
    # 這種情況應該走直接查詢流程
    has_completed = '已完成' in text
    has_date = _has_date_pattern(text)
    has_driver = bool(re.search(r'司機\d+|\d{4,5}號?司機', text))
    
    if has_completed and (has_date or has_driver):
        logger.info(f"📊 已完成班次查詢（已完成+日期/司機），不是狀態篩選: {text}")
        return False
    
    # 操作性狀態詞（不包含「已完成」）+ 班次/列表語氣 → 狀態篩選查詢
    # 語氣詞：班次、列表、有哪些、列出、查
    OPERATION_STATUS_WORDS = {'待派', '準備', '註銷', '衝突', '請假', '取消'}
    query_indicators = ['班次', '列表', '有哪些', '列出', '查']
    has_operation_status = any(s in text for s in OPERATION_STATUS_WORDS)
    has_query_indicator = any(q in text for q in query_indicators)
    
    if has_operation_status and has_query_indicator:
        logger.info(f"📊 狀態篩選查詢（操作性狀態詞+語氣詞）: {text}")
        return True
    
    return False


def is_simple_direct_query(text: str) -> bool:
    """
    判斷是否為簡單直接查詢（一般 range 查詢，走 advanced_query_processor）
    
    這類查詢是純粹的「日期+地點/司機」查詢，不涉及狀態操作。
    
    規則：
    1. 包含「狀態」「狀況」字眼 → False（狀態詢問，走智能助手 clarify）
    2. 如果是狀態篩選查詢 → False（走狀態篩選流程）
    3. 🔥 「日期+司機+已完成班次」→ True（查詢已完成班次，不是操作）
    4. 「日期+地點+操作性狀態詞」（如「明天新建路請假」）→ False（操作請求）
    5. 有動詞+狀態詞（如「要請假」）→ False（操作請求）
    6. 「日期+地點」或「日期+司機」→ True（一般查詢）
    7. 其他 → False（走智能助手）
    
    🔥 2025-12-18 重要修復：
    - 「已完成」是一個查詢修飾詞，不是操作請求
    - 「已完成班次」表示查詢過去態數據，應該走直接查詢流程
    
    Examples:
        "明天新建路" → True（一般查詢）
        "12/7-12/13司機61553" → True（一般查詢）
        "今天司機61553診所已完成班次" → True（🔥 已完成班次查詢）
        "明天新建路狀態" → False（狀態詢問，走智能助手）
        "待派班次" → False（狀態篩選查詢）
        "明天新建路請假" → False（操作請求）
    """
    # 規則1：有「狀態」「狀況」字眼 → 狀態詢問，走智能助手
    if '狀態' in text or '狀況' in text:
        logger.info(f"🤖 狀態詢問，走智能助手: {text}")
        return False
    
    # 規則2：狀態篩選查詢不走這裡
    if is_status_filter_query(text):
        logger.info(f"🔀 分流到狀態篩選查詢: {text}")
        return False
    
    # 先提取條件
    has_date = _has_date_pattern(text)
    has_location = _has_location_pattern(text)
    has_action_verb = any(v in text for v in ACTION_VERBS)
    has_driver = bool(re.search(r'司機\d+|\d{4,5}號?司機', text))
    
    # 🔥 2025-12-18：「已完成」是查詢修飾詞，不是操作
    # 操作性狀態詞：待派、準備、註銷、衝突、請假、取消（這些表示要做某種操作）
    # 查詢性修飾詞：已完成（這個表示查詢已完成的班次）
    OPERATION_STATUS_WORDS = {'待派', '準備', '註銷', '衝突', '請假', '取消'}
    has_operation_status = any(s in text for s in OPERATION_STATUS_WORDS)
    has_completed_keyword = '已完成' in text
    
    # 規則3：🔥 「日期+司機+已完成班次」→ 直接查詢（不是操作）
    if has_date and has_driver and has_completed_keyword and not has_operation_status:
        logger.info(f"📊 已完成班次查詢（日期+司機+已完成）: {text}")
        return True
    
    # 規則4：「日期+地點+操作性狀態詞」→ 操作請求
    if has_date and has_location and has_operation_status:
        logger.info(f"🤖 走智能助手（日期+地點+操作性狀態詞=操作請求）: {text}")
        return False
    
    # 規則5：有動詞+狀態詞 → 操作請求
    if has_action_verb and (has_operation_status or has_completed_keyword):
        logger.info(f"🤖 走智能助手（動詞+狀態詞=操作請求）: {text}")
        return False
    
    # 規則6：「日期+地點」或「日期+司機」或「日期+類別」→ 一般查詢
    has_category = any(c in text for c in ['診所', '東洋', '臨時'])
    
    if has_date and (has_location or has_driver or has_category):
        logger.info(f"📊 一般查詢（日期+地點/司機/類別）: {text}")
        return True
    
    # 其他情況：走智能助手
    logger.info(f"🤖 走智能助手（其他情況）: {text}")
    return False


def determine_query_table(text: str) -> str:
    """
    根據日期和「已完成」關鍵字判斷應該查哪個表
    
    🔥 2025-12-18 重要修復：
    - 今天是一個「流動的邊界」
    - 今天已經執行完成、掉進 completed_trips 的班次 → 過去態
    - 今天還在 trips 表、尚未執行完成的班次 → 現在態
    
    規則：
    1. 有「已完成」關鍵字 → 查 completed_trips（不論日期是今天或過去）
    2. 日期在過去（< 今天）→ 查 completed_trips
    3. 日期是今天且無「已完成」關鍵字 → 查 trips
    4. 日期在未來 → 查 trips
    
    Returns:
        'completed_trips' - 過去態（已完成班次）
        'trips' - 現在態（活躍班次）
    """
    from modules.utils.taiwan_time import get_taiwan_date
    from datetime import date
    
    today = get_taiwan_date()
    
    # 🔥 關鍵：檢查是否有「已完成」關鍵字
    has_completed_keyword = '已完成' in text
    
    # 嘗試解析日期範圍
    range_match = re.search(r'(\d{1,2})[/\-](\d{1,2})[~\-至到](\d{1,2})[/\-](\d{1,2})', text)
    if range_match:
        # 日期範圍查詢
        start_month, start_day = int(range_match.group(1)), int(range_match.group(2))
        end_month, end_day = int(range_match.group(3)), int(range_match.group(4))
        
        # 推斷年份
        year = today.year
        start_year = year
        end_year = year
        
        # 情況：12月查 "12/14 - 1/2" -> 跨年
        if start_month > end_month:
            end_year += 1
            
        try:
            end_date = date(end_year, end_month, end_day)
            # 如果結束日期在過去，整個範圍都是過去態
            if end_date < today:
                logger.info(f"📅 日期範圍 {end_date} < 今天 {today}，查過去態")
                return 'completed_trips'
            else:
                # 🔥 範圍包含今天或未來：根據「已完成」關鍵字決定
                if has_completed_keyword:
                    logger.info(f"📅 日期範圍包含今天或未來，但有「已完成」關鍵字，查過去態")
                    return 'completed_trips'
                else:
                    logger.info(f"📅 日期範圍包含今天或未來，查現在態")
                    return 'trips'
        except ValueError:
            pass
    
    # 嘗試解析單一日期
    single_date_match = re.search(r'(\d{1,2})[/\-](\d{1,2})', text)
    if single_date_match:
        month, day = int(single_date_match.group(1)), int(single_date_match.group(2))
        year = today.year
        try:
            query_date = date(year, month, day)
            if query_date < today:
                logger.info(f"📅 日期 {query_date} < 今天 {today}，查過去態")
                return 'completed_trips'
            elif query_date == today:
                # 🔥 今天是流動的邊界：根據「已完成」關鍵字決定
                if has_completed_keyword:
                    logger.info(f"📅 日期是今天 {today}，有「已完成」關鍵字，查過去態")
                    return 'completed_trips'
                else:
                    logger.info(f"📅 日期是今天 {today}，無「已完成」關鍵字，查現在態")
                    return 'trips'
            else:
                logger.info(f"📅 日期 {query_date} > 今天，查現在態")
                return 'trips'
        except ValueError:
            pass
    
    # 相對日期判斷
    if '昨天' in text or '前天' in text or '上週' in text:
        logger.info(f"📅 相對日期（昨天/前天/上週），查過去態")
        return 'completed_trips'
    
    # 🔥 「今天」關鍵字判斷
    if '今天' in text:
        if has_completed_keyword:
            logger.info(f"📅 今天 + 已完成關鍵字，查過去態")
            return 'completed_trips'
        else:
            logger.info(f"📅 今天（無已完成關鍵字），查現在態")
            return 'trips'
    
    # 默認查現在態
    logger.info(f"📅 默認查現在態")
    return 'trips'


def parse_direct_query(text: str) -> dict:
    """
    解析直接查詢的參數
    
    Returns:
        dict: {
            'start_date': date,
            'end_date': date,
            'driver_id': int or None,
            'category': str or None
        }
    """
    from modules.utils.taiwan_time import get_taiwan_date
    from datetime import date, timedelta
    
    today = get_taiwan_date()
    result = {
        'start_date': None,
        'end_date': None,
        'driver_id': None,
        'category': None
    }
    
    # 解析司機
    driver_match = re.search(r'司機(\d+)', text)
    if driver_match:
        result['driver_id'] = int(driver_match.group(1))
    
    # 解析類別
    if '診所' in text:
        result['category'] = '診所'
    elif '東洋' in text:
        result['category'] = '東洋'
    elif '臨時' in text:
        result['category'] = '臨時'
    
    # 解析日期範圍
    range_match = re.search(r'(\d{1,2})[/\-](\d{1,2})[~\-至到](\d{1,2})[/\-](\d{1,2})', text)
    if range_match:
        start_month, start_day = int(range_match.group(1)), int(range_match.group(2))
        end_month, end_day = int(range_match.group(3)), int(range_match.group(4))
        year = today.year
        
        # 智能年份判斷
        # 如果開始月份比當前月份大很多（例如在1月查12月），可能是去年？但通常查班次是查近期。
        # 假設：
        # 1. 跨年範圍：12月到1月 -> 結束年份+1
        
        start_year = year
        end_year = year
        
        # 情況：12月查 "12/14 - 1/2"
        if start_month > end_month:
            end_year += 1
            
        try:
            result['start_date'] = date(start_year, start_month, start_day)
            result['end_date'] = date(end_year, end_month, end_day)
            logger.info(f"📅 解析日期範圍: {result['start_date']} 到 {result['end_date']}")
            return result
        except ValueError:
            pass
    
    # 解析單一日期
    single_match = re.search(r'(\d{1,2})[/\-](\d{1,2})', text)
    if single_match:
        month, day = int(single_match.group(1)), int(single_match.group(2))
        year = today.year
        try:
            query_date = date(year, month, day)
            result['start_date'] = query_date
            result['end_date'] = query_date
            logger.info(f"📅 解析單一日期: {query_date}")
            return result
        except ValueError:
            pass
    
    # 解析相對日期
    if '今天' in text:
        result['start_date'] = today
        result['end_date'] = today
    elif '昨天' in text:
        yesterday = today - timedelta(days=1)
        result['start_date'] = yesterday
        result['end_date'] = yesterday
    elif '前天' in text:
        day_before = today - timedelta(days=2)
        result['start_date'] = day_before
        result['end_date'] = day_before
    elif '明天' in text:
        tomorrow = today + timedelta(days=1)
        result['start_date'] = tomorrow
        result['end_date'] = tomorrow
    elif '後天' in text:
        day_after = today + timedelta(days=2)
        result['start_date'] = day_after
        result['end_date'] = day_after
    
    if result['start_date']:
        logger.info(f"📅 解析相對日期: {result['start_date']}")
    
    return result


def _has_date_pattern(text: str) -> bool:
    """檢查是否包含日期模式"""
    # 相對日期
    relative_dates = ['今天', '昨天', '前天', '明天', '後天', '本週', '上週', '下週']
    for rd in relative_dates:
        if rd in text:
            return True
    
    # 絕對日期格式
    date_patterns = [
        r'\d{1,2}/\d{1,2}',      # 12/7
        r'\d{1,2}-\d{1,2}',      # 12-7
        r'\d{1,2}月\d{1,2}',     # 12月7
        r'\d{4}-\d{1,2}-\d{1,2}' # 2025-12-07
    ]
    for pattern in date_patterns:
        if re.search(pattern, text):
            return True
    
    return False


def _has_location_pattern(text: str) -> bool:
    """檢查是否包含地點模式（排除已知關鍵字後有剩餘內容）"""
    remaining = text
    
    # 移除已知關鍵字
    remove_patterns = [
        '查詢班次', '查班次', '查已完成', '統計金額',
        '今天', '昨天', '前天', '明天', '後天', '本週', '上週', '下週',
        '診所', '東洋', '臨時',  # 類別不算地點
        '待派', '準備', '已完成', '註銷', '衝突', '請假', '取消',
        '狀態', '狀況',  # 查詢意圖詞不算地點
        '的', '班次', '查', '列出'
    ]
    for kw in remove_patterns:
        remaining = remaining.replace(kw, '')
    
    # 移除日期格式
    remaining = re.sub(r'\d{1,2}/\d{1,2}', '', remaining)
    remaining = re.sub(r'\d{1,2}-\d{1,2}', '', remaining)
    remaining = re.sub(r'\d{1,2}月\d{1,2}', '', remaining)
    remaining = re.sub(r'司機\d+', '', remaining)
    
    remaining = remaining.strip()
    
    # 剩餘內容長度>=2，可能是地點
    return len(remaining) >= 2

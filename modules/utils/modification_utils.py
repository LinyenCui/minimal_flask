"""
統一的 modification_reason 管理工具
確保所有功能都使用相同的編號邏輯，不覆寫現有內容
"""

import re
import logging

logger = logging.getLogger(__name__)

def get_next_modification_number(current_reason):
    """獲取下一個修改編號"""
    if not current_reason or current_reason.strip() == '':
        return 1
    
    # 尋找現有的編號
    numbers = re.findall(r'\[(\d+)\]', current_reason)
    if not numbers:
        return 1
    
    # 返回最大編號 + 1
    return max(int(num) for num in numbers) + 1

def append_modification_reason(current_reason, new_reason, table_name="trips"):
    """
    統一的 modification_reason 追加邏輯
    
    Args:
        current_reason: 現有的 modification_reason
        new_reason: 新的修改原因
        table_name: 表名（用於日誌）
    
    Returns:
        完整的新 modification_reason
    """
    try:
        # 計算下一個編號
        next_number = get_next_modification_number(current_reason)
        
        # 構建新的原因部分
        new_reason_part = f"[{next_number}] {new_reason}"
        
        # 根據現有內容決定如何組合
        if not current_reason or current_reason.strip() == '':
            final_reason = new_reason_part
        else:
            final_reason = f"{current_reason}; {new_reason_part}"
        
        logger.info(f"修改 {table_name} modification_reason: '{current_reason}' → '{final_reason}'")
        
        return final_reason
        
    except Exception as e:
        logger.error(f"處理 modification_reason 時出錯: {e}")
        # 降級處理，至少確保新原因能被記錄
        if not current_reason or current_reason.strip() == '':
            return f"[1] {new_reason}"
        else:
            return f"{current_reason}; {new_reason}"

def build_modification_update_dict(current_reason, new_reason, user_display_name, table_name="trips"):
    """
    構建包含 modification_reason 的更新字典
    
    Args:
        current_reason: 現有的 modification_reason
        new_reason: 新的修改原因
        user_display_name: 修改者顯示名稱
        table_name: 表名（用於日誌）
    
    Returns:
        包含修改欄位的字典
        
    注意：只有 modification_reason 使用追加邏輯，其他欄位正常覆寫
    """
    from modules.utils.taiwan_time import get_taiwan_time
    
    return {
        "modification_reason": append_modification_reason(current_reason, new_reason, table_name),
        "modified_by": user_display_name,  # 正常覆寫
        "modification_time": get_taiwan_time()  # 正常覆寫
    }

def extract_reasons_for_display(modification_reason):
    """
    從 modification_reason 中提取所有編號原因用於顯示
    
    Args:
        modification_reason: 完整的 modification_reason 字符串
    
    Returns:
        格式化的顯示字符串
    """
    if not modification_reason:
        return None
    
    # 尋找所有編號原因
    numbered_reasons = re.findall(r'\[(\d+)\]\s*([^;]+)', modification_reason)
    
    if not numbered_reasons:
        # 如果沒有編號，直接返回原始內容
        return modification_reason
    
    # 格式化顯示
    display_parts = []
    for number, reason in numbered_reasons:
        display_parts.append(f"[{number}] {reason.strip()}")
    
    return "; ".join(display_parts) 
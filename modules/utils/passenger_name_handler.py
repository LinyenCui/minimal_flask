"""
乘客姓名處理模組
處理複合姓名的拆分和乘客資料管理
"""

import logging
import re
from sqlalchemy.sql import text as sql_text
from modules.models.base import db

logger = logging.getLogger(__name__)

def split_passenger_names(passenger_name):
    """
    拆分複合乘客姓名
    
    Args:
        passenger_name (str): 乘客姓名，可能包含分隔符（+、&、、）
        
    Returns:
        list: 拆分後的個別姓名列表
        
    Examples:
        "多多良+田中+永見" -> ["多多良", "田中", "永見"]
        "久保田&蔡永福" -> ["久保田", "蔡永福"]
        "二井、新戸、久保田" -> ["二井", "新戸", "久保田"]
        "張先生" -> ["張先生"]
    """
    if not passenger_name:
        return []
    
    # 使用正則表達式拆分，支援 +、&、、（中文逗號）分隔符
    names = re.split(r'[+&、]', passenger_name)
    
    # 去除空白並過濾空字串
    names = [name.strip() for name in names if name.strip()]
    
    logger.info(f"拆分乘客姓名 '{passenger_name}' -> {names}")
    return names

def check_passenger_exists(passenger_name):
    """
    檢查乘客是否已存在於customers表中
    
    Args:
        passenger_name (str): 乘客姓名
        
    Returns:
        dict: {"exists": bool, "customer_id": int or None, "customer_info": dict or None}
    """
    try:
        check_query = """
        SELECT id, name, short_name, category, address 
        FROM customers 
        WHERE name = :name OR short_name = :short_name
        """
        
        result = db.session.execute(sql_text(check_query), {
            "name": passenger_name,
            "short_name": passenger_name
        }).fetchone()
        
        if result:
            return {
                "exists": True,
                "customer_id": result[0],
                "customer_info": {
                    "id": result[0],
                    "name": result[1],
                    "short_name": result[2],
                    "category": result[3],
                    "address": result[4]
                }
            }
        else:
            return {"exists": False, "customer_id": None, "customer_info": None}
            
    except Exception as e:
        logger.error(f"檢查乘客是否存在時出錯: {e}")
        return {"exists": False, "customer_id": None, "customer_info": None}

def add_passenger_to_database(passenger_name, category="東洋"):
    """
    新增乘客到customers表
    
    Args:
        passenger_name (str): 乘客姓名
        category (str): 乘客類別，預設為"東洋"
        
    Returns:
        dict: {"success": bool, "customer_id": int or None, "message": str}
    """
    try:
        insert_passenger_query = """
        INSERT INTO customers (name, short_name, category, address) 
        VALUES (:name, :short_name, :category, :address)
        ON CONFLICT (short_name) DO NOTHING
        RETURNING id
        """
        
        result = db.session.execute(sql_text(insert_passenger_query), {
            "name": passenger_name,
            "short_name": passenger_name,
            "category": category,
            "address": "預約時未提供地址"
        })
        
        # 獲取新插入的ID
        new_row = result.fetchone()
        if new_row:
            customer_id = new_row[0]
            db.session.commit()
            logger.info(f"成功新增乘客: {passenger_name}, 類別: {category}, ID: {customer_id}")
            return {
                "success": True,
                "customer_id": customer_id,
                "message": f"成功新增乘客: {passenger_name}"
            }
        else:
            # 可能是因為ON CONFLICT DO NOTHING，乘客已存在
            logger.info(f"乘客 {passenger_name} 可能已存在，跳過新增")
            return {
                "success": True,
                "customer_id": None,
                "message": f"乘客 {passenger_name} 已存在"
            }
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"新增乘客時出錯: {e}")
        return {
            "success": False,
            "customer_id": None,
            "message": f"新增乘客失敗: {e}"
        }

def process_multiple_passengers(passenger_name, category="東洋"):
    """
    處理複合乘客姓名，拆分並確保每個乘客都在資料庫中
    
    Args:
        passenger_name (str): 可能包含多個乘客的姓名字串
        category (str): 乘客類別
        
    Returns:
        dict: {
            "success": bool,
            "individual_names": list,
            "existing_passengers": list,
            "new_passengers": list,
            "failed_passengers": list,
            "summary_message": str
        }
    """
    # 拆分姓名
    individual_names = split_passenger_names(passenger_name)
    
    if not individual_names:
        return {
            "success": False,
            "individual_names": [],
            "existing_passengers": [],
            "new_passengers": [],
            "failed_passengers": [],
            "summary_message": "無有效的乘客姓名"
        }
    
    existing_passengers = []
    new_passengers = []
    failed_passengers = []
    
    # 逐一處理每個乘客
    for name in individual_names:
        # 檢查是否已存在
        check_result = check_passenger_exists(name)
        
        if check_result["exists"]:
            existing_passengers.append({
                "name": name,
                "customer_id": check_result["customer_id"],
                "info": check_result["customer_info"]
            })
            logger.info(f"乘客已存在: {name} (ID: {check_result['customer_id']})")
        else:
            # 嘗試新增
            add_result = add_passenger_to_database(name, category)
            
            if add_result["success"]:
                new_passengers.append({
                    "name": name,
                    "customer_id": add_result["customer_id"],
                    "message": add_result["message"]
                })
            else:
                failed_passengers.append({
                    "name": name,
                    "error": add_result["message"]
                })
    
    # 生成摘要訊息
    summary_parts = []
    
    if existing_passengers:
        existing_names = [p["name"] for p in existing_passengers]
        summary_parts.append(f"已存在: {', '.join(existing_names)}")
    
    if new_passengers:
        new_names = [p["name"] for p in new_passengers]
        summary_parts.append(f"新增: {', '.join(new_names)}")
    
    if failed_passengers:
        failed_names = [p["name"] for p in failed_passengers]
        summary_parts.append(f"失敗: {', '.join(failed_names)}")
    
    summary_message = "; ".join(summary_parts) if summary_parts else "無處理結果"
    
    success = len(failed_passengers) == 0  # 只有當沒有失敗的乘客時才算成功
    
    logger.info(f"處理複合乘客姓名完成: {passenger_name} -> {summary_message}")
    
    return {
        "success": success,
        "individual_names": individual_names,
        "existing_passengers": existing_passengers,
        "new_passengers": new_passengers,
        "failed_passengers": failed_passengers,
        "summary_message": summary_message
    }

def get_passengers_display_text(passenger_name):
    """
    獲取乘客的顯示文字，自動處理複合姓名
    
    Args:
        passenger_name (str): 原始乘客姓名
        
    Returns:
        str: 格式化的顯示文字
        
    Examples:
        "多多良+田中+永見" -> "多多良、田中、永見 (3人)"
        "久保田&蔡永福" -> "久保田、蔡永福 (2人)"
        "張先生" -> "張先生"
    """
    individual_names = split_passenger_names(passenger_name)
    
    if len(individual_names) <= 1:
        return passenger_name
    else:
        return f"{'、'.join(individual_names)} ({len(individual_names)}人)"

# 測試函數
def test_passenger_name_handling():
    """測試乘客姓名處理功能"""
    test_cases = [
        "多多良+田中+永見",
        "久保田&蔡永福", 
        "張先生",
        "李小姐+王太太",
        "陳先生&林女士&黃醫師"
    ]
    
    print("🧪 測試乘客姓名拆分功能:")
    for case in test_cases:
        names = split_passenger_names(case)
        display = get_passengers_display_text(case)
        print(f"  輸入: '{case}'")
        print(f"  拆分: {names}")
        print(f"  顯示: '{display}'")
        print()

if __name__ == "__main__":
    test_passenger_name_handling() 
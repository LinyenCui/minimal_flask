#!/usr/bin/env python3
"""
系統知識庫 - 為AI提供完整的系統理解能力
包含資料庫結構、業務邏輯、三時間態映射、查詢範例
"""

# 完整的資料庫Schema
DATABASE_SCHEMA = {
    "trips": {
        "description": "當前進行中的班次表 (現在時間態)",
        "primary_key": "id",
        "columns": {
            "id": {"type": "integer", "description": "班次唯一編號"},
            "date": {"type": "date", "description": "班次日期 (YYYY-MM-DD)"},
            "time": {"type": "time", "description": "班次時間 (HH:MM)"},
            "start_point": {"type": "string", "description": "起點位置"},
            "end_point": {"type": "string", "description": "終點位置"},
            "category": {"type": "string", "description": "班次類別：東洋、診所、臨時"},
            "driver_id": {"type": "integer", "description": "司機編號"},
            "status": {"type": "string", "description": "班次狀態：待派、準備、已完成、取消"},
            "passenger_count": {"type": "integer", "description": "乘客人數"},
            "created_at": {"type": "timestamp", "description": "創建時間"}
        },
        "business_rules": {
            "status_flow": "待派 → 準備 → 已完成 (或取消)",
            "categories": ["東洋", "診所", "臨時"],
            "search_fields": ["driver_id", "category", "status", "date"]
        }
    },
    
    "completed_trips": {
        "description": "已完成班次表 (過去時間態)",
        "primary_key": "id", 
        "columns": {
            "id": {"type": "integer", "description": "記錄唯一編號"},
            "trip_id": {"type": "integer", "description": "關聯的原始班次ID"},
            "date": {"type": "date", "description": "完成日期"},
            "start_point": {"type": "string", "description": "起點位置"},
            "end_point": {"type": "string", "description": "終點位置"}, 
            "category": {"type": "string", "description": "班次類別：東洋、診所、臨時"},
            "driver_id": {"type": "integer", "description": "司機編號"},
            "meter_fare": {"type": "decimal", "description": "錶價金額"},
            "extra_fare": {"type": "decimal", "description": "加成金額"},
            "total_amount": {"type": "computed", "description": "總金額 = meter_fare + extra_fare"},
            "duration_minutes": {"type": "integer", "description": "行程時長(分鐘)"},
            "completed_at": {"type": "timestamp", "description": "完成時間"}
        },
        "business_rules": {
            "amount_calculation": "total_amount = meter_fare + extra_fare",
            "search_fields": ["driver_id", "category", "date", "amount_range"],
            "date_formats": ["今天", "昨天", "本週", "上週", "本月"]
        }
    },
    
    "fixed_schedules": {
        "description": "固定班次模板表 (未來時間態)",
        "primary_key": "id",
        "columns": {
            "id": {"type": "integer", "description": "模板編號"},
            "departure_time": {"type": "time", "description": "出發時間"},
            "start_point": {"type": "string", "description": "起點位置"},
            "end_point": {"type": "string", "description": "終點位置"},
            "category": {"type": "string", "description": "班次類別：東洋、診所、臨時"},
            "driver_id": {"type": "integer", "description": "預設司機編號"},
            "status": {"type": "string", "description": "模板狀態：啟用、停用、請假"},
            "weekday": {"type": "integer", "description": "星期幾 (1-7)"},
            "is_active": {"type": "boolean", "description": "是否啟用"}
        },
        "business_rules": {
            "import_logic": "依據週次匯入到trips表",
            "leave_handling": "可設定請假狀態",
            "search_fields": ["driver_id", "category", "weekday", "status"]
        }
    },
    
    "drivers": {
        "description": "司機基本資料表",
        "primary_key": "id",
        "columns": {
            "id": {"type": "integer", "description": "司機編號"},
            "name": {"type": "string", "description": "司機姓名"},
            "phone": {"type": "string", "description": "聯絡電話"},
            "is_active": {"type": "boolean", "description": "是否在職"},
            "created_at": {"type": "timestamp", "description": "建檔時間"}
        }
    }
}

# 三時間態架構映射
TIME_PERSPECTIVES = {
    "past": {
        "description": "過去時間態 - 成品倉庫區域",
        "production_line_concept": "已完成的產品存放在成品倉庫，記錄車資、收入、統計資料",
        "keywords": ["昨天", "前天", "上週", "上個月", "去年", "已完成", "歷史", "統計", "車資", "收入", "績效", "分析"],
        "primary_table": "completed_trips",
        "related_tables": ["drivers"],
        "typical_queries": [
            "車資查詢", "收入統計", "效率分析", "歷史記錄", "績效評估"
        ],
        "operations": ["查詢", "分析", "統計", "報表"],
        "example_commands": [
            "昨天司機533的車資",
            "上週診所班次收入",
            "查已完成 金額>200"
        ],
        "business_logic": "執行時間到達後，班次自動從trips表掉入completed_trips表"
    },
    
    "present": {
        "description": "現在時間態 - 生產線主體區域", 
        "production_line_concept": "產品正在生產線上流動執行，工作人員可進行品質控制和干預",
        "keywords": ["今天", "明天", "現在", "當前", "目前", "待派", "準備", "進行中", "狀態", "司機5386所有班次"],
        "primary_table": "trips",
        "related_tables": ["drivers", "customers"],
        "typical_queries": [
            "班次查詢", "司機指派", "狀態更新", "當日安排", "生產線監控"
        ],
        "operations": ["查詢", "指派", "修改", "更新", "監控"],
        "example_commands": [
            "今天東洋班次",
            "明天司機5386所有班次",
            "指派司機 1585 5386",
            "找狀態為待派的班次"
        ],
        "business_logic": "包含今天、明天等已匯入到生產線上的所有班次，無論執行日期",
        "intervention_mechanisms": {
            "請假": "標記瑕疵但讓產品繼續跑完流程(狀態保持準備，用passenger_leave_reason記錄)",
            "取消_衝突": "直接從生產線拿掉，防止掉入已完成",
            "30分鐘前修改": "最後調整機會，防止運行中的班次被修改"
        }
    },
    
    "future": {
        "description": "未來時間態 - 整備區域",
        "production_line_concept": "為生產線準備原料和模板，客戶資料和固定班次模板的管理", 
        "keywords": ["匯入", "安排", "預定", "固定班次", "模板", "準備", "規劃", "設定"],
        "primary_table": "fixed_schedules", 
        "related_tables": ["customers", "trips"],
        "typical_queries": [
            "班次匯入", "固定排程", "模板管理", "原料準備"
        ],
        "operations": ["匯入", "安排", "規劃", "預約", "設定"],
        "example_commands": [
            "匯入固定班次 本週",
            "設定客戶資料",
            "管理班次模板"
        ],
        "business_logic": "透過匯入操作將fixed_schedules的模板轉換為trips表中的實際班次"
    }
}

# 可用功能清單
AVAILABLE_FUNCTIONS = {
    "query_functions": {
        "東洋班次": {
            "description": "查詢東洋/臨時類別的未完成班次",
            "syntax": "東洋班次 [日期]",
            "parameters": ["date (optional)"],
            "examples": ["東洋班次", "東洋班次 今天", "東洋班次 明天"],
            "target_table": "trips",
            "conditions": "category IN ('東洋', '臨時')"
        },
        
        "診所班次": {
            "description": "查詢診所類別的班次",
            "syntax": "診所班次 [日期]", 
            "parameters": ["date (optional)"],
            "examples": ["診所班次", "診所班次 今天", "診所班次 2025-07-15"],
            "target_table": "trips",
            "conditions": "category = '診所'"
        },
        
        "班次詳情": {
            "description": "查詢特定班次的詳細信息",
            "syntax": "班次詳情 [班次ID]",
            "parameters": ["trip_id (required)"],
            "examples": ["班次詳情 1585", "班次詳情 1996"],
            "target_table": "trips",
            "conditions": "id = {trip_id}"
        },
        
        "查已完成": {
            "description": "查詢已完成班次，支援複雜條件",
            "syntax": "查已完成 [條件]",
            "parameters": ["conditions (optional)"],
            "examples": [
                "查已完成",
                "查已完成 昨天",
                "查已完成 司機533",
                "查已完成 金額>200"
            ],
            "target_table": "completed_trips",
            "advanced_conditions": {
                "amount_operators": [">", "<", ">=", "<=", "="],
                "date_expressions": ["今天", "昨天", "本週", "上週"],
                "driver_format": "司機{number}",
                "category_filter": ["診所", "東洋", "臨時"]
            }
        }
    },
    
    "management_functions": {
        "指派司機": {
            "description": "為班次指派司機",
            "syntax": "指派司機 [班次ID] [司機編號]",
            "parameters": ["trip_id (required)", "driver_id (required)"],
            "examples": ["指派司機 1585 5386", "指派司機 1996 533"],
            "target_table": "trips",
            "operation": "UPDATE trips SET driver_id = {driver_id} WHERE id = {trip_id}"
        },
        
        "記錄車資": {
            "description": "記錄已完成班次的車資",
            "syntax": "記錄車資 [班次ID] [錶價] [加成]",
            "parameters": ["trip_id (required)", "meter_fare (required)", "extra_fare (optional)"],
            "examples": ["記錄車資 1585 400 80", "記錄車資 1996 350"],
            "target_table": "completed_trips",
            "operation": "INSERT/UPDATE completed_trips"
        },
        
        "匯入固定班次": {
            "description": "從固定班次模板匯入到實際班次",
            "syntax": "匯入固定班次 [週次]",
            "parameters": ["week_identifier (required)"],
            "examples": ["匯入固定班次 本週", "匯入固定班次 下週", "匯入固定班次 週次1"],
            "target_table": "fixed_schedules -> trips",
            "operation": "Copy from fixed_schedules to trips"
        }
    }
}

# 條件解析規則
CONDITION_PARSING_RULES = {
    "amount_conditions": {
        "patterns": {
            "金額大於": {"operator": ">", "field": "(meter_fare + extra_fare)"},
            "金額小於": {"operator": "<", "field": "(meter_fare + extra_fare)"},
            "金額等於": {"operator": "=", "field": "(meter_fare + extra_fare)"},
            "錶價大於": {"operator": ">", "field": "meter_fare"},
            "加成大於": {"operator": ">", "field": "extra_fare"},
        },
        "number_extraction": r"(\d+)",
        "sql_template": "{field} {operator} {value}"
    },
    
    "status_conditions": {
        "patterns": {
            "狀態為待派": {"field": "status", "value": "待派"},
            "狀態為準備": {"field": "status", "value": "準備"}, 
            "狀態為已完成": {"field": "status", "value": "已完成"},
            "待派的班次": {"field": "status", "value": "待派"},
            "未完成": {"field": "status", "value": "待派,準備", "operator": "IN"}
        },
        "sql_template": "{field} = '{value}'"
    },
    
    "date_conditions": {
        "patterns": {
            "今天": "CURRENT_DATE",
            "昨天": "CURRENT_DATE - INTERVAL '1 day'",
            "明天": "CURRENT_DATE + INTERVAL '1 day'",
            "本週": "CURRENT_DATE BETWEEN date_trunc('week', CURRENT_DATE) AND date_trunc('week', CURRENT_DATE) + INTERVAL '6 days'",
            "上週": "CURRENT_DATE BETWEEN date_trunc('week', CURRENT_DATE) - INTERVAL '7 days' AND date_trunc('week', CURRENT_DATE) - INTERVAL '1 day'"
        },
        "sql_template": "date = {date_expression}"
    },
    
    "driver_conditions": {
        "pattern": r"司機(\d+)",
        "field": "driver_id",
        "sql_template": "driver_id = {driver_id}"
    },
    
    "category_conditions": {
        "patterns": {
            "診所": {"field": "category", "value": "診所"},
            "東洋": {"field": "category", "value": "東洋"}, 
            "臨時": {"field": "category", "value": "臨時"}
        },
        "sql_template": "category = '{value}'"
    }
}

# 查詢範例庫
QUERY_EXAMPLES = {
    "simple_queries": [
        {
            "input": "今天診所班次",
            "analysis": "查詢今天的診所類別班次",
            "table": "trips",
            "conditions": "date = CURRENT_DATE AND category = '診所'",
            "command": "診所班次 今天"
        },
        {
            "input": "東洋班次",
            "analysis": "查詢東洋類別的班次",
            "table": "trips", 
            "conditions": "category IN ('東洋', '臨時')",
            "command": "東洋班次"
        }
    ],
    
    "complex_queries": [
        {
            "input": "今天金額大於200的診所班次",
            "analysis": "查詢今天診所班次中總金額超過200的記錄",
            "table": "completed_trips",
            "conditions": "date = CURRENT_DATE AND category = '診所' AND (meter_fare + extra_fare) > 200",
            "command": "查已完成 今天 診所 金額>200"
        },
        {
            "input": "找狀態為待派的班次",
            "analysis": "查詢狀態為待派的班次",
            "table": "trips",
            "conditions": "status = '待派'",
            "command": "查詢班次 狀態=待派"
        },
        {
            "input": "司機533昨天的車資",
            "analysis": "查詢司機533昨天的已完成班次車資",
            "table": "completed_trips",
            "conditions": "driver_id = 533 AND date = CURRENT_DATE - INTERVAL '1 day'",
            "command": "查已完成 昨天 司機533"
        }
    ],
    
    "management_examples": [
        {
            "input": "指派司機5386到班次1585",
            "analysis": "為班次1585指派司機5386",
            "operation": "UPDATE trips SET driver_id = 5386 WHERE id = 1585",
            "command": "指派司機 1585 5386"
        }
    ]
}

def get_system_knowledge():
    """獲取完整的系統知識庫"""
    return {
        "database_schema": DATABASE_SCHEMA,
        "time_perspectives": TIME_PERSPECTIVES,
        "available_functions": AVAILABLE_FUNCTIONS,
        "condition_parsing": CONDITION_PARSING_RULES,
        "query_examples": QUERY_EXAMPLES
    }

def get_table_info(table_name: str):
    """獲取特定表的詳細信息"""
    return DATABASE_SCHEMA.get(table_name, {})

def get_function_info(function_name: str):
    """獲取特定功能的詳細信息"""
    for category in AVAILABLE_FUNCTIONS.values():
        if function_name in category:
            return category[function_name]
    return None

def analyze_time_perspective(user_input: str):
    """分析用戶輸入的時間態度"""
    for perspective, info in TIME_PERSPECTIVES.items():
        for keyword in info["keywords"]:
            if keyword in user_input:
                return perspective, info
    return "present", TIME_PERSPECTIVES["present"]  # 預設為現在時間態 
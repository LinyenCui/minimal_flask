"""
系統知識庫 - 三時間態分類規則和功能映射
包含完整的資料庫結構、業務邏輯和智能路由規則
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json

class TableTimeMapping(Enum):
    """表與時間態的映射"""
    PAST = "completed_trips"
    PRESENT = "trips" 
    FUTURE = "fixed_schedules"

@dataclass
class TableSchema:
    """資料表結構定義"""
    table_name: str
    description: str
    time_perspective: str
    columns: Dict[str, str]
    relationships: List[str]
    business_rules: List[str]
    query_patterns: List[str]

@dataclass
class BusinessFunction:
    """業務功能定義"""
    function_name: str
    description: str
    time_perspective: str
    target_table: str
    operation_type: str
    required_params: List[str]
    optional_params: List[str]

class SystemKnowledgeBase:
    """系統知識庫核心類"""
    
    def __init__(self):
        """初始化知識庫"""
        self.database_schemas = self._init_database_schemas()
        self.business_functions = self._init_business_functions()
        self.time_classification_rules = self._init_time_classification_rules()
        self.operation_classification_rules = self._init_operation_classification_rules()
        self.natural_language_patterns = self._init_natural_language_patterns()
        self.business_workflows = self._init_business_workflows()
    
    def _init_database_schemas(self) -> Dict[str, TableSchema]:
        """初始化資料庫結構知識"""
        schemas = {}
        
        # trips 表 - 現在時間態
        schemas["trips"] = TableSchema(
            table_name="trips",
            description="當前進行中的班次記錄表，管理待派和準備中的班次",
            time_perspective="present",
            columns={
                "trip_id": "班次ID (主鍵，自動生成)",
                "fixed_trip_id": "關聯的固定班次ID (外鍵)",
                "week_number": "週次編號",
                "date": "班次日期",
                "time": "班次時間",
                "start_point": "起點 (關聯customers.short_name)",
                "via_point": "經點 (關聯customers.short_name)",
                "end_point": "終點 (關聯customers.short_name)",
                "meter_fare": "錶價",
                "extra_fare": "加成費用",
                "actual_fare": "實際費用 (計算欄位: meter_fare + extra_fare)",
                "category": "班次類別 (東洋/診所/臨時等)",
                "driver_id": "司機ID (關聯drivers.id)",
                "status": "班次狀態 (待派/準備/已完成)",
                "unique_code": "唯一識別碼",
                "trip_type": "班次類型 (fixed/temp)",
                "passenger_name": "乘客姓名",
                "passenger_leave_reason": "乘客請假原因",
                "modified_by": "修改者",
                "modification_reason": "修改原因",
                "modification_time": "修改時間"
            },
            relationships=[
                "fixed_trip_id -> fixed_schedules.id",
                "start_point -> customers.short_name",
                "via_point -> customers.short_name", 
                "end_point -> customers.short_name",
                "driver_id -> drivers.id"
            ],
            business_rules=[
                "狀態流程: 待派 → 準備 → 已完成",
                "完成後自動寫入completed_trips表",
                "請假班次顯示為「請假（原因）」",
                "actual_fare = meter_fare + extra_fare",
                "category預設為「未分類」，匯入時設定"
            ],
            query_patterns=[
                "今天的東洋班次",
                "司機[ID]的當前班次",
                "待派的班次",
                "準備中的班次"
            ]
        )
        
        # completed_trips 表 - 過去時間態
        schemas["completed_trips"] = TableSchema(
            table_name="completed_trips",
            description="已完成班次記錄表，用於歷史查詢、報表和車資分析",
            time_perspective="past",
            columns={
                "id": "記錄ID (主鍵，自動生成)",
                "date": "班次日期",
                "start_point": "起點 (關聯customers.short_name)",
                "via_point": "經點 (關聯customers.short_name)",
                "end_point": "終點 (關聯customers.short_name)", 
                "meter_fare": "錶價",
                "extra_fare": "加成費用",
                "actual_fare": "實際費用 (計算欄位: meter_fare + extra_fare)",
                "category": "班次類別 (東洋/診所/臨時等)",
                "driver_id": "司機ID (關聯drivers.id)",
                "remarks": "備註說明",
                "created_at": "記錄建立時間",
                "unique_code": "唯一識別碼",
                "trip_type": "班次類型 (fixed/temp)",
                "status": "記錄狀態",
                "passenger_name": "乘客姓名",
                "passenger_leave_reason": "乘客請假原因",
                "modified_by": "修改者",
                "modification_reason": "修改原因",
                "modification_time": "修改時間"
            },
            relationships=[
                "start_point -> customers.short_name",
                "via_point -> customers.short_name",
                "end_point -> customers.short_name",
                "driver_id -> drivers.id"
            ],
            business_rules=[
                "只能查詢，不可修改歷史記錄",
                "支援車資修改和備註更新",
                "按日期和司機分組統計",
                "支援模糊搜尋和智能匹配",
                "提供效率分析和報表功能"
            ],
            query_patterns=[
                "昨天司機[ID]的車資",
                "上週的東洋班次",
                "本月司機效率統計",
                "歷史班次搜尋"
            ]
        )
        
        # fixed_schedules 表 - 未來時間態
        schemas["fixed_schedules"] = TableSchema(
            table_name="fixed_schedules",
            description="固定班次模板表，定義週期性班次安排和匯入規則",
            time_perspective="future",
            columns={
                "id": "固定班次ID (主鍵)",
                "route_number": "路線編號 (包含星期信息)",
                "departure_time": "出發時間",
                "start_point": "起點",
                "via_point": "經點", 
                "end_point": "終點",
                "base_fare": "基本車資",
                "surcharge": "加成費用",
                "total_fare": "總費用 (計算欄位: base_fare + surcharge)",
                "category": "班次類別 (東洋/診所等)",
                "driver_id": "司機ID",
                "direction": "方向 (上行/下行)",
                "status": "狀態 (準備/請假/停用)",
                "note": "說明 (請假原因等)",
                "modified_by": "修改者",
                "modification_time": "修改時間"
            },
            relationships=[
                "被trips表引用 (fixed_trip_id)",
                "driver_id對應司機信息"
            ],
            business_rules=[
                "匯入時創建對應的trips記錄",
                "支援批量請假和恢復",
                "狀態控制匯入行為",
                "請假不影響原始模板",
                "修改記錄追蹤功能"
            ],
            query_patterns=[
                "明天要匯入的固定班次",
                "固定班次請假設定",
                "週次班次模板查詢",
                "司機固定班次安排"
            ]
        )
        
        # customers 表 - 輔助表
        schemas["customers"] = TableSchema(
            table_name="customers",
            description="客戶地點信息表，提供起點終點的詳細信息",
            time_perspective="static",
            columns={
                "id": "客戶ID (主鍵)",
                "name": "客戶全名",
                "address": "詳細地址",
                "short_name": "簡稱 (用於班次記錄)",
                "category": "客戶類別",
                "remarks": "備註",
                "contact_phone": "聯絡電話"
            },
            relationships=[
                "被trips表引用 (start_point, via_point, end_point)",
                "被completed_trips表引用 (start_point, via_point, end_point)"
            ],
            business_rules=[
                "short_name必須唯一",
                "常用地點: 高鐵站、東洋、診所",
                "支援地點別名和模糊匹配"
            ],
            query_patterns=[
                "地點信息查詢",
                "客戶聯絡方式",
                "地點分類統計"
            ]
        )
        
        # drivers 表 - 輔助表
        schemas["drivers"] = TableSchema(
            table_name="drivers",
            description="司機信息表，管理司機基本資料和車輛信息",
            time_perspective="static",
            columns={
                "id": "司機ID (主鍵)",
                "name": "司機姓名",
                "plate_number": "車牌號碼",
                "car_brand": "車輛品牌",
                "car_model": "車型"
            },
            relationships=[
                "被trips表引用 (driver_id)",
                "被completed_trips表引用 (driver_id)",
                "被fixed_schedules引用 (driver_id)"
            ],
            business_rules=[
                "司機ID唯一識別",
                "支援按姓名或ID查詢",
                "車輛信息可選填"
            ],
            query_patterns=[
                "司機基本信息",
                "司機班次統計",
                "車輛管理"
            ]
        )
        
        return schemas
    
    def _init_business_functions(self) -> Dict[str, BusinessFunction]:
        """初始化業務功能映射"""
        functions = {}
        
        # 過去時間態功能
        functions["query_completed_trips"] = BusinessFunction(
            function_name="query_completed_trips",
            description="查詢已完成班次記錄",
            time_perspective="past",
            target_table="completed_trips",
            operation_type="query",
            required_params=[],
            optional_params=["driver_id", "date", "category", "start_point", "end_point"]
        )
        
        functions["analyze_driver_efficiency"] = BusinessFunction(
            function_name="analyze_driver_efficiency", 
            description="分析司機效率和收入統計",
            time_perspective="past",
            target_table="completed_trips",
            operation_type="query",
            required_params=["time_range"],
            optional_params=["driver_id", "category"]
        )
        
        functions["modify_fare"] = BusinessFunction(
            function_name="modify_fare",
            description="修改已完成班次的車資信息",
            time_perspective="past", 
            target_table="completed_trips",
            operation_type="modify",
            required_params=["trip_id", "new_fare"],
            optional_params=["reason", "modifier"]
        )
        
        # 現在時間態功能
        functions["query_current_trips"] = BusinessFunction(
            function_name="query_current_trips",
            description="查詢當前進行中的班次",
            time_perspective="present",
            target_table="trips",
            operation_type="query",
            required_params=[],
            optional_params=["category", "status", "driver_id", "date"]
        )
        
        functions["assign_driver"] = BusinessFunction(
            function_name="assign_driver",
            description="指派司機到班次",
            time_perspective="present",
            target_table="trips", 
            operation_type="modify",
            required_params=["trip_id", "driver_id"],
            optional_params=["reason"]
        )
        
        functions["update_trip_status"] = BusinessFunction(
            function_name="update_trip_status",
            description="更新班次狀態",
            time_perspective="present",
            target_table="trips",
            operation_type="modify", 
            required_params=["trip_id", "new_status"],
            optional_params=["reason"]
        )
        
        functions["passenger_leave"] = BusinessFunction(
            function_name="passenger_leave",
            description="記錄乘客請假",
            time_perspective="present",
            target_table="trips",
            operation_type="modify",
            required_params=["trip_id", "leave_reason"],
            optional_params=["passenger_name"]
        )
        
        # 未來時間態功能
        functions["query_fixed_schedules"] = BusinessFunction(
            function_name="query_fixed_schedules",
            description="查詢固定班次模板",
            time_perspective="future",
            target_table="fixed_schedules",
            operation_type="query",
            required_params=[],
            optional_params=["category", "status", "driver_id"]
        )
        
        functions["import_schedules"] = BusinessFunction(
            function_name="import_schedules",
            description="匯入固定班次到trips表",
            time_perspective="future",
            target_table="fixed_schedules",
            operation_type="create",
            required_params=["week_number", "target_date"],
            optional_params=["category_filter", "driver_filter"]
        )
        
        functions["schedule_leave"] = BusinessFunction(
            function_name="schedule_leave",
            description="設定固定班次請假",
            time_perspective="future",
            target_table="fixed_schedules",
            operation_type="modify",
            required_params=["schedule_id", "leave_reason"],
            optional_params=["leave_period"]
        )
        
        # 跨時間態功能
        functions["generate_report"] = BusinessFunction(
            function_name="generate_report",
            description="生成綜合報表",
            time_perspective="cross_time",
            target_table="multiple",
            operation_type="query",
            required_params=["report_type", "date_range"],
            optional_params=["driver_filter", "category_filter"]
        )
        
        return functions
    
    def _init_time_classification_rules(self) -> Dict[str, Any]:
        """初始化時間態度分類規則"""
        return {
            "past": {
                "keywords": [
                    "昨天", "昨日", "前天", "上週", "上個月", "上月", "去年",
                    "已完成", "歷史", "過去", "之前", "早些時候", "先前",
                    "記錄", "統計", "報表", "分析", "回顧", "查閱"
                ],
                "time_patterns": [
                    r"(\d{4}-\d{2}-\d{2})",  # 具體日期
                    r"([1-9]\d*)天前",        # N天前
                    r"([1-9]\d*)週前",        # N週前  
                    r"([1-9]\d*)月前",        # N月前
                    r"上個?[週月年]",         # 上週/上月/上年
                    r"去年"
                ],
                "indicators": [
                    "車資是多少", "收入統計", "效率分析", "歷史查詢",
                    "已經完成", "記錄顯示", "報表生成"
                ],
                "default_table": "completed_trips",
                "confidence_boost": 0.2
            },
            "present": {
                "keywords": [
                    "今天", "今日", "現在", "當前", "目前", "這個", "正在",
                    "待派", "準備", "進行中", "最新", "即時", "狀態"
                ],
                "time_patterns": [
                    r"今[天日]",
                    r"現在", 
                    r"當前",
                    r"這[個次]",
                    r"正在"
                ],
                "indicators": [
                    "班次狀態", "指派司機", "修改班次", "當前進度",
                    "待派班次", "準備中", "進行中的"
                ],
                "default_table": "trips",
                "confidence_boost": 0.1
            },
            "future": {
                "keywords": [
                    "明天", "明日", "後天", "下週", "下個月", "下月", "明年",
                    "未來", "即將", "安排", "匯入", "預定", "計劃", "排程",
                    "固定班次", "模板", "週次"
                ],
                "time_patterns": [
                    r"明[天日]",
                    r"後天", 
                    r"下[週月年]",
                    r"([1-9]\d*)天後",
                    r"([1-9]\d*)週後",
                    r"週次\d+"
                ],
                "indicators": [
                    "匯入固定班次", "安排班次", "預定班次", "計劃執行",
                    "固定模板", "週次安排", "排程設定"
                ],
                "default_table": "fixed_schedules", 
                "confidence_boost": 0.3
            }
        }
    
    def _init_operation_classification_rules(self) -> Dict[str, Any]:
        """初始化操作類型分類規則"""
        return {
            "query": {
                "keywords": [
                    "查詢", "查", "看", "顯示", "搜尋", "找", "列出", "檢視",
                    "統計", "分析", "報表", "總結", "彙總", "計算"
                ],
                "patterns": [
                    r".*有哪些.*", r".*是什麼.*", r".*怎麼樣.*",
                    r"查詢.*", r"顯示.*", r"列出.*",
                    r".*的狀態", r".*的信息", r".*的記錄"
                ],
                "confidence_boost": 0.1
            },
            "modify": {
                "keywords": [
                    "修改", "改", "更新", "調整", "設定", "變更", "編輯",
                    "指派", "分配", "安排", "調度"
                ],
                "patterns": [
                    r"修改.*", r"改.*", r"調整.*",
                    r"設定.*", r"指派.*", r"安排.*",
                    r".*改成.*", r".*調整為.*", r".*設為.*"
                ],
                "confidence_boost": 0.2
            },
            "create": {
                "keywords": [
                    "創建", "新增", "建立", "匯入", "添加", "預約",
                    "安排", "制定", "生成", "產生"
                ],
                "patterns": [
                    r"匯入.*", r"新增.*", r"創建.*",
                    r"建立.*", r"添加.*", r"預約.*",
                    r"安排.*班次"
                ],
                "confidence_boost": 0.25
            },
            "delete": {
                "keywords": [
                    "刪除", "移除", "清除", "取消", "廢棄", "撤銷"
                ],
                "patterns": [
                    r"刪除.*", r"移除.*", r"取消.*",
                    r"清除.*", r"廢棄.*"
                ],
                "confidence_boost": 0.3
            }
        }
    
    def _init_natural_language_patterns(self) -> Dict[str, Any]:
        """初始化自然語言模式"""
        return {
            "entity_patterns": {
                "driver_id": [
                    r"司機(\d+)", r"司機ID(\d+)", r"(\d+)號司機", 
                    r"司機\s*(\d+)", r"driver\s*(\d+)"
                ],
                "trip_id": [
                    r"班次#?(\d+)", r"#(\d+)", r"trip\s*(\d+)",
                    r"班次ID(\d+)", r"班次編號(\d+)"
                ],
                "date": [
                    r"(\d{4}-\d{2}-\d{2})", r"(\d{2}-\d{2})", 
                    r"(\d{1,2})月(\d{1,2})日", r"(\d{1,2})/(\d{1,2})"
                ],
                "category": [
                    r"(東洋|診所|臨時)班次", r"(東洋|診所|臨時)",
                    r"類別.*?(東洋|診所|臨時)"
                ],
                "location": [
                    r"(高鐵站|東洋|診所|火車站|機場)",
                    r"從(.+)到(.+)", r"起點(.+)", r"終點(.+)"
                ],
                "fare": [
                    r"車資(\d+)", r"費用(\d+)", r"(\d+)元",
                    r"錶價(\d+)", r"加成(\d+)"
                ]
            },
            "intent_patterns": {
                "efficiency_analysis": [
                    r".*效率.*分析.*", r".*統計.*效率.*",
                    r".*司機.*表現.*", r".*收入.*統計.*"
                ],
                "fare_modification": [
                    r".*修改.*車資.*", r".*調整.*費用.*",
                    r".*車資.*改.*", r".*費用.*設.*"
                ],
                "driver_assignment": [
                    r".*指派.*司機.*", r".*安排.*司機.*",
                    r".*司機.*指派.*", r".*分配.*司機.*"
                ],
                "schedule_import": [
                    r".*匯入.*固定班次.*", r".*固定班次.*匯入.*",
                    r".*導入.*班次.*", r".*班次.*安排.*"
                ],
                "leave_management": [
                    r".*請假.*", r".*休假.*", r".*停班.*",
                    r".*暫停.*班次.*", r".*取消.*班次.*"
                ]
            },
            "context_clues": {
                "urgency": ["緊急", "立即", "馬上", "儘快", "urgent"],
                "uncertainty": ["可能", "或許", "也許", "不確定", "看看"],
                "politeness": ["請", "幫忙", "麻煩", "謝謝", "please"],
                "comparison": ["比較", "對比", "差異", "不同", "vs"]
            }
        }
    
    def _init_business_workflows(self) -> Dict[str, Any]:
        """初始化業務流程知識"""
        return {
            "trip_lifecycle": {
                "stages": ["匯入", "待派", "準備", "執行", "完成"],
                "transitions": {
                    "匯入": ["待派"],
                    "待派": ["準備", "取消"],
                    "準備": ["執行", "請假"], 
                    "執行": ["完成"],
                    "完成": []
                },
                "rules": [
                    "fixed_schedules匯入生成trips記錄",
                    "trips完成後自動轉入completed_trips",
                    "請假班次保留在trips但標記請假原因",
                    "狀態轉換需要記錄修改者和原因"
                ]
            },
            "fare_calculation": {
                "formula": "actual_fare = meter_fare + extra_fare",
                "rules": [
                    "錶價為基本費用",
                    "加成根據距離和時間計算",
                    "特殊情況可手動調整",
                    "修改記錄需要留存"
                ]
            },
            "driver_management": {
                "assignment_rules": [
                    "司機ID必須存在於drivers表",
                    "一個司機可以有多個班次",
                    "指派需要檢查衝突",
                    "修改需要記錄原因"
                ],
                "performance_metrics": [
                    "完成班次數量",
                    "總收入統計", 
                    "平均效率",
                    "準時率"
                ]
            },
            "leave_management": {
                "types": ["臨時請假", "長期請假", "固定班次請假"],
                "rules": [
                    "乘客請假：記錄在passenger_leave_reason",
                    "司機請假：修改班次狀態和說明",
                    "固定班次請假：修改模板狀態",
                    "請假不刪除記錄，只標記狀態"
                ]
            }
        }
    
    def get_schema_for_table(self, table_name: str) -> Optional[TableSchema]:
        """獲取指定表的結構信息"""
        return self.database_schemas.get(table_name)
    
    def get_functions_by_time_perspective(self, time_perspective: str) -> List[BusinessFunction]:
        """根據時間態度獲取相關功能"""
        return [
            func for func in self.business_functions.values()
            if func.time_perspective == time_perspective or func.time_perspective == "cross_time"
        ]
    
    def classify_time_perspective(self, text: str) -> Dict[str, float]:
        """分析文本的時間態度傾向"""
        scores = {"past": 0.0, "present": 0.0, "future": 0.0}
        
        text_lower = text.lower()
        
        for time_type, rules in self.time_classification_rules.items():
            # 關鍵詞匹配
            keyword_matches = sum(1 for keyword in rules["keywords"] if keyword in text_lower)
            scores[time_type] += keyword_matches * 0.3
            
            # 模式匹配
            import re
            for pattern in rules["time_patterns"]:
                if re.search(pattern, text):
                    scores[time_type] += 0.4
            
            # 指示詞匹配
            indicator_matches = sum(1 for indicator in rules["indicators"] if indicator in text_lower)
            scores[time_type] += indicator_matches * 0.2
            
            # 信心度加成
            if scores[time_type] > 0:
                scores[time_type] += rules["confidence_boost"]
        
        # 正規化分數
        total_score = sum(scores.values())
        if total_score > 0:
            scores = {k: v/total_score for k, v in scores.items()}
        else:
            scores["present"] = 1.0  # 預設為現在時間態
        
        return scores
    
    def classify_operation_type(self, text: str) -> Dict[str, float]:
        """分析文本的操作類型傾向"""
        scores = {"query": 0.0, "modify": 0.0, "create": 0.0, "delete": 0.0}
        
        text_lower = text.lower()
        
        for op_type, rules in self.operation_classification_rules.items():
            # 關鍵詞匹配
            keyword_matches = sum(1 for keyword in rules["keywords"] if keyword in text_lower)
            scores[op_type] += keyword_matches * 0.4
            
            # 模式匹配
            import re
            for pattern in rules["patterns"]:
                if re.search(pattern, text):
                    scores[op_type] += 0.5
            
            # 信心度加成
            if scores[op_type] > 0:
                scores[op_type] += rules["confidence_boost"]
        
        # 正規化分數
        total_score = sum(scores.values())
        if total_score > 0:
            scores = {k: v/total_score for k, v in scores.items()}
        else:
            scores["query"] = 1.0  # 預設為查詢操作
        
        return scores
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """從文本中提取業務實體"""
        entities = {}
        import re
        
        for entity_type, patterns in self.natural_language_patterns["entity_patterns"].items():
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    if entity_type == "date" and len(matches[0]) == 2:
                        # 處理月日格式
                        entities[entity_type] = f"{matches[0][0]}-{matches[0][1]}"
                    else:
                        entities[entity_type] = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    break
        
        return entities
    
    def get_suggested_function(self, time_perspective: str, operation_type: str, entities: Dict[str, Any]) -> Optional[str]:
        """根據時間態度和操作類型建議功能"""
        relevant_functions = self.get_functions_by_time_perspective(time_perspective)
        
        for func in relevant_functions:
            if func.operation_type == operation_type:
                # 檢查是否有必要參數
                has_required_params = all(
                    param in entities or param in ["time_range", "report_type", "new_status", "new_fare"]
                    for param in func.required_params
                )
                
                if has_required_params or not func.required_params:
                    return func.function_name
        
        # 如果沒有完全匹配，返回最相關的功能
        if relevant_functions:
            return relevant_functions[0].function_name
        
        return None
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """獲取知識庫摘要"""
        return {
            "database_tables": list(self.database_schemas.keys()),
            "business_functions": list(self.business_functions.keys()),
            "time_perspectives": list(self.time_classification_rules.keys()),
            "operation_types": list(self.operation_classification_rules.keys()),
            "total_schemas": len(self.database_schemas),
            "total_functions": len(self.business_functions)
        }
    
    def export_knowledge_json(self) -> str:
        """匯出知識庫為JSON格式"""
        knowledge_data = {
            "database_schemas": {
                name: {
                    "table_name": schema.table_name,
                    "description": schema.description,
                    "time_perspective": schema.time_perspective,
                    "columns": schema.columns,
                    "relationships": schema.relationships,
                    "business_rules": schema.business_rules,
                    "query_patterns": schema.query_patterns
                } for name, schema in self.database_schemas.items()
            },
            "business_functions": {
                name: {
                    "function_name": func.function_name,
                    "description": func.description,
                    "time_perspective": func.time_perspective,
                    "target_table": func.target_table,
                    "operation_type": func.operation_type,
                    "required_params": func.required_params,
                    "optional_params": func.optional_params
                } for name, func in self.business_functions.items()
            },
            "classification_rules": {
                "time_classification": self.time_classification_rules,
                "operation_classification": self.operation_classification_rules,
                "natural_language_patterns": self.natural_language_patterns,
                "business_workflows": self.business_workflows
            }
        }
        
        return json.dumps(knowledge_data, ensure_ascii=False, indent=2)

# 創建全局知識庫實例
system_knowledge = None

def get_system_knowledge() -> SystemKnowledgeBase:
    """獲取系統知識庫實例（單例模式）"""
    global system_knowledge
    if system_knowledge is None:
        system_knowledge = SystemKnowledgeBase()
    return system_knowledge

def test_system_knowledge():
    """測試系統知識庫功能"""
    kb = get_system_knowledge()
    
    print("=== 系統知識庫測試 ===")
    
    # 測試知識庫摘要
    summary = kb.get_knowledge_summary()
    print(f"知識庫摘要: {summary}")
    
    # 測試時間態度分類
    test_texts = [
        "我要查詢今天的東洋班次",
        "昨天司機123的車資是多少？",
        "明天要匯入固定班次"
    ]
    
    for text in test_texts:
        time_scores = kb.classify_time_perspective(text)
        op_scores = kb.classify_operation_type(text)
        entities = kb.extract_entities(text)
        
        print(f"\n文本: {text}")
        print(f"時間態度: {time_scores}")
        print(f"操作類型: {op_scores}")
        print(f"實體提取: {entities}")
        
        # 獲取建議功能
        best_time = max(time_scores, key=time_scores.get)
        best_op = max(op_scores, key=op_scores.get)
        suggested_func = kb.get_suggested_function(best_time, best_op, entities)
        print(f"建議功能: {suggested_func}")

if __name__ == "__main__":
    test_system_knowledge() 
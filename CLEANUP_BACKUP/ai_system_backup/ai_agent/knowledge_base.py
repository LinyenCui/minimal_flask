"""
AI Agent 知識庫
包含資料庫schema、業務規則、範例等供AI大腦查詢使用
"""

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class DatabaseSchema:
    """資料庫結構定義"""
    table_name: str
    description: str
    columns: Dict[str, str]
    relationships: List[str]

@dataclass
class BusinessRule:
    """業務規則定義"""
    name: str
    description: str
    conditions: List[str]
    examples: List[str]

@dataclass
class UsageExample:
    """使用範例定義"""
    user_input: str
    expected_tools: List[str]
    expected_result: str
    explanation: str

class KnowledgeBase:
    """AI Agent 知識庫"""
    
    def __init__(self):
        self.database_schemas = self._init_database_schemas()
        self.business_rules = self._init_business_rules()
        self.usage_examples = self._init_usage_examples()
        self.system_info = self._init_system_info()
    
    def _init_database_schemas(self) -> Dict[str, DatabaseSchema]:
        """初始化資料庫結構信息"""
        schemas = {}
        
        # trips 表
        schemas["trips"] = DatabaseSchema(
            table_name="trips",
            description="核心班次表，存儲當前和未來的班次信息",
            columns={
                "trip_id": "班次ID (主鍵)",
                "fixed_trip_id": "固定班次ID (外鍵)",
                "date": "班次日期",
                "time": "班次時間",
                "start_point": "起點 (客戶簡稱)",
                "via_point": "經點 (可選)",
                "end_point": "終點 (客戶簡稱)",
                "meter_fare": "錶價",
                "extra_fare": "加成",
                "actual_fare": "實收 (計算欄位)",
                "category": "類別 (診所/東洋/臨時)",
                "driver_id": "司機ID",
                "status": "狀態 (待派/準備/已完成)",
                "trip_type": "班次類型 (fixed/temp)",
                "passenger_leave_reason": "請假原因"
            },
            relationships=[
                "關聯 fixed_schedules 表 (fixed_trip_id)",
                "關聯 drivers 表 (driver_id)", 
                "關聯 customers 表 (start_point, via_point, end_point)"
            ]
        )
        
        # fixed_schedules 表
        schemas["fixed_schedules"] = DatabaseSchema(
            table_name="fixed_schedules",
            description="固定班次模板表，用於匯入週次班次",
            columns={
                "id": "固定班次ID (主鍵)",
                "route_number": "路線編號 (包含星期)",
                "departure_time": "出發時間",
                "start_point": "起點",
                "via_point": "經點",
                "end_point": "終點",
                "base_fare": "基本車資",
                "surcharge": "加成",
                "category": "類別",
                "driver_id": "司機ID",
                "status": "狀態 (準備/請假/停用)",
                "note": "說明 (請假原因等)"
            },
            relationships=[
                "被 trips 表引用 (固定班次匯入)"
            ]
        )
        
        # completed_trips 表
        schemas["completed_trips"] = DatabaseSchema(
            table_name="completed_trips",
            description="已完成班次記錄表，用於歷史查詢和報表",
            columns={
                "id": "記錄ID (主鍵)",
                "date": "班次日期", 
                "start_point": "起點",
                "via_point": "經點",
                "end_point": "終點",
                "meter_fare": "錶價",
                "extra_fare": "加成",
                "category": "類別",
                "driver_id": "司機ID",
                "trip_type": "班次類型",
                "created_at": "記錄時間"
            },
            relationships=[
                "關聯 drivers 表 (driver_id)",
                "關聯 customers 表 (地點信息)"
            ]
        )
        
        # drivers 表
        schemas["drivers"] = DatabaseSchema(
            table_name="drivers",
            description="司機信息表",
            columns={
                "id": "司機ID (主鍵)",
                "name": "司機姓名",
                "plate_number": "車牌號碼",
                "car_brand": "車輛品牌",
                "car_model": "車輛型號"
            },
            relationships=[
                "被 trips 表引用",
                "被 completed_trips 表引用"
            ]
        )
        
        # customers 表
        schemas["customers"] = DatabaseSchema(
            table_name="customers",
            description="客戶地點表",
            columns={
                "short_name": "簡稱 (主鍵)",
                "name": "完整名稱",
                "address": "地址",
                "contact": "聯絡方式"
            },
            relationships=[
                "被 trips 表引用 (起終點)",
                "被 completed_trips 表引用"
            ]
        )
        
        return schemas
    
    def _init_business_rules(self) -> List[BusinessRule]:
        """初始化業務規則"""
        rules = []
        
        # 班次狀態規則
        rules.append(BusinessRule(
            name="班次狀態流程",
            description="班次狀態的正常流轉順序",
            conditions=[
                "新班次默認為「待派」狀態",
                "指派司機後變為「準備」狀態", 
                "執行時間到達後變為「已完成」狀態",
                "請假班次顯示為「請假（原因）」但status仍是「準備」"
            ],
            examples=[
                "待派 → 指派司機 → 準備 → 執行完成 → 已完成",
                "請假班次: 準備 + passenger_leave_reason"
            ]
        ))
        
        # 時間態規則（增強版）
        rules.append(BusinessRule(
            name="三時間態架構",
            description="系統按時間維度劃分功能，AI必須根據時間表達選擇正確的時間態",
            conditions=[
                "未來時間態：處理計劃和預約 (fixed_schedules) - 明天、下週、未來日期",
                "現在時間態：處理進行中班次 (trips) - 今天、現在、當前班次", 
                "過去時間態：處理歷史記錄 (completed_trips) - 昨天、上週、過去日期",
                "關鍵判斷：「昨天」、「前天」、「上週」等過去時間 → 使用 query_completed_trips",
                "關鍵判斷：「今天」的班次查詢 → 使用 query_dongyang_trips 或 query_clinic_trips",
                "關鍵判斷：「明天」、「下週」等未來時間 → 使用 import_fixed_schedules 或未來時間態工具"
            ],
            examples=[
                "匯入固定班次 → 未來時間態",
                "查詢今天班次 → 現在時間態 (trips表)",
                "司機533昨天診所班次 → 過去時間態 (completed_trips表)",
                "昨天東洋班次 → 過去時間態 (completed_trips表)",
                "生成報表 → 過去時間態"
            ]
        ))
        
        # 司機指派規則
        rules.append(BusinessRule(
            name="司機指派規則",
            description="司機指派的業務邏輯",
            conditions=[
                "只有「待派」狀態的班次能被指派",
                "司機ID必須存在於drivers表",
                "指派後班次狀態變為「準備」",
                "可以重新指派（覆蓋原指派）"
            ],
            examples=[
                "班次1585指派司機5386",
                "重新指派會覆蓋原司機"
            ]
        ))
        
        # 清理規則
        rules.append(BusinessRule(
            name="資料清理規則",
            description="trips表清理的安全規則",
            conditions=[
                "只能清理過去日期的資料",
                "不影響今天和未來的班次",
                "「清理已完成」只清理status='已完成'的記錄",
                "「清理過去」清理所有過去日期的記錄"
            ],
            examples=[
                "清理昨天已完成的班次",
                "不會清理明天的班次"
            ]
        ))
        
        return rules
    
    def _init_usage_examples(self) -> List[UsageExample]:
        """初始化使用範例"""
        examples = []
        
        # 查詢類範例
        examples.append(UsageExample(
            user_input="明天有哪些東洋班次？",
            expected_tools=["query_dongyang_trips"],
            expected_result="返回明天的東洋/臨時班次列表",
            explanation="自然語言日期'明天'需要轉換為具體日期，然後調用東洋班次查詢工具"
        ))
        
        examples.append(UsageExample(
            user_input="班次1585的詳細信息",
            expected_tools=["get_trip_details"],
            expected_result="返回班次1585的完整信息",
            explanation="直接提取班次ID，調用班次詳情查詢工具"
        ))
        
        # 指派類範例  
        examples.append(UsageExample(
            user_input="班次1585指派司機5386",
            expected_tools=["assign_driver"],
            expected_result="指派司機5386給班次1585",
            explanation="提取班次ID和司機ID，調用司機指派工具"
        ))
        
        # 時間態判斷範例
        examples.append(UsageExample(
            user_input="司機533昨天診所班次",
            expected_tools=["query_completed_trips"],
            expected_result="返回昨天司機533的診所已完成班次列表",
            explanation="過去時間「昨天」→ 使用query_completed_trips工具，包含司機ID和類別篩選"
        ))
        
        examples.append(UsageExample(
            user_input="昨天東洋班次完成情況",
            expected_tools=["query_completed_trips"],
            expected_result="返回昨天所有東洋類別的已完成班次",
            explanation="過去時間「昨天」+ 類別「東洋」→ 使用query_completed_trips工具"
        ))
        
        examples.append(UsageExample(
            user_input="司機5386前天有幾個班次",
            expected_tools=["query_completed_trips"],
            expected_result="返回前天司機5386的所有已完成班次統計",
            explanation="過去時間「前天」+ 司機篩選 → 使用query_completed_trips工具"
        ))
        
        # 複合需求範例
        examples.append(UsageExample(
            user_input="明天早上8點要去診所，但司機5386請假了，幫我重新安排",
            expected_tools=["query_dongyang_trips", "query_clinic_trips", "assign_driver"],
            expected_result="查詢相關班次，識別問題，提供重新指派建議",
            explanation="複合需求：查詢班次 → 識別司機問題 → 提供解決方案"
        ))
        
        return examples
    
    def _init_system_info(self) -> Dict[str, Any]:
        """初始化系統信息"""
        return {
            "database_type": "PostgreSQL",
            "timezone": "Asia/Taipei",
            "date_format": "YYYY-MM-DD",
            "time_format": "HH:MM",
            "current_date": "使用 get_taiwan_date() 獲取",
            "current_time": "使用 get_taiwan_time() 獲取",
            "supported_categories": ["診所", "東洋", "臨時"],
            "supported_statuses": ["待派", "準備", "已完成"],
            "natural_language_dates": {
                "今天": "current_date",
                "明天": "current_date + 1 day",
                "昨天": "current_date - 1 day",
                "後天": "current_date + 2 days"
            }
        }
    
    def get_schema(self, table_name: str) -> DatabaseSchema:
        """獲取表結構信息"""
        return self.database_schemas.get(table_name)
    
    def get_business_rules(self, keyword: str = None) -> List[BusinessRule]:
        """獲取業務規則"""
        if keyword:
            return [rule for rule in self.business_rules 
                   if keyword.lower() in rule.name.lower() or 
                      keyword.lower() in rule.description.lower()]
        return self.business_rules
    
    def get_examples(self, keyword: str = None) -> List[UsageExample]:
        """獲取使用範例"""
        if keyword:
            return [example for example in self.usage_examples 
                   if keyword.lower() in example.user_input.lower()]
        return self.usage_examples
    
    def get_system_info(self, key: str = None) -> Any:
        """獲取系統信息"""
        if key:
            return self.system_info.get(key)
        return self.system_info

# 全局知識庫實例
knowledge_base = KnowledgeBase() 
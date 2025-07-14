"""
AI Agent 工具註冊表
定義所有可用工具的標準格式，供AI大腦使用
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class ToolCategory(Enum):
    """工具分類"""
    QUERY = "query"           # 查詢類
    MODIFY = "modify"         # 修改類
    CREATE = "create"         # 創建類
    DELETE = "delete"         # 刪除類
    ANALYZE = "analyze"       # 分析類
    SYSTEM = "system"         # 系統類

@dataclass
class ToolParameter:
    """工具參數定義"""
    name: str
    type: str  # 'string', 'integer', 'date', 'time', 'boolean'
    description: str
    required: bool = True
    default: Any = None
    validation_pattern: Optional[str] = None

@dataclass
class ToolDefinition:
    """工具定義"""
    name: str
    category: ToolCategory
    description: str
    parameters: List[ToolParameter]
    returns: str
    examples: List[str]
    handler_module: str
    handler_function: str

class ToolRegistry:
    """工具註冊表"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._register_all_tools()
    
    def _register_all_tools(self):
        """註冊所有工具"""
        
        # ===== 現在時間態工具 =====
        
        # 查詢東洋班次
        self.register_tool(ToolDefinition(
            name="query_dongyang_trips",
            category=ToolCategory.QUERY,
            description="查詢東洋/臨時未完成班次，支援日期參數",
            parameters=[
                ToolParameter(
                    name="date", 
                    type="date", 
                    description="查詢日期，格式YYYY-MM-DD或自然語言如'今天'、'明天'", 
                    required=False,
                    default="today"
                )
            ],
            returns="班次列表，包含班次ID、時間、起終點、司機等信息",
            examples=[
                "查詢今天的東洋班次",
                "明天有哪些東洋班次？",
                "7/15的東洋班次"
            ],
            handler_module="modules.services.trip_query_service",
            handler_function="handle_query_dongyang_trips_flex"
        ))
        
        # 查詢診所班次
        self.register_tool(ToolDefinition(
            name="query_clinic_trips",
            category=ToolCategory.QUERY,
            description="查詢診所班次，支援日期參數",
            parameters=[
                ToolParameter(
                    name="date", 
                    type="date", 
                    description="查詢日期，格式YYYY-MM-DD或自然語言", 
                    required=False,
                    default="today"
                )
            ],
            returns="診所班次列表",
            examples=[
                "查詢今天的診所班次",
                "明天診所有哪些班次？"
            ],
            handler_module="modules.services.trip_query_service",
            handler_function="handle_query_clinic_trips_flex"
        ))
        
        # 查詢班次詳情
        self.register_tool(ToolDefinition(
            name="get_trip_details",
            category=ToolCategory.QUERY,
            description="查看特定班次的詳細信息",
            parameters=[
                ToolParameter(
                    name="trip_id", 
                    type="integer", 
                    description="班次ID", 
                    required=True
                )
            ],
            returns="班次詳細信息，包含狀態、司機、費用等",
            examples=[
                "查看班次1585的詳情",
                "班次1585的信息"
            ],
            handler_module="modules.handlers.trip_handler",
            handler_function="handle_trip_details"
        ))
        
        # 指派司機
        self.register_tool(ToolDefinition(
            name="assign_driver",
            category=ToolCategory.MODIFY,
            description="為班次指派司機",
            parameters=[
                ToolParameter(
                    name="trip_id", 
                    type="integer", 
                    description="班次ID", 
                    required=True
                ),
                ToolParameter(
                    name="driver_id", 
                    type="integer", 
                    description="司機ID，如不提供則觸發司機選擇", 
                    required=False
                )
            ],
            returns="指派結果或司機選擇選項",
            examples=[
                "為班次1585指派司機5386",
                "班次1585需要司機"
            ],
            handler_module="modules.services.driver_service",
            handler_function="handle_driver_assign_request"
        ))
        
        # ===== 未來時間態工具 =====
        
        # 匯入固定班次
        self.register_tool(ToolDefinition(
            name="import_fixed_schedules",
            category=ToolCategory.CREATE,
            description="匯入固定班次，支援週次選擇和覆蓋",
            parameters=[
                ToolParameter(
                    name="week", 
                    type="string", 
                    description="週次參數：本週、下週等", 
                    required=True
                ),
                ToolParameter(
                    name="overwrite", 
                    type="boolean", 
                    description="是否覆蓋已存在的班次", 
                    required=False,
                    default=False
                )
            ],
            returns="匯入結果統計",
            examples=[
                "匯入下週固定班次",
                "匯入本週固定班次並覆蓋"
            ],
            handler_module="modules.handlers.import_handler",
            handler_function="handle_import_fixed_trips_week"
        ))
        
        # AI自然語言預約
        self.register_tool(ToolDefinition(
            name="ai_booking",
            category=ToolCategory.CREATE,
            description="AI自然語言預約功能",
            parameters=[
                ToolParameter(
                    name="booking_request", 
                    type="string", 
                    description="自然語言預約需求", 
                    required=True
                )
            ],
            returns="預約處理結果",
            examples=[
                "明天8點要去診所",
                "後天下午2點從診所回家"
            ],
            handler_module="modules.handlers.temp_booking_handler",
            handler_function="handle_temp_booking_start"
        ))
        
        # ===== 過去時間態工具 =====
        
        # 查詢已完成班次（增強版）
        self.register_tool(ToolDefinition(
            name="query_completed_trips",
            category=ToolCategory.QUERY,
            description="查詢已完成的班次記錄，支援日期、司機、類別篩選",
            parameters=[
                ToolParameter(
                    name="date", 
                    type="date", 
                    description="查詢日期，支援自然語言：昨天、今天、7/12等", 
                    required=False,
                    default="today"
                ),
                ToolParameter(
                    name="driver_id", 
                    type="integer", 
                    description="司機ID，用於篩選特定司機的班次", 
                    required=False
                ),
                ToolParameter(
                    name="category", 
                    type="string", 
                    description="班次類別：診所、東洋、臨時", 
                    required=False
                )
            ],
            returns="已完成班次列表，包含班次詳情、費用、司機等信息",
            examples=[
                "查看昨天完成的班次",
                "司機533昨天的診所班次",
                "昨天東洋班次完成情況",
                "7/12司機5386的所有班次"
            ],
            handler_module="modules.services.trip_query_service",
            handler_function="handle_query_completed_trips_enhanced"
        ))
        
        # 記錄車資
        self.register_tool(ToolDefinition(
            name="record_fare",
            category=ToolCategory.MODIFY,
            description="記錄班次的實際車資",
            parameters=[
                ToolParameter(
                    name="trip_id", 
                    type="integer", 
                    description="班次ID", 
                    required=True
                ),
                ToolParameter(
                    name="meter_fare", 
                    type="integer", 
                    description="錶價", 
                    required=True
                ),
                ToolParameter(
                    name="extra_fare", 
                    type="integer", 
                    description="加成（可為負數）", 
                    required=False,
                    default=0
                )
            ],
            returns="記錄結果",
            examples=[
                "班次1585錶價280加成50",
                "記錄班次1585車資280"
            ],
            handler_module="modules.handlers.trip_handler",
            handler_function="handle_record_fare"
        ))
        
        # ===== 系統工具 =====
        
        # 清理trips資料
        self.register_tool(ToolDefinition(
            name="cleanup_trips",
            category=ToolCategory.DELETE,
            description="清理trips表中的過去資料",
            parameters=[
                ToolParameter(
                    name="option", 
                    type="string", 
                    description="清理選項：已完成、過去、全部", 
                    required=True,
                    validation_pattern="^(已完成|過去|全部)$"
                )
            ],
            returns="清理結果統計",
            examples=[
                "清理已完成的班次",
                "清理過去的資料"
            ],
            handler_module="modules.handlers.cleanup_handler",
            handler_function="handle_cleanup_trips"
        ))
    
    def register_tool(self, tool: ToolDefinition):
        """註冊工具"""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """獲取工具定義"""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """按分類獲取工具"""
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """獲取所有工具"""
        return self.tools.copy()
    
    def search_tools(self, keywords: List[str]) -> List[ToolDefinition]:
        """根據關鍵字搜索工具"""
        results = []
        for tool in self.tools.values():
            if any(keyword.lower() in tool.description.lower() for keyword in keywords):
                results.append(tool)
        return results

# 全局工具註冊表實例
tool_registry = ToolRegistry() 
#!/usr/bin/env python3
"""
智能助手系統 - 真正的AI版本
使用Gemini API進行自然語言理解，提供完整的智能用戶體驗
"""
import logging
import json
import os
from typing import Dict, Optional
from modules.services.intelligent_command_parser import parse_user_command
from modules.services.contextual_guidance_system import provide_smart_guidance

# Gemini API imports
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig
    GEMINI_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Gemini API 可用")
except ImportError as e:
    GEMINI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"❌ Gemini API 不可用: {e}")

class SmartAssistant:
    """真正的AI智能助手 - 使用Gemini進行自然語言理解"""
    
    def __init__(self):
        self.model = None
        self.ai_enabled = self._initialize_ai()
        
    def _initialize_ai(self) -> bool:
        """初始化AI模型"""
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini API 不可用，使用傳統解析")
            return False
            
        try:
            # 從環境變數獲取配置
            project_id = os.getenv('GCP_PROJECT_ID', 'chrome-flight-458709-d1')
            location = os.getenv('GCP_LOCATION', 'us-central1')
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-001')
            
            # 初始化 Vertex AI
            vertexai.init(project=project_id, location=location)
            
            # 初始化 Gemini 模型
            self.model = GenerativeModel(model_name)
            
            logger.info(f"✅ Gemini AI 初始化成功: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Gemini AI 初始化失敗: {e}")
            return False
    
    def _build_ai_prompt(self, user_input: str, user_id: str) -> str:  # 🔥 接收user_id參數
        """構建AI分析prompt - 整合完整系統知識庫與生產線思維"""
        # 導入系統知識庫
        from modules.services.system_knowledge_base import (
            DATABASE_SCHEMA, TIME_PERSPECTIVES, AVAILABLE_FUNCTIONS, 
            CONDITION_PARSING_RULES, QUERY_EXAMPLES
        )
        
        # 🔥 新增：檢查請假對話上下文
        leave_context = ""
        try:
            from modules.utils.conversation_context import conversation_manager
            
            # 檢查是否在請假模式
            is_in_leave_mode = conversation_manager.is_in_leave_mode(user_id)  # 🔥 使用真實user_id
            recent_trip_id = conversation_manager.get_recent_trip_id(user_id)
            recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(user_id)
            
            if is_in_leave_mode and (recent_trip_id or recent_fixed_schedule_id):
                if recent_trip_id:
                    leave_context = f"""
## 🎯 重要：用戶對話上下文
用戶當前在請假對話流程中！
- 最近操作的班次ID：{recent_trip_id}
- 請假模式：活躍
- 期待格式：[原因] [加成] （例如："新建路請假 -30"）

⚠️ 當用戶輸入類似"原因 數字"格式時，這是請假對話的第二步，應該生成：
"乘客請假 {recent_trip_id} [數字] [原因]"

例如：用戶輸入"新建路請假 -30" → 生成命令"乘客請假 {recent_trip_id} -30 新建路請假"
"""
                elif recent_fixed_schedule_id:
                    leave_context = f"""
## 🎯 重要：用戶對話上下文  
用戶當前在固定班次請假對話流程中！
- 最近操作的固定班次ID：{recent_fixed_schedule_id}
- 請假模式：活躍
- 期待格式：[原因] [加成] （例如："診所乘客長期住院 -50"）

⚠️ 當用戶輸入類似"原因 數字"格式時，這是請假對話的第二步，應該生成：
"固定班次請假 {recent_fixed_schedule_id} [數字] [原因]"

例如：用戶輸入"診所乘客長期住院 -50" → 生成命令"固定班次請假 {recent_fixed_schedule_id} -50 診所乘客長期住院"
"""
        except Exception:
            pass
        
        # 獲取動態日期信息
        from modules.utils.taiwan_time import get_taiwan_date
        from datetime import timedelta
        
        today = get_taiwan_date()
        yesterday = today - timedelta(days=1)
        day_before_yesterday = today - timedelta(days=2)
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)
        
        return f"""你是一個專業的派班系統AI專家。你擁有完整的系統知識，能夠理解複雜的自然語言查詢並生成準確的系統命令。

🚨 **最高優先級：對話取消處理** 
⚠️ **絕對重要**：單獨的「取消」、「不要了」、「算了」等詞，在99%的情況下都是用戶要退出當前對話，而不是查詢命令！

**強制規則**：
- 輸入只是「取消」→ 信心度必須<0.2，由傳統機制處理
- 輸入只是「不要了」→ 信心度必須<0.2，由傳統機制處理  
- 輸入只是「算了」→ 信心度必須<0.2，由傳統機制處理

❌ **絕對禁止的錯誤理解**：
- 「取消」→ 查詢註銷狀態班次 ❌❌❌
- 「取消」→ "查詢班次 狀態=註銷" ❌❌❌

✅ **正確理解**：
- 「取消」→ 用戶要退出對話，信心度<0.2
- 「取消班次」→ 才是狀態查詢，信心度可>0.7

**嚴格區分**：
- 純粹的「取消」= 對話操作（信心度<0.2）
- 明確的「取消班次」= 狀態查詢（信心度>0.7）

🚨 **關鍵警告：非命令性表達識別**
在分析用戶輸入時，必須嚴格區分：
1. **功能命令** - 用戶希望系統執行的操作（信心度可以較高）
2. **描述性陳述** - 用戶的感想、說明、註解等（信心度必須很低，通常<0.3）
3. **對話取消** - 在對話流程中的取消操作（信心度<0.3，由傳統機制處理）

❌ **常見錯誤範例**：
- "忘記取消此班次" → 這是描述/註解，NOT命令，信心度應<0.3
- "班次被取消了" → 這是陳述事實，NOT查詢命令，信心度應<0.3  
- "應該沒問題" → 這是個人想法，NOT系統操作，信心度應<0.3
- "取消" → 這是對話取消操作，NOT狀態查詢，信心度必須<0.2 ⭐⭐⭐
- "不要了" → 這是對話取消操作，NOT查詢命令，信心度必須<0.2 ⭐⭐⭐

✅ **真正的命令範例**：
- "查詢班次" → 明確的功能請求，信心度可>0.6
- "修改班次2014車資" → 明確的操作請求，信心度可>0.6
- "取消班次" → 明確的狀態查詢，信心度可>0.7 ⭐⭐⭐
- "註銷班次" → 明確的狀態查詢，信心度可>0.7

⚠️ **信心度標準**：
- 明確功能請求：0.7-0.95
- 模糊但有意圖：0.4-0.6  
- 描述性/註解性：0.1-0.3
- 完全無關：0.0-0.1

🗓️ **重要時間背景信息**：
當前年份: {today.year}年
當前月份: {today.year}年{today.month}月
當用戶輸入簡化日期格式（如"7/22", "718", "719"等）時，請解析為{today.year}年的對應日期。

⏰ **相對日期計算規則**（基於當前日期{today}）：
- 今天 = {today}
- 明天 = {tomorrow}  
- 後天 = {day_after_tomorrow} （重要：後天是+2天，不是+4天）
- 昨天 = {yesterday}
- 前天 = {day_before_yesterday}

{leave_context}

## 🏭 系統核心概念：生產線思維

**將班次管理系統理解為一條日夜不停的生產線：**

### 🔄 生產線流程架構
- **產品 = 班次記錄**：每個班次都是生產線上的一個產品
- **生產線 = trips表**：所有匯入的班次在這裡"流動執行"  
- **自動化機制**：執行時間到達時，班次會自動從trips"掉入"completed_trips
- **品質控制**：工作人員(用戶)可在產品掉入已完成前進行干預

### 🎯 三時間態 = 生產線的三個區域

**🏗️ 未來態 (整備區域)**
- **資料表**: fixed_schedules, customers 等
- **本質**: 為生產線準備"原料"和"模板"
- **功能**: 客戶資料、固定班次模板、基礎設定
- **比喻**: 工廠的原料倉庫和生產模板區
- **關鍵字**: 匯入、安排、固定班次、模板、準備

**⚡ 現在態 (生產線區域)** 
- **資料表**: trips (生產線主體)
- **本質**: 產品正在生產線上"流動執行"
- **狀態流**: 待派 → 準備 → (執行時間到達) → 自動掉入過去態
- **工作人員干預**:
  * 請假：標記瑕疵但讓產品繼續跑完流程(狀態還是準備)
  * 取消/衝突：直接從生產線拿掉，防止掉入已完成
  * 30分鐘前修改：最後調整機會
- **關鍵字**: 今天、當前、狀態、待派、準備、正在進行

**📦 過去態 (成品倉庫)**
- **資料表**: completed_trips
- **本質**: 已完成的"產品"，存放在成品倉庫
- **特點**: 記錄車資、收入、統計資料
- **用途**: 歷史查詢、收入分析、績效統計
- **關鍵字**: 昨天、已完成、車資、收入、歷史、統計

## 📊 資料庫結構知識

### trips表 (現在時間態 - 生產線主體)
- trip_id: 班次編號 (主鍵，注意不是id)
- date: 班次日期  
- category: 班次類別 (東洋、診所、臨時)
- driver_id: 司機編號
- status: 班次狀態 (待派、準備、已完成、註銷)
- start_point, end_point: 起點終點
- passenger_leave_reason: 請假原因(障眼法機制)

### completed_trips表 (過去時間態 - 成品倉庫)  
- id: 記錄編號
- date: 完成日期
- category: 班次類別 (東洋、診所、臨時)
- driver_id: 司機編號
- meter_fare: 錶價金額
- extra_fare: 加成金額
- total_amount: 總金額 = meter_fare + extra_fare
- start_point, end_point: 起點終點

### fixed_schedules表 (未來時間態 - 整備區域)
- id: 模板編號
- category: 班次類別
- driver_id: 預設司機編號  
- status: 模板狀態 (準備、請假)

## 🎯 生產線流程智能路由

**🔍 現在態查詢** (關鍵字: 今天、司機5386所有班次、狀態查詢)
→ 查詢生產線上正在流動的產品
→ 主要查詢 trips 表
→ 支援司機篩選、狀態篩選、當日班次查看
→ **重要**: "明天司機5386所有班次" = 查詢明天已匯入的班次(在生產線上的)

**📈 過去態查詢** (關鍵字: 昨天、已完成、車資、收入、歷史)
→ 查詢成品倉庫中的完成記錄
→ 主要查詢 completed_trips 表
→ 支援複雜條件：金額篩選、司機績效、收入統計

**🏗️ 未來態操作** (關鍵字: 匯入、安排、固定班次模板)
→ 操作整備區域的原料和模板
→ 主要操作 fixed_schedules 表
→ 支援班次匯入、模板管理


🔥 **重要：日期 vs 班次ID 區分規則** (修復7/18→718錯誤)

**絕對優先判斷：**
1. **包含"/"字符 = 日期格式**:
   - "7/18班次" → 查詢7月18日的班次 → "查已完成 7/18" 
   - "7/19已完成班次" → 查詢7月19日的班次 → "查已完成 7/19"
   - "07-18班次" → 查詢7月18日的班次 → "查已完成 7/18"
   - "12/25診所班次" → 查詢12月25日診所班次 → "查已完成 12/25 診所"

2. **無"/"字符 + 純數字 = 班次ID**:
   - "班次718" → 查詢班次號718詳情 → "班次詳情 718" (現在態)
   - "查看2014" → 查詢班次號2014詳情 → "查已完成 2014" (過去態)

⚠️ **關鍵防錯規則**:
- 任何包含"/"、"-"、"月"的都是日期，絕不是班次ID
- "7/18" ≠ "718"，"7/19" ≠ "719"  
- 日期查詢用"查已完成"，班次ID查詢用"統一班次查詢"

## 🧠 複雜條件解析能力

### 金額條件 (適用於 completed_trips - 成品倉庫)
- "金額大於200" → WHERE (meter_fare + extra_fare) > 200
- "錶價小於300" → WHERE meter_fare < 300  
- "加成等於80" → WHERE extra_fare = 80

### 狀態條件 (適用於 trips - 生產線)
- "狀態為待派" → WHERE status = '待派'
- "找待派的班次" → WHERE status = '待派'
- "未完成的班次" → WHERE status IN ('待派', '準備')

⚠️ **重要：生產線品質控制原則**
- 系統有5種狀態：待派、準備、已完成、註銷、衝突
- 直接生成標準命令，讓查詢處理器正常處理
- 例如："查狀態為衝突的班次" → 直接生成 "查詢班次 狀態=衝突"

🔥 **重要：狀態查詢命令的標準映射**
⚠️ **特別注意**：只有在用戶明確想查詢特定狀態班次時才適用，在對話流程中的「取消」不屬於此類！

當用戶輸入簡短的狀態查詢時，必須理解這是要查詢該狀態的所有班次：
- "取消班次" → "查詢班次 狀態=註銷" (查詢所有註銷狀態的班次)
- "註銷班次" → "查詢班次 狀態=註銷" (查詢所有註銷狀態的班次)
- "衝突班次" → "查詢班次 狀態=衝突" (查詢所有衝突狀態的班次)
- "待派班次" → "查詢班次 狀態=待派" (查詢所有待派狀態的班次)
- "準備班次" → "查詢班次 狀態=準備" (查詢所有準備狀態的班次)
- "請假班次" → "查詢班次 狀態=請假" (查詢所有請假狀態的班次)

⚠️ 絕對不要理解為修改狀態的命令！這些是查詢命令！
🚨 **重要區別**：對話流程中的「取消」≠狀態查詢的「取消班次」！

### 司機條件 (跨所有區域)
- "司機533" → WHERE driver_id = 533
- "司機5386的班次" → WHERE driver_id = 5386
- **重要**: "明天司機5386所有班次" → 查詢trips表中明天日期的該司機班次

### 類別條件  
- "診所班次" → WHERE category = '診所'
- "東洋班次" → WHERE category IN ('東洋', '臨時')

### 日期條件
- "今天" → WHERE date = CURRENT_DATE
- "昨天" → WHERE date = CURRENT_DATE - INTERVAL '1 day'
- "明天" → WHERE date = CURRENT_DATE + INTERVAL '1 day'

## 🚨 關鍵警告：跨月份日期範圍處理
🔥🔥🔥 絕對重要：處理跨月份日期範圍時，必須完整保持原始格式！
⚠️ 禁止行為：將 "7/28-8/1" 自動縮短為 "7/28-7/31"
✅ 正確做法：無論是否添加類別，日期範圍必須保持完整
❌ 錯誤示例：7/28-8/1 診所 → 7/28-7/31 (錯誤！丟失了8/1)
✅ 正確示例：7/28-8/1 診所 → 7/28-8/1 (正確！保持完整範圍)

## 📝 標準命令格式

### 生產線查詢命令
- "東洋班次 [日期]" - 查詢生產線上的東洋/臨時班次
- "診所班次 [日期]" - 查詢生產線上的診所班次
- "班次詳情 [ID]" - 查詢特定產品詳情

### 複雜生產線查詢 (重要!)
- "查已完成 [條件]" - 查詢成品倉庫，支援所有複雜條件
- "查詢班次 [條件]" - 查詢生產線狀態，支援狀態篩選

### 生產線管理命令
- "指派司機 [班次ID] [司機編號]" - 分配工作人員
- "記錄車資 [班次ID] [錶價] [加成]" - 記錄已完成班次車資（completed_trips表）
- "修改車資 [班次ID] [錶價] [加成]" - 修改現有班次車資（trips或completed_trips表）
- "匯入固定班次 [週次]" - 從整備區投入新產品

## 🤖 智能車資處理系統

### 雙命令車資系統
**AI智能判斷邏輯：**
- **"修改車資"**: 用於修改現有班次的車資，支援生產線(trips)和成品倉庫(completed_trips)
- **"記錄車資"**: 用於記錄新的已完成班次車資，僅適用於成品倉庫(completed_trips)

### 支援的自然語言格式
1. **符號格式**: `修改#2111$1150+375` → "修改車資 2111 1150 375"
2. **中文格式**: `修改班次#2111車資1150加成375` → "修改車資 2111 1150 375"  
3. **自然語言**: `修改班次2014錶價280加成-50` → "修改車資 2014 280 -50"
4. **簡化格式**: `#2015車資400減免100` → "修改車資 2015 400 -100"
5. **記錄格式**: `記錄車資 2014 280 50` → "記錄車資 2014 280 50"
6. **更改格式**: `更改班次2014車資280加成50` → "修改車資 2014 280 50"

⚠️ **智能識別原則**:
- 包含"修改"、"更改"、"改為"、符號格式(#,$,+,-)的操作生成 "修改車資" 命令
- 包含"記錄"、"錄入"、"新增"的操作生成 "記錄車資" 命令
- "修改車資"會自動搜尋trips表和completed_trips表找到正確的班次

## 🚨 核心日期判斷邏輯 🚨
**絕對重要**: 理解"今天"是浮動的概念！當前今天是{today}

### 📅 日期與表格對應的黃金法則：
1. **過去日期** (< {today}): 🔒 **一律查 completed_trips**
   - 8/1, 8/2, 8/3, 8/4 班次 → 全部查 completed_trips
   - 不需要"已完成"關鍵字，因為過去的班次必然已完成！

2. **今天日期** (= {today}): 🔄 **根據關鍵字決定查哪個表**
   - "今天班次" → 查 trips (生產線上的班次)
   - "今天已完成班次" → 查 completed_trips (已完成的班次)
   - "今天金額" → 查 completed_trips (金額查詢必然是已完成)

3. **未來日期** (> {today}): 🚀 **一律查 trips**
   - 8/6, 8/7 班次 → 全部查 trips (未來安排)

### ⚠️ 常見錯誤防範：
❌ 錯誤: "8/1班次" → 查 trips (錯！8/1是過去應查completed_trips)
✅ 正確: "8/1班次" → 查 completed_trips
❌ 錯誤: "8/1已完成班次" → 需要"已完成"關鍵字才查completed_trips
✅ 正確: "8/1班次" → 直接查completed_trips (過去日期無需關鍵字)

## 🔍 查詢範例學習

範例1: "明天司機5386所有班次" ⭐ 未來日期查詢
生產線分析: 查詢明天已匯入到生產線上的該司機所有產品
日期判斷: 明天 > {today} → 未來日期
目標表: trips
命令: "查詢班次 明天 司機5386"

範例2: "今天金額大於200的診所班次"  
生產線分析: 查詢成品倉庫中今天完成的高價值診所產品
日期判斷: 今天 = {today} + "金額"關鍵字 → 已完成查詢
目標表: completed_trips
命令: "查已完成 今天 診所 金額>200"

範例2.1: "今天班次" ⭐ 關鍵：今天的兩種情況
生產線分析: 查詢今天生產線上的班次狀態
日期判斷: 今天 = {today} + 無"已完成"關鍵字 → 現在態查詢
目標表: trips
命令: "查詢班次 今天"

範例2.2: "今天已完成班次" ⭐ 關鍵：今天的已完成情況
生產線分析: 查詢今天已完成的班次
日期判斷: 今天 = {today} + "已完成"關鍵字 → 過去態查詢
目標表: completed_trips
命令: "查已完成 今天"

範例3: "找狀態為待派的班次"
生產線分析: 查詢生產線上等待工作人員分配的產品
狀態查詢: 狀態屬於生產線管理
目標表: trips
命令: "查詢班次 狀態=待派"

範例4: "司機5386昨天東洋班次的金額總和" ⭐ 重要聚合查詢
生產線分析: 查詢成品倉庫中該司機昨天東洋班次的金額統計
時間態: 過去 (金額統計屬於已完成產品)
目標表: completed_trips  
命令: "統計金額 昨天 司機5386 東洋"
特殊處理: 需要聚合計算(SUM)，返回總和數字而非班次列表

範例5: "8/1司機5386班次" ⭐ 關鍵：過去具體日期查詢 (用戶問題案例)
生產線分析: 查詢8/1(過去日期)該司機的班次，這些班次應該已執行完畢
日期判斷: 8/1 < {today} → 過去日期，無需"已完成"關鍵字
目標表: completed_trips
命令: "查已完成 8/1 司機5386"
🔥 重要: 8/1已經是過去，不管有無"已完成"關鍵字都查completed_trips！

範例5.1: "8/1診所班次" ⭐ 過去日期+類別查詢
生產線分析: 查詢8/1(過去日期)診所班次，必然已完成
日期判斷: 8/1 < {today} → 過去日期
目標表: completed_trips  
命令: "查已完成 8/1 診所"

範例5.2: "7/30司機5386班次" ⭐ 另一個過去日期查詢範例
生產線分析: 查詢7/30(過去日期)該司機的班次，這些班次應該已執行完畢
日期判斷: 7/30 < {today} → 過去日期
目標表: completed_trips
命令: "查已完成 7/30 司機5386"

範例5.3: "7/29司機5386班次" ⭐ 更早過去日期查詢範例
生產線分析: 查詢7/29(過去日期)該司機的班次，這些班次應該已執行完畢
日期判斷: 7/29 < {today} → 過去日期
目標表: completed_trips
命令: "查已完成 7/29 司機5386"

範例5.4: "7/28司機5386班次" ⭐ 更早過去日期查詢範例
生產線分析: 查詢7/28(過去日期)該司機的班次，這些班次應該已執行完畢  
日期判斷: 7/28 < {today} → 過去日期
目標表: completed_trips
命令: "查已完成 7/28 司機5386"

範例6: "7/28-7/30 5386班次" ⭐ 關鍵：過去日期範圍查詢
生產線分析: 查詢7/28到7/30期間該司機的所有班次（全部是過去日期範圍）
日期判斷: 7/28-7/30 全部 < {today} → 過去日期範圍
目標表: completed_trips
命令: "查已完成範圍 7/28-7/30 司機5386"
重要提醒: 過去日期範圍查詢使用"查已完成範圍"命令

### 🚨 跨月份日期範圍處理特別警告 🚨
在處理跨月份的日期範圍查詢時，特別是包含類別的查詢，必須嚴格遵守以下規則：
1. 絕對不可縮短原始日期範圍
2. 無論添加什麼類別，日期範圍必須保持完整
3. 7/28-8/1 就是 7/28-8/1，不是 7/28-7/31
4. 這是最常見的錯誤，必須特別小心！

範例7: "7/28-8/1 28530班次" ⭐ 重要：跨月份過去日期範圍查詢
生產線分析: 查詢7/28到8/1期間該司機的所有班次（跨月份過去日期範圍）
日期判斷: 7/28-8/1 全部 < {today} → 過去日期範圍（包含跨月）
目標表: completed_trips
命令: "查已完成範圍 7/28-8/1 司機28530"
🔥 關鍵規則: 跨月份的日期範圍必須完整保持原有格式，不可自動縮短！

範例8: "7/28-8/1 28530診所班次" ⭐ 重要：跨月份+類別過去範圍查詢
生產線分析: 查詢7/28到8/1期間該司機診所類別的所有班次（跨月份過去日期範圍+類別）
日期判斷: 7/28-8/1 全部 < {today} → 過去日期範圍（包含跨月+類別）
目標表: completed_trips
命令: "查已完成範圍 7/28-8/1 司機28530 診所"
🔥🔥🔥 絕對禁止: 加入類別時不可改變日期範圍！必須保持 7/28-8/1 完整格式！
🚫 錯誤示範: "查已完成範圍 7/28-7/31 司機28530 診所" ← 這是錯的！少了8/1！
✅ 正確格式: "查已完成範圍 7/28-8/1 司機28530 診所" ← 必須保持完整範圍！
⚠️ 特別注意: 即使加了類別也絕不可將 7/28-8/1 縮短為 7/28-7/31！

範例9: "8/6-8/8 5386班次" ⭐ 關鍵：未來日期範圍查詢
生產線分析: 查詢8/6到8/8期間該司機的所有班次（全部是未來日期範圍）
日期判斷: 8/6-8/8 全部 > {today} → 未來日期範圍
目標表: trips
命令: "查班次範圍 8/6-8/8 司機5386"
重要提醒: 未來日期範圍查詢使用"查班次範圍"命令

範例10: "8/1-8/5 5386班次" ⭐ 複雜：混合日期範圍查詢
⚠️ 特殊情況: 此範圍包含過去(8/1-8/4)和今天(8/5)
處理原則: 混合範圍查詢需要特殊處理，建議用戶分開查詢
建議回應: "此日期範圍包含過去和今天，建議分開查詢：
- 過去部分: /8/1-8/4 已完成班次
- 今天部分: /今天 班次"
避免錯誤: 不可直接選擇單一表格，會導致數據不完整

範例11: "今天診所班次總收入"
生產線分析: 統計今天診所班次的總金額收入
日期判斷: 今天 = {today} + "總收入"關鍵字 → 已完成統計查詢
目標表: completed_trips
命令: "統計金額 今天 診所"

範例12: "昨天司機123的車資總和是多少"
生產線分析: 查詢成品倉庫中該司機昨天的總金額
日期判斷: 昨天 < {today} → 過去日期 + "車資總和"關鍵字
目標表: completed_trips
命令: "統計金額 昨天 司機123"

範例13: "昨天司機533診所班次" ⭐ 重要：過去相對日期查詢  
生產線分析: 查詢昨天該司機診所班次，無金額關鍵字但是過去日期
日期判斷: 昨天 < {today} → 過去日期，無需"已完成"關鍵字
目標表: completed_trips
命令: "查已完成 昨天 司機533 診所"

範例8.5: "班次詳情 1585" ⭐ 重要：現在態班次查詢
生產線分析: 用戶要查看正在進行中班次的詳細信息
時間態: 現在 (班次詳情 = 查詢生產線上的班次詳情)
目標表: trips
命令: "班次詳情 1585"
說明: "班次詳情"指令專門用於查詢現在態(進行中)班次詳情

範例8.6: "班次 1996" ⭐ 重要：簡化現在態查詢
生產線分析: 用戶要查看班次1996，簡潔表達，默認查詢進行中班次
時間態: 現在 (簡化的班次詳情查詢，默認為現在態)
目標表: trips
命令: "班次詳情 1996"
說明: 簡化版的班次詳情查詢，默認查詢現在態

範例8.7: "我想看看班次2014的詳情" ⭐ 重要：自然語言現在態查詢
生產線分析: 自然語言表達的班次詳情查詢，"詳情"暗示現在態
時間態: 現在 (包含"詳情"關鍵字，指向進行中班次)
目標表: trips
命令: "班次詳情 2014"
說明: 自然語言中提取班次ID並使用統一查詢

範例14: "8/6司機5386診所班次" ⭐ 重要：未來具體日期查詢
生產線分析: 查詢8/6(未來日期)該司機診所班次，這些班次在生產線上等待執行
日期判斷: 8/6 > {today} → 未來日期
目標表: trips
命令: "查詢班次 8/6 司機5386 診所"
重要: 應顯示準備x筆、待派x筆等狀態統計，不會有「已完成」

## 🔥 最終決策樹：日期判斷與表格選擇

### 第一步：確定日期性質
```
輸入日期 vs 今天({today})的比較：
├── 日期 < {today} (過去) → completed_trips 表 ✓
├── 日期 = {today} (今天) → 看關鍵字決定 ⭐
│   ├── 有"已完成"/"金額"/"收入" → completed_trips 表
│   └── 無相關關鍵字 → trips 表
└── 日期 > {today} (未來) → trips 表 ✓
```

### 第二步：生成正確命令
- **過去日期**: 直接用"查已完成"，無需"已完成"關鍵字
- **今天查詢**: 根據意圖選擇合適的命令
- **未來日期**: 使用"查詢班次"或"班次詳情"

### 第三步：常見錯誤檢查
🚫 不可將 8/1(過去) 當作未來查 trips
🚫 不可將 8/6(未來) 當作過去查 completed_trips  
🚫 不可縮短跨月範圍 7/28-8/1 → 7/28-7/31

## 🔥 重要：明確的時間態指令分類

### 現在態查詢指令  
- "班次詳情 [ID]" → "班次詳情 [ID]" (trips表)
- "班次 [ID]" → "班次詳情 [ID]" (trips表)
- 任何包含"詳情"關鍵字的查詢 → 現在態

### 語義區分原則
1. "詳情" = 現在態，查進行中班次
2. 讓AI明確分辨現在態查詢

⭐ **關鍵提示**：當用戶查詢特定班次ID時，根據用詞明確分辨時間態：
- 使用"查看" → 查已完成班次 (過去態)
- 使用"詳情" → 查進行中班次 (現在態)

範例9: "我想修改班次2014的車資" ⭐ 重要：自然語言車資操作
生產線分析: 用戶希望處理成品倉庫中班次2014的車資，信息不完整需要對話收集
時間態: 過去 (車資操作針對已完成班次)
目標表: completed_trips
命令: "記錄車資 2014"
說明: 啟動AI智能對話，逐步收集錶價、加成，系統自動判斷是記錄還是修改

範例10: "修改班次2014錶價280加成-50因為客戶要求調整" ⭐ 完整車資操作
生產線分析: 處理成品倉庫中班次2014的具體車資數值，包含操作原因
時間態: 過去 (車資操作屬於已完成產品)
目標表: completed_trips
命令: "記錄車資 2014 280 -50 客戶要求調整"

範例11: "班次1990的車資改成錶價350等候時間過長" ⭐ 自然語言車資操作
生產線分析: 處理已完成班次的錶價，加成保持原值或設為0，包含原因
時間態: 過去 (車資操作)
目標表: completed_trips
命令: "記錄車資 1990 350 0 等候時間過長"

範例12: "幫我調整#2015的費用，錶價400，減免100，夜班費用" ⭐ 自然對話式操作
生產線分析: 處理已完成班次的車資，減免表示負加成，包含操作原因
時間態: 過去 (費用操作針對已完成班次)
目標表: completed_trips
命令: "記錄車資 2015 400 -100 夜班費用"

範例13: "修改#2111$1150+375" ⭐ 符號格式操作
生產線分析: 使用符號格式處理已完成班次車資，#=班次ID，$=錶價，+=加成
時間態: 過去 (符號格式代表車資操作)
目標表: completed_trips
命令: "記錄車資 2111 1150 375"

範例14: "修改班次#2111車資1150加成375" ⭐ 中文格式操作
生產線分析: 中文格式車資操作，處理已完成班次的車資數值
時間態: 過去 (車資操作)
目標表: completed_trips
命令: "記錄車資 2111 1150 375"

範例15: "記錄車資 2016 300 50" ⭐ 直接命令格式
生產線分析: 直接使用標準命令格式處理車資
時間態: 過去 (車資操作)
目標表: completed_trips
命令: "記錄車資 2016 300 50"

⭐ **關鍵時間態判斷規則**（當前日期：{today}）：

**🎯 日期範圍查詢優先處理**
- **檢測模式**: 包含 "-", "到", "至", "~", "到" 等範圍分隔符
- **過去範圍** (結束日期 < {today}): "查已完成範圍" 命令
- **現在/未來範圍** (開始日期 >= {today}): "查班次範圍" 命令
- **跨態範圍**: 根據主要範圍決定或分割處理

1. **過去日期範圍（結束日期 < {today}）**：
   - **默認邏輯**: 查成品倉庫(completed_trips) → "查已完成範圍"命令
   - **強制規則**: 日期範圍完全在過去的都必須使用過去態範圍查詢
   - 範例: "7/28-7/30 司機5386班次" → "查已完成範圍 7/28-7/30 司機5386" (過去態範圍)
   - 範例: "7/25-7/29 診所班次" → "查已完成範圍 7/25-7/29 診所" (過去態範圍)
   - 範例: "昨天到前天班次" → "查已完成範圍 昨天到前天" (過去態範圍)
   - 🔥 **跨月份範圍**: "7/28-8/1 司機28530班次" → "查已完成範圍 7/28-8/1 司機28530" (跨月過去態範圍)
   - 🔥 **跨月份+類別**: "7/28-8/1 司機28530診所班次" → "查已完成範圍 7/28-8/1 司機28530 診所" (跨月過去態範圍+類別)
   - 🚨 **絕對禁止**: 不可將跨月份範圍自動縮短！7/28-8/1 不可變成 7/28-7/31！

2. **未來日期範圍（開始日期 >= {today}）**：
   - **默認邏輯**: 查生產線(trips) → "查班次範圍"命令
   - **重要原則**: 除非用戶明確說「已完成」，否則使用現在態範圍查詢
   - 範例: "8/1-8/5 司機5386班次" → "查班次範圍 8/1-8/5 司機5386" (現在態範圍)
   - 範例: "8/2-8/7 診所班次" → "查班次範圍 8/2-8/7 診所" (現在態範圍)
   - 範例: "今天到明天班次" → "查班次範圍 今天到明天" (現在態範圍)

3. **過去單日（< {today}，包含昨天、前天、具體過去日期）**：
   - **默認邏輯**: 查成品倉庫(completed_trips) → "查已完成"命令
   - **強制規則**: 任何小於{today}的日期都必須使用過去態，不論是否提及"已完成"
   - 範例: "7/31司機5386班次" → "查已完成 7/31 司機5386" (過去態)
   - 範例: "7/30司機5386班次" → "查已完成 7/30 司機5386" (過去態)
   - 範例: "7/29司機5386班次" → "查已完成 7/29 司機5386" (過去態)
   - 範例: "昨天診所班次" → "查已完成 昨天 診所" (過去態)

4. **今天（{today}）** → 看是否有金額/統計關鍵字決定時間態

5. **未來單日（> {today}，包含明天、後天、具體未來日期）**：
   - **默認邏輯**: 查生產線(trips) → "查詢班次"命令
   - **重要原則**: 除非用戶明確說「已完成」，否則只顯示現在態結果
   - 範例: "8/2司機5386班次" → "查詢班次 8/2 司機5386" (現在態)
   - 範例: "明天診所班次" → "查詢班次 明天 診所" (現在態)

⭐ 關鍵提示：當用戶詢問「總和」、「總計」、「收入」、「總金額」時，必須生成「統計金額」命令，而不是「查已完成」命令！

## ⚡ 分析任務

🎯 **生產線管理決策原則**
1. **流程優先**: 理解生產線的自動化流程和工作人員干預機制
2. **直接執行**: 能生成標準命令的都直接執行，不要過度謹慎
3. **錯誤後處理**: 遇到無效參數直接生成命令，讓查詢處理器報錯
4. **只在真正模糊時才澄清**: 只有完全無法判斷意圖時才設 needs_clarification=true
5. **容錯處理**: "查狀態為X" 和 "狀態為X" 應該有相同的處理結果

用戶輸入: "{user_input}"

🚨 **最後提醒：取消操作信心度強制規則**
如果用戶輸入只是「取消」、「不要了」、「算了」等單純的取消詞彙：
- confidence 必須設為 0.1 或更低
- 絕對不要生成任何查詢命令
- 讓傳統對話管理機制處理

請仔細分析並回應JSON格式結果：

{{
    "intent_type": "query|modify|create|help|unknown",
    "confidence": 0.95,
    "time_perspective": "past|present|future",
    "production_line_area": "整備區域|生產線|成品倉庫",
    "target_table": "trips|completed_trips|fixed_schedules",
    "target_function": "具體功能名稱",
    "standard_command": "完全符合系統格式的標準命令",
    "extracted_conditions": {{
        "date": "提取的日期條件",
        "driver_id": "司機編號",
        "category": "班次類別", 
        "status": "班次狀態",
        "amount_condition": "金額條件",
        "other_conditions": "其他條件"
    }},
    "sql_logic": "對應的SQL邏輯說明",
    "needs_clarification": false,
    "clarification_question": "需要澄清的問題",
    "suggested_actions": ["建議的操作1", "建議的操作2"],
    "reasoning": "詳細的分析推理過程，說明如何用生產線思維理解用戶意圖並選擇命令"
}}"""
    
    def _analyze_with_ai(self, user_input: str, user_id: str) -> Dict:
        """使用Gemini AI分析用戶輸入"""
        try:
            logger.info(f"🤖 使用Gemini分析: {user_input}")
            
            prompt = self._build_ai_prompt(user_input, user_id)  # 🔥 傳遞user_id
            
            generation_config = GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if response.candidates and response.candidates[0].content.parts:
                text_response = response.candidates[0].content.parts[0].text
                
                # 提取JSON
                import re
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    ai_result = json.loads(json_str)
                    logger.info(f"✅ AI分析成功: 信心度={ai_result.get('confidence', 0)}")
                    return ai_result
            
            logger.warning("AI回應格式異常，使用傳統解析")
            return None
            
        except Exception as e:
            logger.error(f"❌ AI分析失敗: {e}")
            return None
    
    def process_user_message(self, user_input: str, user_id: str) -> Dict:
        """智能處理用戶消息 - AI增強版"""
        logger.info(f"🤖 智能助手處理: {user_input}")
        
        # 步驟1: 嘗試AI分析（如果可用）
        ai_result = None
        if self.ai_enabled:
            ai_result = self._analyze_with_ai(user_input, user_id)  # 🔥 傳遞user_id
        
        if ai_result and ai_result.get('confidence', 0) > 0.6:  # 🔥 提高門檻到0.6，避免錯誤解析低質量輸入
            logger.info(f"✅ AI分析成功，信心度: {ai_result['confidence']}")
            
            # AI理解成功，執行標準命令
            if ai_result.get('standard_command'):
                return {
                    "type": "execute_command",
                    "command": ai_result['standard_command'],
                    "original_input": user_input,
                    "confidence": ai_result['confidence'],
                    "ai_reasoning": ai_result.get('reasoning', ''),
                    "entities": ai_result.get('entities', {})
                }
        
        # 🔥 新增：處理中等信心度情況（0.3-0.6）- 提供澄清對話
        elif ai_result and 0.3 <= ai_result.get('confidence', 0) <= 0.6:
            logger.info(f"⚠️ AI信心度中等: {ai_result['confidence']}，提供澄清選項")
            return {
                "type": "ai_clarification_needed",
                "original_input": user_input,
                "confidence": ai_result['confidence'],
                "possible_command": ai_result.get('standard_command', ''),
                "clarification_message": f"🤔 我理解您可能想要：「{ai_result.get('standard_command', '未知操作')}」\n\n是否正確？",
                "ai_reasoning": ai_result.get('reasoning', '')
            }
        
        # 步驟2: AI失敗時，回退到傳統智能解析
        logger.info("回退到傳統智能解析")
        parse_result = parse_user_command(user_input)
        
        if parse_result["success"]:
            logger.info(f"✅ 傳統解析成功: {parse_result['standard_command']}")
            
            # 檢查是否需要上下文引導
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "parsed_command": parse_result,
                    "should_execute_command": False
                }
            else:
                return {
                    "type": "execute_command", 
                    "command": parse_result["standard_command"],
                    "original_input": user_input,
                    "confidence": parse_result["confidence"]
                }
        else:
            # 完全無法理解，提供一般性建議
            logger.info(f"❓ 無法理解，提供一般性建議")
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "should_execute_command": False
                }
            else:
                return {
                    "type": "general_suggestion",
                    "suggestions": self._get_intelligent_suggestions(user_input),
                    "original_input": user_input
                }
    
    def _get_intelligent_suggestions(self, user_input: str) -> list:
        """根據用戶輸入提供智能建議"""
        suggestions = [
            "💡 嘗試說「東洋班次」查看班次",
            "💡 嘗試說「今天診所班次」查看診所安排", 
            "💡 嘗試說「匯入固定班次 本週」匯入班次",
            "💡 輸入「幫助」查看完整功能列表"
        ]
        
        # 根據關鍵詞提供相關建議
        if any(word in user_input for word in ['查', '看', '查詢']):
            suggestions.insert(0, "💡 嘗試更具體：「今天東洋班次」或「司機123今天班次」")
        elif any(word in user_input for word in ['匯入', '導入', '固定']):
            suggestions.insert(0, "💡 嘗試：「匯入固定班次 本週」或「匯入固定班次 下週」")
        elif any(word in user_input for word in ['司機', '指派']):
            suggestions.insert(0, "💡 嘗試：「指派司機 [班次ID] [司機編號]」")
            
        return suggestions[:3]
    
    def format_smart_response(self, process_result: Dict) -> str:
        """格式化智能回應"""
        response_type = process_result["type"]
        
        if response_type == "ai_clarification":
            return f"""🤖 AI需要澄清

💬 「{process_result['original_input']}」
❓ {process_result['question']}

💡 建議：
{chr(10).join(f"• {action}" for action in process_result.get('suggestions', []))}

信心度：{process_result.get('confidence', 0):.1%}"""
            
        elif response_type == "ai_clarification_needed":
            return f"""🤔 AI需要確認

💬 您的輸入：「{process_result['original_input']}」
{process_result['clarification_message']}

💡 如果不正確，請嘗試更明確的表達方式
📊 AI信心度：{process_result.get('confidence', 0):.1%}"""
            
        elif response_type == "smart_guidance":
            return self._format_guidance_response(process_result["guidance"])
            
        elif response_type == "general_suggestion":
            suggestions = process_result.get("suggestions", [])
            return f"""🤔 我無法理解您的請求

💬 「{process_result['original_input']}」

{chr(10).join(suggestions)}"""
            
        elif response_type == "execute_command":
            ai_info = ""
            if "ai_reasoning" in process_result:
                ai_info = f"\n🧠 AI理解：{process_result['ai_reasoning']}"
            
            return f"✅ 理解您的請求{ai_info}\n正在執行：{process_result['command']}"
            
        else:
            return "❓ 抱歉，我無法理解您的請求。"
    
    def _format_guidance_response(self, guidance: Dict) -> str:
        """格式化引導回應"""
        guidance_text = guidance.get("message", "")
        if guidance.get("options"):
            guidance_text += "\n\n" + "\n".join(f"• {option}" for option in guidance["options"])
        return guidance_text

# 全域實例
smart_assistant = SmartAssistant()

def process_with_smart_assistant(user_input: str, user_id: str) -> Dict:
    """使用真正的AI智能助手處理用戶消息"""
    return smart_assistant.process_user_message(user_input, user_id)

def format_smart_response(process_result: Dict) -> str:
    """格式化智能回應的便捷函數"""
    return smart_assistant.format_smart_response(process_result) 
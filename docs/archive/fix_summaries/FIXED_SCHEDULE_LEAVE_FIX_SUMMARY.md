# 固定班次請假功能修復總結

## 問題描述
用戶點擊「固定班次#17請假」按鈕後，輸入「測試 -0」，系統回應「找不到ID為 17 的固定班次」，儘管：
1. 用戶能看到班次#17並點擊按鈕（說明資料庫中存在該記錄）
2. 系統應該正確設置上下文
3. 查詢邏輯在 `fixed_schedule_query_handler.py` 和 `fixed_schedule_leave_handler.py` 中基本相同

## 根本原因分析
經過詳細代碼分析，發現問題在於**上下文管理邏輯錯誤**：

### 1. 原有錯誤邏輯
```python
# 在 text_message_handler.py 中
conversation_manager.set_leave_mode(user_id=user_id, trip_id=int(schedule_id))  # ❌ 錯誤
```

`set_leave_mode()` 函數原先只接受 `trip_id` 參數，但固定班次的ID不是普通班次的ID。

### 2. 上下文查詢問題
```python
# 在簡單請假格式處理中
recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(user_id)
```

`get_recent_fixed_schedule_id()` 函數只從 `recent_fixed_schedule_ids` 字典中查找，沒有檢查 `leave_modes` 中的固定班次ID。

## 修復方案

### 1. 修改 `ConversationManager.set_leave_mode()` 函數
**文件**: `modules/utils/conversation_context.py`

```python
def set_leave_mode(self, user_id: str, trip_id: int = None, fixed_schedule_id: int = None):
    """設定用戶進入請假模式"""
    if trip_id is None and fixed_schedule_id is None:
        logger.error(f"設定請假模式時必須提供 trip_id 或 fixed_schedule_id")
        return
        
    self.leave_modes[user_id] = {
        'trip_id': trip_id,
        'fixed_schedule_id': fixed_schedule_id,  # 🔥 新增
        'timestamp': time.time()
    }
    
    if trip_id:
        logger.info(f"用戶 {user_id} 進入普通班次請假模式，班次ID: {trip_id}")
    elif fixed_schedule_id:
        logger.info(f"用戶 {user_id} 進入固定班次請假模式，固定班次ID: {fixed_schedule_id}")
```

### 2. 修改 `get_recent_fixed_schedule_id()` 函數
**文件**: `modules/utils/conversation_context.py`

```python
def get_recent_fixed_schedule_id(self, user_id: str) -> Optional[int]:
    """獲取用戶最近操作的固定班次ID，優先使用leave_mode中的ID"""
    # 🔥 修復：優先從請假模式中獲取固定班次ID
    if user_id in self.leave_modes:
        mode_data = self.leave_modes[user_id]
        # 檢查時效性
        if time.time() - mode_data['timestamp'] <= 300:  # 5分鐘內有效
            fixed_schedule_id = mode_data.get('fixed_schedule_id')
            if fixed_schedule_id:
                return fixed_schedule_id
    
    # 回退到普通記錄
    return self.recent_fixed_schedule_ids.get(user_id)
```

### 3. 修正按鈕點擊處理
**文件**: `modules/handlers/text_message_handler.py`

```python
# 🔧 修正：設置請假模式標記，正確使用 fixed_schedule_id 參數
conversation_manager.set_leave_mode(user_id=user_id, fixed_schedule_id=int(schedule_id))
```

### 4. 加強日誌記錄
在以下文件中加入詳細的調試日誌：
- `modules/handlers/text_message_handler.py`
- `modules/handlers/fixed_schedule_leave_handler.py`

## 預期效果

修復後的流程：
1. 用戶點擊「固定班次#17請假」按鈕
2. 系統正確設置 `leave_modes[user_id]['fixed_schedule_id'] = 17`
3. 用戶輸入「測試 -0」
4. 簡單請假格式檢測通過
5. `get_recent_fixed_schedule_id()` 正確返回 17
6. 構造命令：`固定班次請假 17 -0 測試`
7. 資料庫查詢成功找到ID=17的固定班次
8. 成功處理請假請求

## 測試建議

1. 重啟應用
2. 用戶執行「固定班表 萬年七街」查詢
3. 點擊「設定班次#17請假」按鈕
4. 輸入「測試 -0」
5. 檢查是否成功處理，而不是報告「找不到ID」錯誤

## 重要文件清單

- ✅ `modules/utils/conversation_context.py` - 上下文管理核心修復
- ✅ `modules/handlers/text_message_handler.py` - 按鈕處理和簡單格式處理
- ✅ `modules/handlers/fixed_schedule_leave_handler.py` - 加強日誌記錄
- ✅ `modules/handlers/fixed_schedule_query_handler.py` - 按鈕生成（無需修改）
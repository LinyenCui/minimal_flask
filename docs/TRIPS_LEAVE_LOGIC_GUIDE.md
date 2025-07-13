# trips 班次請假功能邏輯說明

## 🎯 核心架構原則

### **統一邏輯**：所有進入 trips 表的班次都遵循相同的生命週期和邏輯

---

## 📋 完整架構說明

### **1. 固定班次表 (fixed_schedules)**

**作用**：只是匯入 trips 表時的**模板和依據**，不參與實際班次執行流程

#### 欄位說明：
- `status`：只作為匯入依據
  - `"準備"`：匯入時設為正常狀態
  - `"請假"`：匯入時設為請假狀態
- `note`：請假原因（當 status = "請假" 時）
- `surcharge`：加成金額（可能為負值）

#### 請假流程：
1. 用戶通過「固定班次請假」功能修改 fixed_schedules
2. 設定 `status = "請假"`、`note = "請假原因"`、`surcharge = -30`
3. **不影響已匯入的 trips 班次**

---

### **2. trips 表（核心執行表）**

**作用**：實際的班次執行和管理，所有班次都在此表進行操作

#### ✅ **統一邏輯原則**：

**無論班次來源**（固定班次匯入 或 直接在trips請假），**都遵循相同邏輯**：

1. **status 欄位**：
   - 永遠保持業務流程狀態：`待派` → `準備` → `已完成`
   - **請假不改變 status**，請假班次的 status 仍是 `準備`

2. **請假表示**：
   - `passenger_leave_reason`：請假原因（障眼法）
   - `extra_fare`：請假時的加成（通常為負值）

3. **顯示邏輯**：
   - 有 `passenger_leave_reason` → 顯示「請假（原因）」
   - 無 `passenger_leave_reason` → 顯示原始 status

#### **完整生命週期**：

```
匯入/創建 → [待派] → [準備] → (執行時間到) → 寫入completed_trips → [已完成]
```

**請假班次**：
```
[準備] + passenger_leave_reason → 顯示「請假（原因）」
↓ (執行時間到)
寫入 completed_trips（含請假原因和負加成）→ [已完成]
```

---

### **3. 匯入邏輯（import_handler.py）**

#### **修正後的邏輯**：

```python
# 檢查固定班次的狀態
if fixed_schedules.status == '請假' and fixed_schedules.note:
    # 匯入為請假班次
    trips.status = '準備'                          # 業務狀態
    trips.passenger_leave_reason = fixed_schedules.note  # 請假原因
    trips.extra_fare = fixed_schedules.surcharge         # 負加成
else:
    # 匯入為正常班次
    trips.status = '準備'
    trips.passenger_leave_reason = NULL
    trips.extra_fare = fixed_schedules.surcharge
```

#### **重要原則**：
- ✅ 所有匯入的班次 `status` 都設為「準備」
- ✅ 請假狀態通過 `passenger_leave_reason` 表示
- ✅ 請假班次一樣會正常執行流程，寫入 completed_trips

---

### **4. 請假功能（passenger_leave_handler.py）**

#### **直接在 trips 表請假**：

```python
# 不改變 status，只設定請假標記
UPDATE trips SET 
    passenger_leave_reason = '請假原因',
    extra_fare = -30
WHERE trip_id = xxx
# status 保持原值（通常是「準備」）
```

#### **改回準備**：

```python
# 清除請假標記，不改變 status
UPDATE trips SET 
    passenger_leave_reason = NULL,
    extra_fare = 0
WHERE trip_id = xxx
# status 保持原值
```

---

### **5. 顯示邏輯（passenger_leave_handler.py: get_display_status）**

```python
def get_display_status(trip):
    if trip.passenger_leave_reason:
        return f"請假 ({trip.passenger_leave_reason})"
    elif trip.modification_reason and "乘客請假" in trip.modification_reason:
        return f"請假 ({extract_reason(trip.modification_reason)})"
    else:
        return trip.status  # 原始業務狀態
```

---

### **6. Quick Reply 按鈕邏輯（trip_details_flex.py）**

```python
# 基於顯示狀態判斷，不是基於 status 欄位
display_status = get_display_status(trip)
main_status = display_status.split()[0]  # "請假" 或 "準備" 等

if main_status == "請假":
    # 請假狀態：只顯示「改回準備」
    buttons = ["🟢 改回準備"]
elif trip.status != "完成":
    # 非請假狀態：顯示正常按鈕
    buttons = ["🟢 改回準備", "❌ 取消", "⚠️ 衝突", "🔵 請假"]
```

---

### **7. completed_trips 寫入邏輯**

#### **所有班次**（包括請假班次）**都會正常寫入 completed_trips**：

```python
# 執行時間到時，無論是否請假都寫入
INSERT INTO completed_trips 
SELECT *, passenger_leave_reason, modification_reason 
FROM trips 
WHERE status = '準備' AND datetime < now()

# trips 狀態更新為「已完成」
UPDATE trips SET status = '已完成' WHERE ...
```

---

## 🔥 關鍵重點總結

### **1. 統一原則**
- **所有進入 trips 的班次都遵循相同邏輯**
- **請假不是狀態，是屬性**

### **2. status 欄位的作用**
- **只表示業務流程狀態**：待派 → 準備 → 已完成
- **不表示請假狀態**

### **3. 請假表示方式**
- **passenger_leave_reason**：主要請假標記
- **modification_reason**：向下兼容的請假標記
- **顯示邏輯**：有請假標記就顯示「請假（原因）」

### **4. 匯入邏輯**
- **fixed_schedules.status** 只是模板依據
- **匯入到 trips 後就遵循 trips 的統一邏輯**

### **5. 執行流程**
- **請假班次依然會執行**：寫入 completed_trips，狀態變為已完成
- **只是在車資上有影響**（負加成）

---

## ⚠️ 注意事項

1. **不要再基於 trips.status 判斷請假狀態**
2. **請假功能不要改變 trips.status**
3. **所有顯示邏輯都要使用 get_display_status()**
4. **匯入邏輯必須統一設定 status = '準備'**

---

## 📅 最後更新
**日期**：2025-01-15  
**原因**：統一 trips 班次邏輯，修正固定班次匯入不一致問題  
**影響文件**：
- `modules/handlers/import_handler.py`：修正一周匯入邏輯
- `handlers/trip_handler.py`：修正單日匯入邏輯  
- `modules/handlers/passenger_leave_handler.py`：請假功能邏輯
- `modules/flex_designs/trip_details_flex.py`：Quick Reply按鈕邏輯
- `modules/handlers/trip_status_handler.py`：改回準備功能邏輯 
# Render Production /drug 功能實測與驗收報告

- 測試時間：2026-05-25
- 測試環境：**Render PRODUCTION**（`dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com / dispatch_system_db`）
- 方法（重要）：`/drug` 是 LINE bot 指令，無法在不發送真實 LINE 訊息的情況下直接觸發。為**零副作用**驗證，本測試**以唯讀方式重現 production 的查詢路徑**——完全照 `modules/services/drug_query_service.py` 的 search 與 related-diagnoses SQL，對 production DB 跑相同查詢；並依 `modules/views/drug_flex.py` 的渲染邏輯（健保碼列為條件式 `if item.get("nhi_drug_code")`）判定圖卡顯示。**未發送 LINE 訊息、未 import app（避免觸發 db.create_all）、未寫 DB、未改程式。**
- 結論：**5 項全部通過，無錯誤、無 500，健保碼顯示正確。**

---

## 1. 每個查詢結果摘要

| /drug 查詢 | 命中數 | top / 主要結果（id｜brand｜generic） | nhi_drug_code | 健保碼列 |
|---|---|---|---|---|
| Metformin | 3 | **87**｜Metformin 寬樂醣｜Metformin | **AC585341G0** | ✅ 顯示 |
| | | 5｜Temilg F.C. 甜蜜克｜GLIMEPIRIDE+METFORMIN | AC60134100 | ✅ 顯示 |
| | | 80｜Xigduo 釋多糖持續性｜Dapagliflozin+Metformin | (無) | 正確不顯示 |
| 寬樂醣 | 1 | **87**｜Metformin 寬樂醣｜Metformin | **AC585341G0** | ✅ 顯示 |
| Doxazosin | 2 | 2｜Dophilin 道福寧｜Doxazosin | (無) | 正確不顯示 |
| | | 30｜Doxaben XL 可迅持續錠｜Doxazosin | (無) | 正確不顯示 |
| Bisoprolol | 2 | 1｜Concor 康肯｜Bisoprolol | **BC171251G0** | ✅ 顯示 |
| | | 34｜Biso 百適歐(bisoprolol)｜Bisoprolol | **AB45348100** | ✅ 顯示 |
| Atorvastatin | 2 | 24｜Lipitor 立普妥｜Atorvastatin | **BC22889100** | ✅ 顯示 |
| | | 61｜Atorva 立舒脂(立脂妥)｜Atorvastatin | **AC57805100** | ✅ 顯示 |

### related_diagnoses（drug_diagnosis_links 顯示）
| top 藥品 | 相關診斷 |
|---|---|
| 87 Metformin 寬樂醣 | **E11.9 第2型糖尿病，未伴有併發症**（primary, high）← id198 |
| 2 Dophilin (Doxazosin) | I10 本態性高血壓（medium） |
| 1 Concor (Bisoprolol) | I10 本態性高血壓（primary, high） |
| 24 Lipitor (Atorvastatin) | 高血脂（primary, high） |

---

## 2. 驗收重點對照

| 驗收項目 | 結果 |
|---|---|
| 查詢不應 500 | ✅ 5 項皆正常回傳；查詢邏輯本身包在 try/except（失敗只回 error/empty dict，不丟 500）；drug_items 已存在故不會「relation does not exist」 |
| Metformin / 寬樂醣 找到 drug item 87 | ✅ 兩者 top 命中皆 id=87 |
| Metformin / 寬樂醣 圖卡顯示 AC585341G0 | ✅ id87 nhi_drug_code=`AC585341G0`，健保碼列會顯示 |
| Bisoprolol / Atorvastatin 顯示各自健保碼 | ✅ Concor `BC171251G0`、Biso `AB45348100`、Lipitor `BC22889100`、Atorva `AC57805100` |
| Doxazosin 若無健保碼，不顯示空白健保碼列 | ✅ 兩筆 Doxazosin 皆無 nhi_drug_code；渲染為條件式 `if nhi_drug_code` → **不出現空白健保碼列** |
| drug_diagnosis_links 相關診斷顯示正常 | ✅ 各 top 藥品皆正確帶出相關診斷 |
| E11.9 / 第2型糖尿病 id198 連結正常 | ✅ id198 join 正常；共 **10** 筆 links 指向 id198（含 Metformin 87、TRAJENTA 78、Xigduo 80、胰島素類 125–130 等），無 FK/JOIN 錯誤 |

---

## 3. 是否有錯誤

- **無**。5 項查詢皆成功，無例外、無 500、無 JOIN/FK 錯誤。
- 空健保碼（Doxazosin、Xigduo）行為正確：不顯示空白健保碼列。

## 4. 是否建議修正

- **無需修正**。Tier 1 sync 後 production `/drug` 查詢、健保碼顯示、藥↔診斷連結（含新補的 id198 E11.9）皆正常。
- 建議（非缺陷，加分驗證）：可在 LINE 上實際輸入一次 `/drug 寬樂醣` 做**端到端 round-trip** 最終確認（本報告已驗證 production 資料與查詢/渲染邏輯，唯一未走的是 LINE webhook→bot→使用者訊息這段傳輸）。

---

## 5. 本輪未做（遵守限制）
- 未寫 production DB、未 UPDATE/INSERT/DELETE/TRUNCATE、未改程式、未 git add/commit、未清 backup table、未處理 Tier 2。
- 測試方式為**唯讀重現查詢路徑**，未發送 LINE 訊息、未 import app。

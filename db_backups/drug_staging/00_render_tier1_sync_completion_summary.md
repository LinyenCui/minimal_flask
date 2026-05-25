# Render Production Tier 1 Sync — 完成總結

- 完成日期：2026-05-25
- 範圍：**僅 Tier 1**（drug_items + drug_diagnosis_links + 20 customers，加 1 筆必要 diagnosis_code）。**不含 Tier 2**（official staging 四表 / prescription candidates / mappings）。
- 結果：**成功**（第二次嘗試；第一次因腳本 search_path bug 乾淨 rollback，詳見第 4 節）。
- 腳本：`db_backups/drug_staging/render_tier1_sync_apply.py`（預設 dry-run，本次以 `--apply-confirm --add-missing-diagnosis` 寫入）。
- 本報告為純文件：**未寫資料庫、未改程式、未 DROP 任何表、未 git add/commit。**

---

## 1. Production target（Render，未輸出密碼）

| 項目 | 值 |
|---|---|
| host | dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com |
| database | dispatch_system_db |
| user | dispatch_system_db_user |
| 性質 | **Render PRODUCTION（live 系統）** |

寫入前已硬性確認 target（host 含 render.com 且符指定值、db、user）才允許 apply。

---

## 2. 本次 apply 結果

| 項目 | 結果 | 驗收 |
|---|---|---|
| drug_items 建表 | 成功（含 NHI 五欄，pg_dump 取本地真實 schema） | ✅ |
| drug_items count | **152** | ✅ =152 |
| drug_items.nhi_drug_code filled | **31** | ✅ =31 |
| diagnosis_codes 補 id198 | `(198, 'E11.9', '第2型糖尿病，未伴有併發症')` | ✅ 197→198 |
| drug_diagnosis_links 建表 + 匯入 | **27**（blocked 0） | ✅ =27 |
| customers | **53 → 73** | ✅ +20 |
| 新增 customers id | **104–123** | ✅ |
| trips / completed_trips / fixed_schedules | **未變**（1053 / 1540 / 48，前後一致） | ✅ 未操作 |

- 寫入方式：每層各自 transaction、僅 INSERT（+ 建表/備份）、不 UPDATE/DELETE/TRUNCATE 既有資料、失敗整批 rollback。
- 未寫入欄位：national_id（身分證）、contact_phone（電話）、medical_record_no（病歷號）。
- customers 為 additive INSERT（既有 53 筆 address≠門診 未動）；20 筆 address 統一「門診」、gender M/F、short_name 同 name。

---

## 3. 備份表（暫不 DROP）

| 備份表 | 來源 | 內容 | 處置 |
|---|---|---|---|
| `customers_render_tier1_backup_20260525_103328` | 第一次（失敗）嘗試前建立 | customers 53 筆快照 | **無害，暫保留** |
| `customers_render_tier1_backup_20260525_103837` | 第二次（成功）嘗試前建立 | customers 53 筆快照 | 保留作還原安全網 |

> 兩個皆為 customers 寫入前的 53 筆快照。`103328` 來自第一次 rollback 嘗試（當時尚未寫任何資料），純屬無害遺留。**本輪不 DROP**；是否清理多餘者日後另行授權。

---

## 4. 第一次失敗與修正

- **錯誤**：`psycopg2.errors.UndefinedTable: relation "drug_items" does not exist`（INSERT 階段）。
- **根因**：`pg_dump`(16) 產生的 schema DDL 內含 `SELECT pg_catalog.set_config('search_path','',false);`，執行後把 session 的 search_path 清空，導致後續未加 schema 前綴的 `INSERT INTO drug_items` 找不到表（表其實已建為 `public.drug_items`）。
- **Layer 1 rollback 乾淨**：CREATE + INSERT 在同一未 commit 的交易內，例外後連線結束 → 自動回滾，drug_items 未殘留；Layer 2/3 未執行。回滾後 prod 驗證：drug_items / drug_diagnosis_links 不存在、customers=53、diagnosis_codes=197（id198=0）、live 表不變。**未自行 DELETE/TRUNCATE/DROP 修資料。**
- **修正**（`render_tier1_sync_apply.py`）：
  1. `pg_dump_schema()` 剝除 `set_config('search_path'…)` 行；
  2. 每次執行 DDL 後 `SET search_path TO public`（並於開連線時先設一次）；
  3. sequence 對齊改為 null-safe `reset_seq()`。
- **第二次成功**：`drug_items=152 / nhi=31 / links=27 / blocked=0 / customers_added=20`。

---

## 5. 新增 customers 清單（id / name）

| id | name | id | name |
|---|---|---|---|
| 104 | 孫美玲 | 114 | 蔡海同 |
| 105 | 張王梅香 | 115 | 邱蔡碧花 |
| 106 | 張碧娟 | 116 | 陳月秀 |
| 107 | 曹秀美 | 117 | 黃朝榮 |
| 108 | 朱月滿 | 118 | 湯喬登 |
| 109 | 李秀美 | 119 | 盧蕭秋柑 |
| 110 | 林茂清 | 120 | 鄭昇東 |
| 111 | 楊秀環 | 121 | 高羅祝員 |
| 112 | 湯陳淑蘭 | 122 | 黃方貴米 |
| 113 | 王陳美蘭 | 123 | 黃陳玉盆 |

（陳月秀 id116 與既有 陳昭月 不同人，獨立新增；湯喬登 id118 為 OCR「湯春益」人工更正。）

---

## 6. 驗收結果

- Row counts（prod，唯讀查證）：drug_items=152（nhi 31）、diagnosis_codes=198（含新 id198）、drug_diagnosis_links=27、customers=73（既有 53 不變）。
- **live tables 未變**：trips 1053→1053、completed_trips 1540→1540、fixed_schedules 48→48。
- git：0 staged/modified，未 commit。

### /drug 顯示測試建議（下次 redeploy 後或現在即可測）
| 指令 | 預期 |
|---|---|
| `/drug Metformin` | 顯示 Metformin/寬樂醣，健保碼 `AC585341G0` |
| `/drug 寬樂醣` | 同上（id87 主碼 `AC585341G0`） |
| `/drug Doxazosin` | 顯示對應藥品與其主健保碼，無錯誤 |
| `/drug Bisoprolol` | 顯示對應藥品，圖卡正常 |
| `/drug Atorvastatin` | 顯示對應藥品，圖卡正常 |
- 另檢查：查無藥品的 fallback、Flex 圖卡不報錯、藥↔診斷連結（drug_diagnosis_links）顯示正常。

---

## 7. 尚未處理 / 待辦

- **Tier 2 尚未同步**：official_nhi_drug_payment_staging / official_tfda_drug_license_staging / official_tfda_drug_ingredient_staging / official_tfda_atc_staging（合計 ~561 MB）＋ prescription_nhi_drug_code_candidates（235）＋ drug_item_official_code_mappings（31）。這些為治理/參考資料、/drug 執行期不查；要灌入前須先評估 Render 儲存配額。
- **production DB 密碼明文硬編** 於 repo 多支 .py（如 `check_render_database.py`）：屬安全風險，**需另開安全任務**輪替密碼＋改環境變數＋清 git 歷史（已建立背景任務 chip）。
- **多餘備份表清理**：`customers_render_tier1_backup_20260525_103328`（與成功前的 103837）是否保留/清除，日後另行授權（涉及 DROP，本輪不做）。
- **redeploy 後 /drug 實測**：建議照第 6 節逐項驗證。

---

## 本輪未做（遵守限制）
- 未寫 production DB、未 DROP 任何備份表、未修改程式、未 git add/commit、未推 main、未處理 Tier 2、未處理密碼輪替。

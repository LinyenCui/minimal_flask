# Render Production ↔ 本地 全量同步 Preflight Plan（唯讀；未寫 production）

- 產生日期：2026-05-25
- 性質：**唯讀 preflight + migration plan**。本輪只對兩邊資料庫做 SELECT/information_schema 查詢；**未對 production 做任何 ALTER/INSERT/UPDATE/DELETE/TRUNCATE、未建表、未改本地 DB、未改程式、未 git**。
- 連線：local 與 prod 皆以 `set_session(readonly=True)` 開唯讀連線。

## DB targets
| | host | database | user | 標示 |
|---|---|---|---|---|
| local | localhost:5432 | dispatch_db | postgres | 本機開發 |
| **production** | dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com | **dispatch_system_db** | dispatch_system_db_user | **Render PRODUCTION（live）** |

- production 連線：**成功（唯讀）**。它是 live 系統（含 `completed_trips` / `trips` / `fixed_schedules`，public schema 共 19 張表）。
- 密碼來源：硬編在 repo 的 `check_render_database.py`（**未輸出密碼**）。⚠ 見文末「安全提醒」。

---

## 1 & 2. Row counts（唯讀）

| 表 | local | production | 差異 |
|---|---:|---:|---|
| customers | 73 | 53 | prod 少 20（即本地新增的 20 位） |
| drug_items | 152 | **不存在(MISSING)** | prod 無此表 |
| drug_diagnosis_links | 27 | **MISSING** | prod 無此表 |
| official_nhi_drug_payment_staging | 224,261 | **MISSING** | prod 無此表 |
| official_tfda_drug_license_staging | 71,804 | **MISSING** | prod 無此表 |
| official_tfda_drug_ingredient_staging | 125,902 | **MISSING** | prod 無此表 |
| official_tfda_atc_staging | 80,290 | **MISSING** | prod 無此表 |
| prescription_nhi_drug_code_candidates | 235 | **MISSING** | prod 無此表 |
| drug_item_official_code_mappings | 31 | **MISSING** | prod 無此表 |

---

## 3. Schema 差異（重大）

> **與原本預期不同**：原假設「prod 只是缺 drug_items 的 NHI 五欄」。實際上 **prod 完全沒有 `drug_items` 表，也沒有任何 drug/official/prescription/mapping 相關表**。所以不是「ALTER 加欄位」，而是「**整套 drug 子系統都要在 prod 建立**」。

- `drug_items` 的 NHI 五欄（nhi_drug_code / _source / _confidence / _verified_at / _note）：local 有、**prod 沒有**（因為整張表不存在）。
- 4 張 official staging、`prescription_nhi_drug_code_candidates`、`drug_item_official_code_mappings`：**prod 全部不存在**。
- `customers` schema：**local 與 prod 完全一致**（欄位無差異）→ customers 同步是「純資料新增」。
- **prod 無 Alembic**（無 `alembic_version` 表）；app 部署用 `web: python app.py`，啟動時走 `db.create_all()`（`modules/__init__.py`，註解寫明「無 migration，使用 create_all」）。

### /drug 在 prod 的實際風險（重要）
main 重新部署到 Render 時 `db.create_all()` 會跑：
- **若** `drug_items` model 有被註冊到該 `db` → 會**自動建立一張空的 drug_items（含 NHI 欄位）** → `/drug` 不會因「表不存在」崩潰，但因**沒有資料**而查無藥品（圖卡空白/查無）。
- **若** model 未在 create_all 範圍（例如某些查詢走 raw SQL）→ `/drug` 會因 `relation "drug_items" does not exist` **報錯**。
- 兩種情況的共同結論：**prod 一定要把 drug_items 的「資料」匯入** `/drug` 才會真的可用；且不能只靠 create_all（它不會補欄位到既有表、也不會匯資料）。→ 建議**明確建表＋載入資料**，不依賴 create_all 行為。

---

## 4. Data 差異 / 同步範圍

- customers：local-only = **剛好 20 位**（孫美玲、張王梅香、張碧娟、曹秀美、朱月滿、李秀美、林茂清、楊秀環、湯陳淑蘭、王陳美蘭、蔡海同、邱蔡碧花、陳月秀、黃朝榮、湯喬登、盧蕭秋柑、鄭昇東、高羅祝員、黃方貴米、黃陳玉盆）。prod-only = **0**（prod ⊆ local by name）→ 同步＝**additive 新增 20 筆**，prod 既有 53 筆不動。
- drug_items：prod 0 → 需 152 筆（其中 31 筆已填主健保碼，例：Metformin/寬樂醣 id87＝`AC585341G0`）。
- 其餘 drug 表：prod 0 → 視同步層級決定是否匯入（見下「分層建議」）。

### ⚠ 資料量 / 分層建議（強烈建議先讀）
official staging 四表在本地 **約 561 MB**：
| 表 | 大小 | rows |
|---|---|---:|
| official_nhi_drug_payment_staging | 283 MB | 224,261 |
| official_tfda_drug_ingredient_staging | 112 MB | 125,902 |
| official_tfda_drug_license_staging | 110 MB | 71,804 |
| official_tfda_atc_staging | 56 MB | 80,290 |
| （drug_items / links / candidates / mappings 合計 < 1 MB） | | |

這四張是**治理/推導用參考資料，`/drug` 執行期並不查它們**。把 561 MB 灌進 Render production 會吃掉儲存配額、拉長轉移時間，且對 `/drug` 沒有 runtime 幫助。建議分層：

- **Tier 1（runtime 必要，~0.5 MB）**：`drug_items`（含 NHI 欄位＋資料）〔＋ `drug_diagnosis_links` 27 筆，若 /drug 卡片要顯示關聯診斷〕。**這是 /drug 不壞的最小必要集**。
- **Tier 2（治理一致性，~561 MB，可選）**：official staging 四表＋`prescription_nhi_drug_code_candidates`＋`drug_item_official_code_mappings`。**只在你要 prod 與本地完全一致時才做**，且**先確認 Render 方案儲存上限**。
- **customers**：additive 20 筆（Tier 1 一起做即可）。

> 使用者原意是「一次同步到一致（全做）」。以上分層是讓你在知道成本後再決定；下方 apply 順序以「全做」為主、並標明哪些屬 Tier 2 可略。

---

## 5 & 6. 建議 apply 順序（對應你列的 8 步，已依實況修正）

> 機制建議：drug 相關表用 `pg_dump`（local 指定表，schema+data）→ `psql` restore 到 prod（最省事、schema 完全一致）；customers 用「只 INSERT 20 筆」的受控腳本（prod 是 live，**不可整表覆蓋**）。每步單獨交易、可回滾、先 dry-run。

**步驟 0｜備份 production（必做）**
- `pg_dump`（custom format）整庫或至少 customers＋（若已存在）任何同名表：
  `pg_dump "<prod_url>" -Fc -f render_pre_sync_backup_YYYYMMDD_HHMMSS.dump`
- 驗收：備份檔產生、`pg_restore -l` 可列出。

**步驟 1｜建立 + 載入 drug_items（取代你原本的「ALTER」）** 〔Tier 1〕
- 因 prod 無此表 → 不是 ALTER 而是 **CREATE + LOAD**：`pg_dump -t drug_items` (schema+data) local → restore prod。**一步即帶入 NHI 五欄＋152 筆＋31 筆主碼**（你原本的步驟 2「ALTER」與步驟 5「回填 31 筆」自動合併在這裡）。
- rollback：`DROP TABLE drug_items;`（新表，安全）。
- 驗收：`SELECT count(*) FROM drug_items;`→152；`SELECT count(*) FROM drug_items WHERE nhi_drug_code<>'';`→31；NHI 欄位存在；`SELECT brand_name,nhi_drug_code FROM drug_items WHERE id=87;`→ 寬樂醣 / `AC585341G0`。

**步驟 1b｜drug_diagnosis_links** 〔Tier 1，若 /drug 需要〕
- `pg_dump -t drug_diagnosis_links` → restore（27 筆）。rollback：DROP。驗收：count=27。

**步驟 2｜official staging 四表 建 + 載入** 〔Tier 2，可選，~561MB〕
- 先確認 Render 儲存配額足夠；逐表 `pg_dump -t <staging>` → restore。
- rollback：逐表 DROP。驗收：四表 count 與本地一致（224261 / 71804 / 125902 / 80290）。

**步驟 3｜prescription_nhi_drug_code_candidates 建 + 載入 235 筆** 〔Tier 2〕
- rollback：DROP。驗收：count=235。

**步驟 4｜drug_item_official_code_mappings 建 + 載入 31 筆** 〔Tier 2〕
- 注意外鍵：若此表 FK 參考 drug_items，需在步驟 1 之後。rollback：DROP。驗收：count=31。

**步驟 5｜customers 新增 20 筆**（additive，受控）
- 重用本地的 gated 模式（`apply_customer_candidates.py` 改指向 prod、新增 localhost→prod 的目標檢查），preflight：prod count=53、20 名皆不存在（已驗證 prod-only=0、overlap=0）。
- 寫法：單一交易、只 INSERT（name/short_name/address=門診/birthday/gender M/F；id 由 prod sequence；created_at/updated_at 走 default）；先 `CREATE TABLE customers_render_sync_backup_<ts> AS TABLE customers`。
- rollback：刪除本次新增 ids，或還原備份表。驗收：count 53→73；20 名皆在；prod 既有 53 未變。

**步驟 6｜驗收 + redeploy + /drug 測試**（見第 7 節）

> 與你原 8 步的差異：①原「ALTER drug_items」改為「CREATE + LOAD」②原「回填 31 筆」併入步驟 1（pg_dump 連資料一起）③official staging 標為 Tier 2 可選。

---

## 7. Render redeploy 後測試項目

部署 main 後（`/drug` 走 drug_items.nhi_drug_code）逐一測：
1. `/drug Metformin` → 應出現 Metformin/寬樂醣，健保碼 `AC585341G0`。
2. `/drug 寬樂醣` → 同上（id87 主碼 `AC585341G0`）。
3. `/drug Doxazosin` → 應出現對應藥品與其主健保碼（非空白、無錯誤）。
- 另檢查：Flex 圖卡不報錯、查無藥品時的 fallback 正常。

驗收 SQL（prod，唯讀）：
```
SELECT count(*) FROM drug_items;                              -- 152
SELECT count(*) FROM drug_items WHERE nhi_drug_code <> '';    -- 31
SELECT brand_name, nhi_drug_code FROM drug_items WHERE id=87; -- 寬樂醣 | AC585341G0
SELECT count(*) FROM customers;                               -- 73
```

---

## 8. 回報摘要

1. production 可連：**是**（唯讀連線成功）。
2. production schema 是否落後本地：**是，且幅度大**——prod 完全沒有 drug_items 及所有 drug/official/prescription/mapping 表；customers 落後 20 筆。`/drug` 在 prod 目前無資料可用。
3. production row counts：customers=53、其餘 drug 相關全部 MISSING（見第 1 節）。
4. 本報告路徑：`db_backups/drug_staging/00_render_full_db_sync_preflight_plan.md`。
5. 是否可進入 production apply 腳本設計：**可以**，建議照上方修正後順序（含 Tier1/Tier2 抉擇、步驟 0 備份、每步可回滾、customers 用受控 INSERT）。實際 apply 必須是**另一支、預設 dry-run、需 `--apply-confirm`、且加 prod 目標確認**的腳本，並在你明確授權後才執行。

---

## 安全提醒（順帶發現，非本任務範圍）
- production DB 連線密碼**硬編在 repo 多支 .py**（如 `check_render_database.py` 等），屬於版本控管內的明文正式憑證 → 建議**輪替密碼並改用環境變數**。本輪未輸出密碼、未改動這些檔案。

## 本輪未做（遵守限制）
- 未對 production ALTER/INSERT/UPDATE/DELETE/TRUNCATE、未建 prod table、未改本地 DB、未改程式、未 git add/commit、未推 main。
- 唯讀輔助檔（可重複使用）：`db_backups/drug_staging/_sync_preflight_check.py`、`_sync_preflight_detail.py`、`_sync_preflight_customers.py`、`_preflight_result.json`（皆唯讀產物，無密碼）。

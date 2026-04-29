# 本地 PostgreSQL Schema 盤點報告 — Diagnosis / Medication

> **盤點日期**：2026-04-12
> **盤點範圍**：本地 `dispatch_db` 的 `diagnosis%` / `medication%` / `drug%` 相關 schema
> **執行方式**：純唯讀（SELECT + information_schema + pg_catalog）
> **目的**：為未來診斷知識庫擴充（含向量化、醫藥整合）提供基礎資料

---

## 1. 連線資訊確認

| 項目 | 值 |
|------|---|
| `DATABASE_URL`（遮碼） | `postgresql+psycopg://postgres:****@localhost:5432/dispatch_db` |
| `current_database()` | `dispatch_db` |
| `current_user` | `postgres` |
| `inet_server_addr()` | `::1`（IPv6 loopback） |
| `inet_server_port()` | `5432` |

✅ **確認為本地資料庫**（loopback `::1`,非 Render）。

---

## 2. public schema 全部 table(共 17 張,字母排序)

```
account_ledger
chat_settings
clinic_locations
completed_trips
customers
database_maintenance
diagnosis_chapters
diagnosis_code_chapters
diagnosis_code_components
diagnosis_code_notes
diagnosis_codes
drivers
fixed_schedules
group_location_meta
payments
persons
trips
```

⚠️ **重要發現**：**沒有任何 `medication%` 或 `drug%` 的表**,僅存在 5 張 `diagnosis%` 相關表。

---

## 3. diagnosis 相關表的完整欄位

### 3.1 `diagnosis_chapters`(章節主表)

| 欄位 | 型別 | Null | Default |
|------|------|------|---------|
| `id` | integer | NO | `nextval('diagnosis_chapters_id_seq')` |
| `chapter_number` | integer | NO | — |
| `name` | varchar | NO | — |
| `source_photos` | text | YES | — |

### 3.2 `diagnosis_codes`(診斷碼主表 ⭐)

| 欄位 | 型別 | Null | Default |
|------|------|------|---------|
| `id` | integer | NO | `nextval('diagnosis_codes_id_seq')` |
| `icd9_code` | varchar | YES | — |
| `icd10_code` | varchar | YES | — |
| `name_zh` | varchar | NO | — |
| `name_en` | varchar | YES | — |
| `aliases` | text | YES | — |
| `subcategory` | varchar | YES | — |
| `is_high_frequency` | boolean | YES | — |
| `is_handwritten` | boolean | YES | — |
| `is_deprecated` | boolean | YES | — |
| `confidence` | varchar | YES | — |
| `description` | text | YES | — |
| `usage_note` | text | YES | — |
| `additional_codes` | varchar | YES | — |

### 3.3 `diagnosis_code_chapters`(診斷碼 ↔ 章節關聯表)

| 欄位 | 型別 | Null | Default |
|------|------|------|---------|
| `id` | integer | NO | `nextval(...)` |
| `diagnosis_code_id` | integer | NO | — |
| `chapter_id` | integer | NO | — |

### 3.4 `diagnosis_code_components`(組合碼拆解表)

| 欄位 | 型別 | Null | Default |
|------|------|------|---------|
| `id` | integer | NO | `nextval(...)` |
| `combined_code_id` | integer | NO | — |
| `component_code` | varchar | NO | — |
| `component_order` | integer | NO | — |
| `component_name_zh` | varchar | YES | — |

### 3.5 `diagnosis_code_notes`(診斷碼備註表)

| 欄位 | 型別 | Null | Default |
|------|------|------|---------|
| `id` | integer | NO | `nextval(...)` |
| `diagnosis_code_id` | integer | YES | — |
| `chapter_id` | integer | YES | — |
| `note_type` | varchar | YES | — |
| `note_text` | text | NO | — |

---

## 4. Foreign Keys

| table_name | column_name | → foreign_table | foreign_column |
|---|---|---|---|
| `diagnosis_code_chapters` | `chapter_id` | `diagnosis_chapters` | `id` |
| `diagnosis_code_chapters` | `diagnosis_code_id` | `diagnosis_codes` | `id` |
| `diagnosis_code_components` | `combined_code_id` | `diagnosis_codes` | `id` |
| `diagnosis_code_notes` | `chapter_id` | `diagnosis_chapters` | `id` |
| `diagnosis_code_notes` | `diagnosis_code_id` | `diagnosis_codes` | `id` |

---

## 5. Primary Key / Unique / Index

### 5.1 PK / UNIQUE

| table_name | constraint_type | constraint_name | column_name |
|---|---|---|---|
| `diagnosis_chapters` | PRIMARY KEY | `diagnosis_chapters_pkey` | `id` |
| `diagnosis_chapters` | UNIQUE | `diagnosis_chapters_chapter_number_key` | `chapter_number` |
| `diagnosis_code_chapters` | PRIMARY KEY | `diagnosis_code_chapters_pkey` | `id` |
| `diagnosis_code_chapters` | UNIQUE | `uq_dx_code_chapter` | `(diagnosis_code_id, chapter_id)` |
| `diagnosis_code_components` | PRIMARY KEY | `diagnosis_code_components_pkey` | `id` |
| `diagnosis_code_notes` | PRIMARY KEY | `diagnosis_code_notes_pkey` | `id` |
| `diagnosis_codes` | PRIMARY KEY | `diagnosis_codes_pkey` | `id` |

### 5.2 pg_indexes

| tablename | indexname | indexdef |
|---|---|---|
| `diagnosis_chapters` | `diagnosis_chapters_chapter_number_key` | UNIQUE btree (`chapter_number`) |
| `diagnosis_chapters` | `diagnosis_chapters_pkey` | UNIQUE btree (`id`) |
| `diagnosis_code_chapters` | `diagnosis_code_chapters_pkey` | UNIQUE btree (`id`) |
| `diagnosis_code_chapters` | `uq_dx_code_chapter` | UNIQUE btree (`diagnosis_code_id, chapter_id`) |
| `diagnosis_code_components` | `diagnosis_code_components_pkey` | UNIQUE btree (`id`) |
| `diagnosis_code_notes` | `diagnosis_code_notes_pkey` | UNIQUE btree (`id`) |
| `diagnosis_codes` | `diagnosis_codes_pkey` | UNIQUE btree (`id`) |
| `diagnosis_codes` | `ix_diagnosis_codes_icd10_code` | btree (`icd10_code`) |
| `diagnosis_codes` | `ix_diagnosis_codes_icd9_code` | btree (`icd9_code`) |

---

## 6. Row Count

| table_name | row_count |
|---|---|
| `diagnosis_chapters` | **9** |
| `diagnosis_codes` | **197** |
| `diagnosis_code_chapters` | **203** |
| `diagnosis_code_components` | **6** |
| `diagnosis_code_notes` | **32** |

---

## 7. 結論

### Q1:diagnosis 主表是哪張?
→ **`diagnosis_codes`**(197 筆),是整個診斷系統的核心實體表。

### Q2:主鍵是什麼?
→ 代理鍵 `id`(integer,auto-increment via `diagnosis_codes_id_seq`)。**沒有**對 `icd9_code` / `icd10_code` 設 UNIQUE 約束,僅建了一般 btree 索引。

### Q3:ICD-9 / ICD-10 怎麼存?
- 兩者同時存在於 `diagnosis_codes` 的 **兩個獨立欄位**:`icd9_code` (varchar, nullable) 與 `icd10_code` (varchar, nullable)。
- 兩欄皆 nullable,表示一筆診斷可能只有 ICD-9、只有 ICD-10、或兩者都有。
- 兩欄各自有一般索引 (`ix_diagnosis_codes_icd9_code`、`ix_diagnosis_codes_icd10_code`) 支援查找,但**未設 UNIQUE**,理論上允許重複。
- 另有 `additional_codes` (varchar) 欄位存補充碼;組合碼的拆解則由 `diagnosis_code_components` 處理(`combined_code_id` → `component_code` 有序列表)。

### Q4:有沒有 medication 主表?
→ **沒有**。整個 public schema 不存在任何 `medication%` 或 `drug%` 表。目前這個資料庫**完全沒有藥物主檔**。

### Q5:有沒有 diagnosis 和 medication 的關聯表?
→ **沒有**。因為 medication 端本身不存在,自然也沒有 `diagnosis_medication` / `dx_drug` 類關聯表。`diagnosis_codes` 目前只和 `diagnosis_chapters`(章節分類)、`diagnosis_code_notes`(備註)、`diagnosis_code_components`(組合碼拆解)關聯。

### Q6:哪些欄位適合未來做向量化預留?
以語義檢索/相似診斷比對的價值排序:

| 優先級 | 表.欄位 | 理由 |
|---|---|---|
| ⭐⭐⭐ | `diagnosis_codes.name_zh` | 中文病名,主要檢索入口 |
| ⭐⭐⭐ | `diagnosis_codes.aliases` | 同義詞/別名,語義檢索關鍵來源 |
| ⭐⭐⭐ | `diagnosis_codes.description` | 描述長文,最適合 embedding |
| ⭐⭐ | `diagnosis_codes.name_en` | 英文病名,跨語查找 |
| ⭐⭐ | `diagnosis_codes.usage_note` | 使用註記,含語義情境 |
| ⭐⭐ | `diagnosis_code_notes.note_text` | 備註長文,可按 `note_type` 分類向量化 |
| ⭐ | `diagnosis_chapters.name` | 章節名稱,粒度較粗,可做粗分類向量 |

建議做法是**新增一張 `diagnosis_code_embeddings` 附表**(包含 `diagnosis_code_id`, `source_field`, `embedding vector(n)`, `model_version`, `updated_at`),而非在 `diagnosis_codes` 主表直接加 vector 欄位,方便多模型／多欄位並存。(**僅為建議,尚未實作。**)

---

## 8. 觀察到的設計問題(僅描述,未修改)

1. **ICD-9 / ICD-10 未設 UNIQUE 約束**:`ix_diagnosis_codes_icd9_code`、`ix_diagnosis_codes_icd10_code` 都是普通 btree,不是 unique。理論上可能出現重複碼,匯入時需靠應用層自行去重。
2. **`diagnosis_code_notes` 的 `diagnosis_code_id` 與 `chapter_id` 皆 nullable**:一筆 note 可能兩邊都為 null,成為孤立記錄;缺少 CHECK 約束確保「兩者至少擇一」。
3. **`diagnosis_code_chapters` 的存在暗示「一個診斷碼可歸屬多章節」**(多對多),但 `diagnosis_codes` 自身沒有 `primary_chapter_id`,需要應用層決定「主章節」。
4. **`aliases` 存 text(非 JSON/array)**:可能是分隔字串,查詢時需 `LIKE` 或 `split`,效能與正規化程度不佳;對未來向量化反而是中性(可直接整段 embed)。
5. **`completed_trips` / `trips` / `customers` 與 diagnosis 系統之間沒有任何 FK**:代表目前「病人診斷」與「班次」是斷開的——派班系統和診斷知識庫尚未整合。若未來要做「依診斷建議路線/車型」,需要新增關聯(例如 `customers.primary_diagnosis_id` 或 `customer_diagnoses` 關聯表)。
6. **完全沒有藥物資料模型**:若後續業務要支援「洗腎/化療/特殊用藥提醒」,整個 medication 層(主表、劑量、頻率、病人用藥關聯)都需要從零設計。

---

## 附錄:本次盤點使用的唯讀 SQL

```sql
-- 步驟 0:確認連線
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();

-- 步驟 1:列出 public schema 所有 table
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 步驟 2:欄位清單
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (table_name LIKE 'diagnosis%'
    OR table_name LIKE 'medication%'
    OR table_name LIKE 'drug%')
ORDER BY table_name, ordinal_position;

-- 步驟 3:Foreign Keys
SELECT tc.table_name, kcu.column_name,
       ccu.table_name  AS foreign_table_name,
       ccu.column_name AS foreign_column_name,
       tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema    = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema    = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND (tc.table_name LIKE 'diagnosis%'
    OR tc.table_name LIKE 'medication%'
    OR tc.table_name LIKE 'drug%')
ORDER BY tc.table_name, kcu.column_name;

-- 步驟 4a:PK / UNIQUE
SELECT tc.table_name, tc.constraint_type, tc.constraint_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema    = kcu.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
  AND (tc.table_name LIKE 'diagnosis%'
    OR tc.table_name LIKE 'medication%'
    OR tc.table_name LIKE 'drug%')
ORDER BY tc.table_name, tc.constraint_type, kcu.ordinal_position;

-- 步驟 4b:pg_indexes
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND (tablename LIKE 'diagnosis%'
    OR tablename LIKE 'medication%'
    OR tablename LIKE 'drug%')
ORDER BY tablename, indexname;

-- 步驟 5:Row count
SELECT 'diagnosis_chapters'        AS table_name, COUNT(*) FROM diagnosis_chapters
UNION ALL SELECT 'diagnosis_codes',            COUNT(*) FROM diagnosis_codes
UNION ALL SELECT 'diagnosis_code_chapters',    COUNT(*) FROM diagnosis_code_chapters
UNION ALL SELECT 'diagnosis_code_components',  COUNT(*) FROM diagnosis_code_components
UNION ALL SELECT 'diagnosis_code_notes',       COUNT(*) FROM diagnosis_code_notes
ORDER BY table_name;
```

---

**盤點完成,本報告僅為現況描述,未對資料庫或程式碼做任何修改。**

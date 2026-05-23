# 處方照片健保藥品代碼專項流程設計

## 本階段目的

使用者指出處方照片左側每列藥品旁有健保藥品代碼，例如 `AC415191G0`、`AC58316100`。先前 OCR/Gemini 標準化流程主要處理藥名，沒有把這些健保藥品代碼結構化保存進 `drug_items` 或 `drug_items_staging`。

本文件只做流程設計與 schema 草案說明，不 OCR 圖片、不修改圖片、不寫資料庫、不建立 table、不產生 apply SQL。

## 檔案 Inventory

| 路徑 | 檔案數 | 圖片檔數 | CSV/MD/JSON/TXT | 是否可能包含 31 張處方照片 | 是否已有 OCR 結果 | 是否已有健保碼欄位 |
|---|---:|---:|---:|---|---|---|
| `/Users/linyancui/zhensuo/處方照片` | 31 | 30 | 0 | 是，原始處方照片資料夾；另有 `.DS_Store` | 否 | 否 |
| `/Users/linyancui/zhensuo/workbench/prescription_photos` | 48 | 30 | 16 | 是，工作副本/轉檔與報告資料夾 | 是 | 無獨立健保碼欄位 |
| `/Users/linyancui/zhensuo/workbench/prescription_photos/original_inventory` | 1 | 0 | 1 | 盤點 30 張來源照片 | 否 | 否 |
| `/Users/linyancui/zhensuo/workbench/prescription_photos/ocr_raw` | 4 | 0 | 2 | 否，OCR 結果 | 是：`prescription_examples_raw.csv`, `prescription_examples_gemini.csv` | 無獨立健保碼欄位；健保碼混在 `drug_names_raw` / `brand_names_raw` |
| `/Users/linyancui/zhensuo/workbench/prescription_photos/review_reports` | 13 | 0 | 13 | 否，review 報告 | 是 | 無獨立健保碼欄位；部分文字已出現健保碼候選 |
| `/Users/linyancui/zhensuo/workbench/drug_reference_gemini_standardized.csv` | 173 rows | - | CSV | 否，藥名表格標準化 | 是 | 否 |

## 已找到的既有 OCR 結果

- `prescription_examples_raw.csv`：30 rows，有 `drug_names_raw`、`generic_names_raw`、`brand_names_raw`、`dosage_raw`、`days_raw` 等欄位。
- `prescription_examples_gemini.csv`：30 rows，有類似欄位。
- `drug_alias_candidates_from_prescriptions.csv`：15 rows，其中 `raw_drug_text` 已出現類似 `AC415191G0 ELUPINE TABLETS 0.25`、`AC58534L00 METROPMIN F.C. TABLE`。
- 多份 review markdown 已列出健保碼樣式片段，例如 `AC415191G0`、`BC21571100`、`AC57805100`。

重要結論：目前已有 OCR 文字中「看得到」健保碼，但沒有被拆成 `nhi_drug_code` 欄位，也沒有與官方 NHI staging 或 `drug_items` 建立結構化關係。

## 健保碼格式觀察

照片與既有 OCR 文字中的健保碼常見格式：

- `AC415191G0`
- `AC58316100`
- `BC21571100`
- `AC57805100`
- `AB58075100`

風險：OCR 會把 `0/O`、`1/I/L`、`G/6` 混淆，例如 `BC171251GO` 可能應為 `BC171251G0`。

## 專項 Staging 流程

### Step 1：只抽健保碼候選

輸入來源：

- 原始照片：`/Users/linyancui/zhensuo/處方照片`
- 工作副本：`/Users/linyancui/zhensuo/workbench/prescription_photos`
- 既有 OCR raw CSV：`prescription_examples_raw.csv`, `prescription_examples_gemini.csv`

第一階段建議先不用重新 OCR 全圖，而是從既有 OCR raw 文字用 regex 抽候選，再人工補漏：

- regex 候選：`[A-Z]{1,2}[0-9A-Z]{8}` 或更嚴格以 official NHI `normalized_drug_code` 做校正。
- 保存原始片段，不直接修正 OCR 錯字。
- 每張照片、每列藥品建立一筆 candidate。

### Step 2：人工 review

每筆候選需要人工確認：

- 健保碼是否讀對。
- 該健保碼是否和同列藥名對應。
- 是否為 OCR 把上下列混在一起。
- 是否需要回原圖確認。

### Step 3：join official NHI staging

Join 條件：

```text
prescription_nhi_drug_code_candidates.normalized_nhi_drug_code
= official_nhi_drug_payment_staging.normalized_drug_code
```

注意：

- `official_nhi_drug_payment_staging` 是歷史給付列，同一 code 理論上是唯一代號，但仍需處理有效起迄日、停用/變更狀態。
- 若同一 `normalized_drug_code` 有多列或歷史列，review report 應全部列出，不可直接重複建立 `drug_items`。
- 應優先顯示目前有效列；但保留歷史資訊作佐證。

### Step 4：產生 drug_items mapping candidates

不要直接把健保碼寫入 `drug_items.aliases`。

建議產生候選：

- `drug_item_id`
- NHI code
- official NHI row
- match_method：`exact_code_from_prescription`, `code_plus_name_match`, `code_only_needs_review`
- confidence
- review_status

### Step 5：approved-only apply

人工核准後，寫入正式 mapping table：`drug_item_official_code_mappings`。

## Staging Table 草案：prescription_nhi_drug_code_candidates

用途：保存從處方照片/OCR 文字抽出的健保藥品代碼候選。這是 raw/review staging，不是正式 mapping。

核心欄位：

- `source_photo`：原始照片檔名。
- `source_photo_page_or_index`：若未來有 PDF/多頁，保存頁碼或圖片序號。
- `source_row_number`：照片中藥品列序。
- `raw_nhi_drug_code`：OCR 原始讀值。
- `normalized_nhi_drug_code`：標準化後值，例如移除空白、全大寫、常見 OCR 校正前後需保留。
- `raw_drug_name_text`、`raw_dosage_text`、`raw_frequency_text`、`raw_days_text`：同列文字。
- `ocr_method`、`confidence`：來源方法與信心。
- `review_status`、`review_decision`：人工審核狀態。

## Formal Mapping Table 草案：drug_item_official_code_mappings

用途：正式保存 `drug_items` 與官方代碼的關係，可支援 NHI、TFDA license、ATC。

不建議直接新增 `drug_items.nhi_drug_code` 作唯一欄位，原因：

- 一個診所品項可能對應多個官方碼或不同劑型/規格。
- NHI 代碼有給付歷史、有效起迄與停用狀態。
- TFDA license / ATC 也是官方碼，未來需要同一套 mapping 機制。

## 與 official_nhi_drug_payment_staging 的 Join 設計

```text
candidate.normalized_nhi_drug_code = official_nhi_drug_payment_staging.normalized_drug_code
```

Review report 應列出：

- raw / normalized NHI code
- official drug name zh/en
- ingredient
- spec amount/unit
- dosage form
- supplier / manufacturer
- ATC
- effective_start_date / effective_end_date
- source_photo
- raw row text

## 不要做的事

- 不要把健保碼直接塞進 `aliases`。
- 不要因同一健保碼找到 official row 就自動建立或覆蓋 `drug_items`。
- 不要把 OCR 低信心碼直接 apply。
- 不要混入 diagnosis / ICD 流程。

## 建議下一步

1. 先從既有 `prescription_examples_raw.csv` / `prescription_examples_gemini.csv` 抽健保碼候選，不重新 OCR。
2. 產出 `prescription_nhi_drug_code_candidates.csv` 離線候選檔。
3. 用 official NHI staging 做 code exact join，產出 review report。
4. 人工確認後，才考慮建立 staging table 並匯入。
5. 再設計 `drug_item_official_code_mappings` 的 approved-only apply 流程。

## 安全聲明

本文件不修改資料庫、不建立 table、不 OCR 圖片、不修改圖片、不修改 `drug_items` / `drug_items_staging` / official staging。

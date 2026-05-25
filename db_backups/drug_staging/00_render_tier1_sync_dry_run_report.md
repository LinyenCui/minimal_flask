# Render Tier 1 Sync — DRY-RUN 報告（未寫 production）

- 產生：2026-05-25 09:13:09
- PROD target：dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com / dispatch_system_db / dispatch_system_db_user（PRODUCTION，render.com）
- 範圍：Tier 1（A drug_items / B drug_diagnosis_links / C customers 20）；不做 Tier 2。
- **本輪未對 production 或 local 做任何寫入**（read-only）。

## Row counts (local | prod)
| table | local | prod |
|---|---:|---:|
| drug_items | 152 | MISSING |
| drug_items.nhi_drug_code filled | 31 | (n/a) |
| drug_diagnosis_links | 27 | MISSING |
| customers | 73 | 53 |

## Planned schema actions
- CREATE `drug_items`（29 欄，apply 用 `pg_dump --schema-only` 從本地取得，含 NHI 五欄）：
  - id, seq_no, table_type, supplier, manufacturer, generic_name, brand_name, aliases, is_high_frequency, highlight_color, highlight_meaning, handwritten_note, note_confidence, note_type, item_kind, category, needs_manual_check, source_photo, source_version, staging_import_batch_id, staging_row_id, is_active, created_at, updated_at, nhi_drug_code, nhi_drug_code_source, nhi_drug_code_confidence, nhi_drug_code_verified_at, nhi_drug_code_note
- CREATE `drug_diagnosis_links`（12 欄；FK→drug_items, diagnosis_codes）：
  - id, drug_item_id, diagnosis_code_id, link_type, role_type, confidence, is_primary, sort_order, source_type, note_text, created_at, updated_at
- `customers`：不改 schema，只 additive INSERT。

## Planned insert counts
- A. drug_items：152 筆（含 31 筆 nhi_drug_code）
- B. drug_diagnosis_links：27 筆 → 可插 17、blocked 10（FK 缺 diagnosis_code）
  - links per diagnosis_code_id：`{189: 8, 129: 4, 65: 2, 24: 3, 198: 10}`
  - prod 缺少的 diagnosis_code id：`[198]`（本地 198＝第2型糖尿病 E11.9）
- C. customers：additive INSERT 20 筆（prod 自配新 id）

## Production safety checks
- [PASS] prod target host/db/user
- [PASS] prod customers == 53
- [PASS] prod drug_items absent or empty
- [PASS] prod drug_diagnosis_links absent or empty
- [PASS] live tables present & untouched (read-only)
- [PASS] none of 20 new customers already on prod (name+birthday)

## Blocked risks（需你決策）
- ⚠ **10 筆 drug_diagnosis_links 無法插入**：參照 prod 不存在的 diagnosis_code（本地 id 198＝第2型糖尿病 E11.9）。
  - prod 僅 197 筆 diagnosis_codes、無 E11.9；最相近的 prod id187＝『糖尿病併多發性神經病變』語意不同，**不可 remap**。
  - **選項①（達成 links=27，建議）**：apply 加 `--add-missing-diagnosis` → 先 additive 新增該 diagnosis_code（preserve id 198）到 prod，再插 27 筆。diagnosis_codes 為參考表、additive 低風險，但**超出你列的 Tier 1 三項**，需你同意。
  - **選項②（不動 diagnosis_codes）**：只插 17 筆、其餘 10 筆略過 → prod links=17（非 27），/drug 少了第2型糖尿病相關連結。
  - **選項③**：先單獨做 diagnosis_codes 對齊（local 198 vs prod 197），再回來插 links。

## apply 後預期（驗收目標）
- drug_items=152（nhi 31）、drug_diagnosis_links=17、customers=73；prod 既有 53 customers 不變；live 表 count 不變。

## 本輪未做
- 未對 production ALTER/INSERT/UPDATE/DELETE/TRUNCATE/DROP、未動 live 表、未寫 local、未改程式、未 git。

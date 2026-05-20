# diagnosis_codes × official_icd10_cm_reference_staging 品質報告

## 本階段目的
本報告只做唯讀品質分析，檢查正式 `diagnosis_codes` 與健保 2023 ICD-10-CM 官方 reference staging 的對照品質，並規劃下一批 ICD-10 補碼候選。

明確限制：本報告不修改資料庫、不產生 UPDATE SQL、不 apply、不修改 `/dx`、`/drug`、LIFF、藥品、OCR、photos 或 prescription 相關資料。

## 資料來源
| 資料表 | 用途 | 筆數 |
| --- | --- | --- |
| diagnosis_codes | 正式診斷碼表 | 198 |
| official_icd10_cm_reference_staging | 健保 2023 ICD-10-CM 官方 reference | 96802 |
| diagnosis_icd_mappings_staging | 第一批 ICD-9 → ICD-10 補碼 staging | 18 |
| drug_diagnosis_links | 藥品診斷關聯，僅確認未受影響 | 27 |

## diagnosis_codes 總覽
| 項目 | 筆數 |
| --- | --- |
| 總筆數 | 198 |
| 有 ICD-10 | 22 |
| 缺 ICD-10 | 176 |
| 有 ICD-9 | 197 |
| 缺 ICD-9 | 1 |
| ICD-9 組合碼/多重碼 | 4 |
| ICD-9 非純數字或含小數以外格式 | 5 |
| ICD-10 組合碼/多重碼 | 0 |
| ICD-10 非標準格式 | 0 |

## 已有 ICD-10 官方對照檢查
| 項目 | 筆數 |
| --- | --- |
| ICD-10 非空 | 22 |
| 存在於官方 staging | 22 |
| 官方 staging 查不到 | 0 |
| USE=1 | 22 |
| USE=0 | 0 |
| 需要 review 項目數 | 15 |

### 可能需要 review 的已有 ICD-10 項目（最多列 40 筆）
| id | ICD-10 | 診所中文名 | 官方存在 | USE | 官方中文名 | 差異摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| 65 | N40.0 | 良性攝護腺肥大 | 是 | 1 | 良性攝護腺增生未伴有下泌尿道症狀 | 中文名相近但不完全一致，建議 review |
| 129 | E78.5 | 高血脂 | 是 | 1 | 高血脂症 | 中文名包含關係，建議 review 語意範圍 |
| 140 | E78.1 | 純高甘油脂血症 | 是 | 1 | 純高三酸甘油酯血症 | 中文名相近但不完全一致，建議 review |
| 141 | E78.2 | 混合性高血脂症 | 是 | 1 | 混合型高血脂症 | 中文名相近但不完全一致，建議 review |
| 164 | R94.5 | 肝功能檢驗異常 | 是 | 1 | 肝功能檢查結果異常 | 中文名相近但不完全一致，建議 review |
| 189 | I10 | 本態性高血壓 | 是 | 1 | 本態性(原發性)高血壓 | 中文名相近但不完全一致，建議 review |
| 190 | I11.9 | 高血壓性心臟病（無心衰竭） | 是 | 1 | 高血壓性心臟病，無心臟衰竭 | 中文名相近但不完全一致，建議 review |
| 191 | I11.0 | 高血壓性心臟病（有心衰竭） | 是 | 1 | 高血壓性心臟病伴有心臟衰竭 | 中文名相近但不完全一致，建議 review |
| 192 | I12.9 | 高血壓性慢性腎臟病（CKD 第 1–4 期或未特定） | 是 | 1 | 高血壓性慢性腎臟病伴有第一至第四期慢性腎病或未明示慢性腎病 | 中文名差異較明顯，需 review |
| 193 | I12.0 | 高血壓性慢性腎臟病（CKD 第 5 期或 ESRD） | 是 | 1 | 高血壓性慢性腎臟病伴有第五期慢性腎病或末期腎病 | 中文名差異較明顯，需 review |
| 194 | I13.10 | 高血壓性心臟及慢性腎臟病（無心衰竭，CKD 第 1–4 期或未特定） | 是 | 1 | 高血壓性心臟及慢性腎臟病未伴有心臟衰竭合併第一至第四期慢性腎病或未明示慢性腎病 | 中文名相近但不完全一致，建議 review |
| 195 | I13.0 | 高血壓性心臟及慢性腎臟病（有心衰竭，CKD 第 1–4 期或未特定） | 是 | 1 | 高血壓性心臟及慢性腎臟病伴有心臟衰竭及第一至第四期慢性腎病或未明示慢性腎病 | 中文名相近但不完全一致，建議 review |
| 196 | I13.11 | 高血壓性心臟及慢性腎臟病（無心衰竭，CKD 第 5 期或 ESRD） | 是 | 1 | 高血壓性心臟及慢性腎臟病未伴有心臟衰竭合併第五期慢性腎病或末期腎病 | 中文名相近但不完全一致，建議 review |
| 197 | I13.2 | 高血壓性心臟及慢性腎臟病（有心衰竭，CKD 第 5 期或 ESRD） | 是 | 1 | 高血壓性心臟及慢性腎臟病伴有心臟衰竭及第五期慢性腎病或末期腎病 | 中文名相近但不完全一致，建議 review |
| 198 | E11.9 | 第2型糖尿病，未伴有併發症 | 是 | 1 | 第二型糖尿病，未伴有併發症 | 中文名相近但不完全一致，建議 review |

## Phase 3 新補 10 筆驗收
| id | name_zh | icd9_code | icd10_code | official_name_zh | official_name_en | USE | 官方存在 | 合理性 | review_note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 痛風 | 2749 | M10.9 | 痛風 | Gout, unspecified | 1 | 是 | 合理 | 中文名完全一致 |
| 64 | 急性腎盂腎炎 | 59010 | N10 | 急性腎盂腎炎 | Acute pyelonephritis | 1 | 是 | 合理 | 中文名完全一致 |
| 94 | 腎絞痛 | 7880 | N23 | 腎絞痛 | Unspecified renal colic | 1 | 是 | 合理 | 中文名完全一致 |
| 128 | 貧血 | 2859 | D64.9 | 貧血 | Anemia, unspecified | 1 | 是 | 合理 | 中文名完全一致 |
| 140 | 純高甘油脂血症 | 2721 | E78.1 | 純高三酸甘油酯血症 | Pure hyperglyceridemia | 1 | 是 | 合理 | 中文名相近但不完全一致，建議 review |
| 141 | 混合性高血脂症 | 2722 | E78.2 | 混合型高血脂症 | Mixed hyperlipidemia | 1 | 是 | 合理 | 中文名相近但不完全一致，建議 review |
| 164 | 肝功能檢驗異常 | 7948 | R94.5 | 肝功能檢查結果異常 | Abnormal results of liver function studies | 1 | 是 | 合理 | 中文名相近但不完全一致，建議 review |
| 171 | 酒精性脂肪肝 | 5710 | K70.0 | 酒精性脂肪肝 | Alcoholic fatty liver | 1 | 是 | 合理 | 中文名完全一致 |
| 172 | 慢性肝炎 | 57140 | K73.9 | 慢性肝炎 | Chronic hepatitis, unspecified | 1 | 是 | 合理 | 中文名完全一致 |
| 17 | 脂漏性皮膚炎 | 69010 | L21.9 | 脂漏性皮膚炎 | Seborrheic dermatitis, unspecified | 1 | 是 | 合理 | 中文名完全一致 |

結論：Phase 3 10 筆皆可在官方 staging 找到；多數中文名完全一致或高度接近。`E78.1`、`E78.2` 與診所用語存在「高甘油脂/高三酸甘油酯」、「混合性/混合型」文字差異，語意仍接近但建議保留 review note。

## 缺 ICD-10 remaining pool 分析
| 項目 | 筆數 |
| --- | --- |
| 缺 ICD-10 總筆數 | 176 |
| 缺 ICD-10 且有 ICD-9 | 176 |
| 缺 ICD-10 且 ICD-9 單一純數字 | 172 |
| 缺 ICD-10 且 ICD-9 組合/多重/非純數字 | 4 |

### 依中文名粗分類
| 分類 | 筆數 |
| --- | --- |
| 其他 | 60 |
| 腎臟 / 泌尿 | 51 |
| 肝膽腸胃 | 22 |
| 皮膚 | 16 |
| 感染 | 16 |
| 糖尿病 / 代謝 | 9 |
| 神經 | 2 |

## 下一批候選策略
候選來源以 `diagnosis_icd_mappings_staging` 既有 18 筆為起點；Phase 3 已 apply 10 筆後，剩餘候選多屬於語意範圍需人工確認的項目。本輪只產生候選方向，不 apply。

| candidate_status | 筆數 |
| --- | --- |
| needs_more_source | 7 |
| high_confidence_candidate | 1 |

### 下一批候選摘要
| diagnosis_code_id | ICD-9 | name_zh | candidate ICD-10 | official_name_zh | USE | candidate_status | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | 28521 | 腎性貧血 | D63.1 | 慢性腎臟疾病導致的貧血 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 71 | 5990 | 泌尿道感染 | N39.0 | 未明示部位之泌尿道感染症 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 76 | 5849 | 急性腎衰竭 | N17.9 | 急性腎衰竭 | 1 | high_confidence_candidate | 可列下一批 approve 候選，但仍需人工確認 |
| 78 | 5829 | 慢性腎絲球腎炎 | N03.9 | 慢性腎炎症候群伴有非特異性的組織形態改變 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 92 | 6019 | 攝護腺炎 | N41.9 | 攝護腺炎性疾病 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 98 | 5932 | 腎囊腫 | N28.1 | 後天性腎囊腫 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 109 | 75313 | 多囊腎（顯性染色體） | Q61.2 | 成人型多囊腎 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |
| 133 | 2810 | 惡性貧血 | D51.0 | 內因子缺乏所致的維生素Ｂ12缺乏性貧血 | 1 | needs_more_source | 官方單一對應但語意範圍需人工確認 |

### 建議分類
- `high_confidence_candidate`：官方單一對應、USE=1、語意高度一致；可進下一批人工 approve 清單。
- `needs_more_source`：官方單一對應但語意變窄/變廣、涉及部位、分期、急慢性或臨床語境；需更多來源。
- `do_not_auto_apply`：組合碼、多重碼、候選不存在官方 staging、或診所自訂概念；不建議自動補。

## 風險與安全原則
1. 不直接 UPDATE `diagnosis_codes`。
2. 不產生可直接執行的 UPDATE SQL。
3. `USE=0` 是分類/header code，後續不可未經 review 當正式補碼。
4. ICD-9 一對多、語意變窄/變廣、組合碼需人工 review。
5. 官方中文名與診所中文名不完全一致時，應保留診所原始名稱並用 review 流程決定是否補 ICD-10。
6. `drug_diagnosis_links` 不應被本輪品質分析影響。

## 輸出
- Markdown：`db_backups/diagnosis_backup_20260505_085955/00_icd10_official_reference_quality_report.md`
- CSV：`db_backups/diagnosis_backup_20260505_085955/icd10_next_batch_candidate_summary.csv`

本報告不修改資料庫、不產生 UPDATE SQL。
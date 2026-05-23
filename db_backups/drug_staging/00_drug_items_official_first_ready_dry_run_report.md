# Drug Items Official-first Ready Dry-run Report

## 本階段目的

本報告只處理 official-first dry-run candidates 中 `readiness = ready_for_dry_run` 的 6 筆，產生 dry-run 明細與人工決策 CSV。
本輪不修改資料庫、不產生可直接執行的 UPDATE SQL、不 git add/commit。

## 範圍

- 本批處理：id 4, 10, 13, 96, 123, 150。
- 不處理：id 14, 17, 77。
  - id 14: 已有 drug_diagnosis_links，需 high-attention dry-run；本批先不處理。
  - id 17: 需更詳細 evidence；本批先不處理。
  - id 77: 官方候選 losartan 與現有 Co-Diovan 品牌語意不一致，blocked。

## 唯讀 DB 確認

- 6 筆 `drug_items.id` 均存在。
- 6 筆目前 `generic_name` / `brand_name` 與候選 CSV current 值一致。
- 6 筆皆無 `drug_diagnosis_links` 引用。
- 本批所有 action_type 均在允許清單內：`correct_generic_name`、`add_alias_only`、`keep_current`。

## Dry-run 明細

| id | current generic / brand | proposed generic / brand | action | official source | risk | duplicate risk | dry_run_status | 驗收方式 |
|---:|---|---|---|---|---|---|---|---|
| 4 | Dextromethorphan20mg+Pot. Cres / Noncough(Medicon-A) 諾咳 | POTASSIUM CRESOLSULFONATE 90 MG + LYSOZYME CHLORIDE 20 MG + DEXTROMETHORPHAN HBR 20 MG / MEDICON-A CAPSULES / 滅咳康複合膠囊 | correct_generic_name | NHI payment | medium | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug 可用 `POTASSIUM CRESOLSULFONATE 90 MG + LYSOZYME CHLORIDE 20 MG + DEXTROMETHORPHAN HBR 20 MG` 查到；舊名稱 `Dextromethorphan20mg+Pot. Cres` 若需保留，後續應加入 aliases 或保留查詢策略。 |
| 10 | Cephalaxin / Keflex 賜福力欣 | CEPHALEXIN MONOHYDRATE / CEPHALEXIN MONOHYDRATE "OPOS" / 賜福力欣 | correct_generic_name | TFDA license | medium | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug 可用 `CEPHALEXIN MONOHYDRATE` 查到；舊名稱 `Cephalaxin` 若需保留，後續應加入 aliases 或保留查詢策略。 |
| 13 | DIMETHYL 1, 4- 7-ISOPROPYLASUL / Azulene 安如寧 | AZULENE / AZUKURENIN TABLETS / 愛胃寧錠 | correct_generic_name | TFDA license | medium | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug 可用 `AZULENE` 查到；舊名稱 `DIMETHYL 1, 4- 7-ISOPROPYLASUL` 若需保留，後續應加入 aliases 或保留查詢策略。 |
| 96 | Bethamechol / Wecoli 胃可麗 | BETHANECHOL CHLORIDE 25 MG / WECOLI TABLETS 25MG / "應元"胃可麗錠２５毫克 | correct_generic_name | NHI payment | medium | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug 可用 `BETHANECHOL CHLORIDE 25 MG` 查到；舊名稱 `Bethamechol` 若需保留，後續應加入 aliases 或保留查詢策略。 |
| 123 | Beniel / Beniel 保你爾膜衣錠 | BENIDIPINE HYDROCHLORIDE 4 MG / Beniel F.C. Tablets 4mg / 保你爾膜衣錠4毫克 | correct_generic_name | NHI payment | medium | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug 可用 `BENIDIPINE HYDROCHLORIDE 4 MG` 查到；舊名稱 `Beniel` 若需保留，後續應加入 aliases 或保留查詢策略。 |
| 150 | Urea / U/Sinpharderm cream 杏化 | UREA / Soficome Cream / 芙澤適乳膏 | add_alias_only | TFDA license | low | 未在 possible_duplicates CSV 中找到相關 pair | ready_to_apply | /drug `Urea` 應維持可查；新增 aliases 後可用官方/舊品牌別名查詢。 |

## 分布

| action_type | 筆數 |
|---|---:|
| add_alias_only | 1 |
| correct_generic_name | 5 |

- ready_to_apply: 6
- 涉及 drug_diagnosis_links: 0

## 安全結論

6 筆均可進入下一階段 apply 腳本設計，但本報告不代表已執行 apply。正式 apply 腳本仍須在執行前重新查 DB，並建立 `drug_items` 備份。
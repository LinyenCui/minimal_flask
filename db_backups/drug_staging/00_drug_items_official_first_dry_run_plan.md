# Drug Items Official-first Dry-run Apply Plan

## 本階段目的

本報告審查 official-first 高風險藥品決策草案，將 9 筆分成可進 dry-run、需更多 evidence、以及 blocked 三組。
本輪不修改資料庫、不產生 UPDATE SQL、不 git add/commit。

## 來源

- `db_backups/drug_staging/00_drug_items_high_risk_official_decision_plan.md`
- `db_backups/drug_staging/drug_items_high_risk_official_review_decisions.csv`

## 唯讀 DB 確認

- `drug_items` 9 筆皆存在，且目前 `generic_name` / `brand_name` 與 decisions CSV 一致。
- `drug_diagnosis_links` 引用：id 14 有 1 筆；其他 8 筆沒有引用。
- 官方 staging 候選：9 筆的 `official_code_or_license` 均可在對應 official staging 找到。
- 本輪未執行 `UPDATE / INSERT / DELETE / TRUNCATE`。

## 分組統計

| group | 筆數 |
|---|---:|
| A. ready_for_dry_run | 6 |
| B. needs_dry_run_before_apply | 2 |
| C. blocked | 1 |

## A. ready_for_dry_run，可進下一步 dry-run 的項目

| id | current generic / brand | proposed generic / brand | action | readiness | link | risk | official evidence | next step |
|---:|---|---|---|---|---|---|---|---|
| 4 | Dextromethorphan20mg+Pot. Cres / Noncough(Medicon-A) 諾咳 | POTASSIUM CRESOLSULFONATE 90 MG + LYSOZYME CHLORIDE 20 MG + DEXTROMETHORPHAN HBR 20 MG / MEDICON-A CAPSULES / 滅咳康複合膠囊 | correct_generic_name | ready_for_dry_run | no | medium | NHI payment; A021758100; 成分: POTASSIUM CRESOLSULFONATE 90 MG+LYSOZYME CHLORIDE 20 MG+DEXTROMETHORPHAN HBR 20 MG; 英文: MEDICON-A CAPSULES; 中文: 滅咳康複合膠囊; ATC: R05FA01; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |
| 10 | Cephalaxin / Keflex 賜福力欣 | CEPHALEXIN MONOHYDRATE / CEPHALEXIN MONOHYDRATE "OPOS" / 賜福力欣 | correct_generic_name | ready_for_dry_run | no | medium | TFDA license; 衛署藥輸字第015885號; 成分: CEPHALEXIN MONOHYDRATE; 英文: CEPHALEXIN MONOHYDRATE "OPOS"; 中文: 賜福力欣; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |
| 13 | DIMETHYL 1, 4- 7-ISOPROPYLASUL / Azulene 安如寧 | AZULENE / AZUKURENIN TABLETS / 愛胃寧錠 | correct_generic_name | ready_for_dry_run | no | medium | TFDA license; 衛署藥輸字第015277號; 成分: AZULENE; 英文: AZUKURENIN TABLETS; 中文: 愛胃寧錠; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |
| 96 | Bethamechol / Wecoli 胃可麗 | BETHANECHOL CHLORIDE 25 MG / WECOLI TABLETS 25MG / "應元"胃可麗錠２５毫克 | correct_generic_name | ready_for_dry_run | no | medium | NHI payment; AC37225100; 成分: BETHANECHOL CHLORIDE 25 MG; 英文: WECOLI TABLETS 25MG (BETHANECHOL CHLORIDE) "YY"; 中文: "應元"胃可麗錠２５毫克（氯化月尿酯膽生僉）; ATC: N07AB02; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |
| 123 | Beniel / Beniel 保你爾膜衣錠 | BENIDIPINE HYDROCHLORIDE 4 MG / Beniel F.C. Tablets 4mg / 保你爾膜衣錠4毫克 | correct_generic_name | ready_for_dry_run | no | medium | NHI payment; A056633100; 成分: BENIDIPINE HYDROCHLORIDE 4 MG; 英文: Beniel F.C. Tablets 4mg; 中文: 保你爾膜衣錠4毫克; ATC: C08CA15; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |
| 150 | Urea / U/Sinpharderm cream 杏化 | UREA / Soficome Cream / 芙澤適乳膏 | add_alias_only | ready_for_dry_run | no | low | TFDA license; 衛部藥製字第060928號; 成分: UREA; 英文: Soficome Cream; 中文: 芙澤適乳膏; staging_verified=yes | 可納入下一步 dry-run apply report；dry-run 通過後再評估是否建立 apply 腳本。 |

## B. needs_dry_run_before_apply，需更詳細 evidence 的項目

| id | current generic / brand | proposed generic / brand | action | readiness | link | risk | official evidence | next step |
|---:|---|---|---|---|---|---|---|---|
| 14 | IRBESARTAN 300MG + HYDROCHLORO / Aprovel 安普諾維(原廠) | IRBESARTAN 300 MG / Aprovel 安普諾維(原廠) | correct_generic_name | high_attention_dry_run | yes | high | NHI payment; AB57864100; 成分: IRBESARTAN 300 MG; 英文: Heipo F.C. Tablets 300mg "EVEREST"; 中文: "永勝"愛必斯膜衣錠300毫克; ATC: C09CA04; staging_verified=yes | 可進 dry-run，但 apply 前需確認 /drug 顯示與既有 drug_diagnosis_links 語意不受影響。 |
| 17 | Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰 | GLIMEPIRIDE 2 MG / Amaryl-M 美爾胰 | correct_generic_name | needs_dry_run_before_apply | no | medium | NHI payment; A047172100; 成分: GLIMEPIRIDE 2 MG; 英文: Amepiride Tablets 2.0MG; 中文: 欣益糖錠 2.0 毫克; ATC: A10BB12; staging_verified=yes | 先補更完整 evidence，再進 dry-run；不得直接 apply。 |

## C. blocked，不進 apply 的項目

| id | current generic / brand | proposed generic / brand | blocked reason | next step |
|---:|---|---|---|---|
| 77 | Valosartan80mg+Hydrochlorothia / Co- Diovan(80) 可得安穩 (諾華) | losartan / Co- Diovan(80) 可得安穩 (諾華) | 現有品牌 Co-Diovan 通常語意可能涉及 valsartan/hydrochlorothiazide，官方候選 losartan 與現有品牌語意不一致，需更多來源或原始照片確認。 | 暫不納入 apply；先回原圖或另查官方品項，確認 Co-Diovan 對應成分。 |

## id 14 風險確認

id 14 已有 1 筆 `drug_diagnosis_links`。即使官方候選 `IRBESARTAN 300 MG` 明確，這筆也只能列為 `high_attention_dry_run`：後續 apply 前需確認 `/drug` 顯示、藥診關聯語意、以及現有 `Aprovel` 品牌是否仍保留在 brand 或 alias。

## id 77 暫不 apply 原因

id 77 的 official-first 候選來自 TFDA ATC，候選為 `losartan`；但現有品牌 `Co-Diovan(80) 可得安穩 (諾華)` 通常語意可能涉及 valsartan/hydrochlorothiazide。官方候選與現有品牌語意不一致，因此本輪標記 blocked，不納入 apply 候選，也不輸出任何修正到 apply list。

## Dry-run Apply Plan

下一步若要進入 dry-run，建議只處理 A 組 6 筆；B 組 2 筆另列 high-attention dry-run；C 組 id 77 暫停。
dry-run 應逐筆重新確認：

- `drug_items.id` 存在。
- `generic_name` / `brand_name` 仍與 decisions CSV 中 current 值一致。
- official staging 候選仍存在。
- 不修改 `drug_diagnosis_links`。
- 不產生或執行 UPDATE SQL。

## 安全原則

- 本報告只產出 dry-run plan。
- 不修改 `drug_items`。
- 不修改 `drug_diagnosis_links`。
- 不修改 official staging。
- 不產生可直接執行的 UPDATE SQL。
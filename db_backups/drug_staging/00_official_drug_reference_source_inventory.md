# 官方藥品公開資料來源盤點

查找日期：2026-05-21  
範圍：只查官方或準官方公開來源；未下載資料檔、未建立 reference_data/drug、未寫資料庫。

## 結論

建議先以健保署「健保用藥品項查詢項目檔」作為 `drug_items` 的第一層對照來源，因為它直接含健保藥品代號、藥品中英文名稱、成分、規格、劑型、支付價、有效日期與 ATC 代碼。食藥署「全部藥品許可證資料集」適合作為許可證與品名正規化來源，但成分欄位偏摘要；若要做成分比對，應再接「藥品詳細處方成分資料集」。ATC 則建議用食藥署 ATC 對照資料集先做台灣許可證層級連結，再用 WHO/WHOCC ATC/DDD 作官方分類 reference。

## 建議優先下載順序

1. 健保署：健保用藥品項查詢項目檔
   - 用途：優先比對現有 `drug_items` 的 generic / brand / table_type / item_kind / source alias，補健保代碼、支付價、劑型、規格、ATC。
   - 建議路徑：`reference_data/drug/nhia/`
   - 建議檔名：`nhia_drug_items_YYYYMMDD.csv`

2. 食藥署：全部藥品許可證資料集
   - 用途：建立許可證字號、中文品名、英文品名、藥商、製造廠、註銷狀態與許可證有效性 reference。
   - 建議路徑：`reference_data/drug/tfda/`
   - 建議檔名：`tfda_all_drug_licenses_YYYYMMDD.csv`

3. 食藥署：藥品詳細處方成分資料集
   - 用途：用許可證字號 join 許可證資料，取得較結構化的成分名稱、成分代碼、含量與單位。
   - 建議路徑：`reference_data/drug/tfda/`
   - 建議檔名：`tfda_drug_ingredients_YYYYMMDD.csv`

4. 食藥署：藥品藥理治療分類 ATC 碼資料集
   - 用途：台灣許可證字號到 ATC code 的準官方橋接資料。
   - 建議路徑：`reference_data/drug/atc/`
   - 建議檔名：`tfda_drug_atc_codes_YYYYMMDD.csv`

5. WHO/WHOCC：ATC/DDD Index
   - 用途：ATC code 階層、英文分類名、DDD 與年度版本 reference；不作台灣品項主鍵，只作分類標準。
   - 建議路徑：`reference_data/drug/atc/`
   - 建議檔名：`who_atc_ddd_index_YYYY.xlsx` 或 `who_atc_ddd_index_YYYY.xml`
   - 注意：完整電子版需註冊/訂購入口與授權確認；不可直接假設為自由再散布資料。

## 1. 健保署藥品給付 / 藥價資料

### 1.1 健保用藥品項查詢項目檔

- 資料名稱：健保用藥品項查詢項目檔
- 官方網址：
  - 政府資料開放平臺：https://data.gov.tw/dataset/23715
  - 健保署資料開放平台：https://info.nhi.gov.tw/IODE0000/
- 提供機關：衛生福利部中央健康保險署
- 檔案格式：CSV；政府資料頁也標示有 OAS/OpenAPI 說明文件。
- 是否含健保藥品代碼：是，欄位為「藥品代號」。
- 是否含中文藥名 / 英文藥名：是，欄位為「藥品中文名稱」、「藥品英文名稱」。
- 是否含成分、規格、劑型、藥價、給付狀態：
  - 成分：是。
  - 規格：是，含「規格量」、「規格單位」。
  - 劑型：是。
  - 藥價：是，欄位為「支付價」。
  - 給付狀態：有「異動」、「有效起日」、「有效迄日」、「給付規定章節」等，可推估有效與給付資訊；不宜只用單一欄位判定 active。
  - 其他有用欄位：藥商、製造廠名稱、藥品分類、分類分組名稱、ATC 代碼、藥品代碼超連結。
- 更新頻率或版本日期：
  - 更新頻率：每 1 月。
  - 查得詮釋資料更新時間：2026-05-13 07:05。
  - 查得檔案更新時間：2026-05-13 07:01:57。
- 下載方式：
  - 從政府資料開放平臺資料集頁的 CSV 資源連到 `info.nhi.gov.tw`。
  - 也可由健保署資料開放平台 / OAS API 介接，但下一步實作前應先固定 metadata snapshot 與檔案 hash。
- 建議用途：
  - `drug_items` 最優先比對來源。
  - 可用於建立 `nhia_drug_code`、健保品名 alias、支付價與有效日期 reference。
- 風險點：
  - 資料可能有歷史/異動列，同一藥品代號需依有效日期判斷目前狀態。
  - 藥品英文名稱可能是商品名、劑型與規格混合字串，不應直接當 generic_name。
  - 中文品名與診所常用簡稱差距大，仍需 alias normalization。
  - CSV 編碼與大量資料欄位型別需先檢查，尤其藥品代號不可被當數字處理。

### 1.2 全民健保藥品價格檔 H_NHI_DRPRICE

- 資料名稱：全民健保藥品價格檔（H_NHI_DRPRICE）
- 官方/準官方資訊來源：
  - 衛福部資料庫使用手冊頁曾列出 `H_NHI_DRPRICE` 欄位資訊。
  - Taiwan Gateway to Health Data 有「全民健保藥品價格檔」資料集說明。
- 檔案格式：GHD 說明偏申請型資料，非一般政府開放資料直接下載。
- 是否含健保藥品代碼：是，欄位說明含醫令代碼 / ORDER_CODE。
- 是否含中文藥名 / 英文藥名：價格檔本身重點是價格與醫令代碼，不宜期待完整品名欄位。
- 是否含成分、規格、劑型、藥價、給付狀態：
  - 藥價：是。
  - 成分、規格、劑型：需與藥品主檔或健保用藥品項資料串接。
- 更新頻率或版本日期：GHD 說明為歷史檔，可申請自 2000 年起資料，最新年份視資料中心公告。
- 下載方式：偏研究/申請流程，不是本階段優先公開下載來源。
- 建議用途：
  - 若未來要做歷史藥價趨勢，再評估申請。
  - 目前比對 `drug_items` 不建議先用它，因為「健保用藥品項查詢項目檔」已包含現行支付價。
- 風險點：
  - 可能涉及申請資格、費用、使用環境與研究目的限制。
  - 不是本次「不下載、公開來源盤點」的優先落地資料。

## 2. 食藥署藥品許可證資料

### 2.1 全部藥品許可證資料集

- 資料名稱：全部藥品許可證資料集
- 官方網址：
  - 政府資料開放平臺：https://data.gov.tw/dataset/9122
  - 食藥署 Open Data 詳細頁：https://data.fda.gov.tw/frontsite/data/DataAction.do?method=doDetail&infoId=36
  - 食藥署安全資訊 open data 清單：https://www.fda.gov.tw/TC/siteList.aspx?sid=4253
- 提供機關：衛生福利部食品藥物管理署
- 檔案格式：CSV / JSON / XML；資料量大時以 ZIP 壓縮。
- 是否含許可證字號：是。
- 是否含中文品名 / 英文品名：是。
- 是否含成分：有「主成分略述」，但不是最佳結構化成分來源。
- 是否含劑型、藥商、製造廠：
  - 劑型：是。
  - 藥商：是，欄位含申請商名稱、申請商地址、統一編號。
  - 製造廠：是，欄位含製造商名稱、製造廠廠址、公司地址、國別、製程。
- 其他有用欄位：註銷狀態、註銷日期、有效日期、發證日期、許可證種類、適應症、包裝、藥品類別、管制藥品分類級別、用法用量、包裝與國際條碼。
- 更新頻率或版本日期：
  - 更新頻率：每 7 日。
  - 查得詮釋資料更新時間：2026-05-07 08:39。
- 下載方式：
  - 從政府資料開放平臺資料集頁取得 CSV / JSON / XML 資源。
  - 或走食藥署 Open Data API / exportDataList 介面。
- 建議用途：
  - 建立 `drug_items` 的許可證、品牌品名、中文/英文品名、藥商與製造廠 reference。
  - 判斷品項是否註銷或許可證過期。
- 風險點：
  - 全部資料包含已註銷資料，匯入前要明確保留 `cancel_status` 與有效日期，不可直接當 active drug list。
  - 「英文品名」常含劑型、規格、包裝或商品名，不能直接當 generic_name。
  - 「主成分略述」不夠結構化，成分比對要串「藥品詳細處方成分資料集」。
  - 資料量大且 ZIP 包裝，需保留版本日期與原始檔 hash。

### 2.2 藥品詳細處方成分資料集

- 資料名稱：藥品詳細處方成分資料集
- 官方網址：
  - 政府資料開放平臺：https://data.gov.tw/dataset/9121
  - 食藥署 Open Data 詳細頁：https://data.fda.gov.tw/frontsite/data/DataAction.do?method=doDetail&infoId=43
- 提供機關：衛生福利部食品藥物管理署
- 檔案格式：CSV / JSON / XML；資料量大時以 ZIP 壓縮。
- 是否含許可證字號：是。
- 是否含中文品名 / 英文品名：否，需 join「全部藥品許可證資料集」。
- 是否含成分：是，欄位含「成分名稱」、「成分代碼」、「含量描述」、「含量」、「含量單位」。
- 是否含劑型、藥商、製造廠：否，需 join 許可證資料。
- 更新頻率或版本日期：
  - 更新頻率：每 7 日。
  - 查得詮釋資料更新時間：2026-05-07 08:39。
- 下載方式：
  - 從政府資料開放平臺資料集頁取得 CSV / JSON / XML 資源。
  - 或走食藥署 Open Data API / exportDataList 介面。
- 建議用途：
  - 用 `permit_no` 建立 structured ingredients reference。
  - 補強 `drug_items.generic_name` / aliases 的成分比對。
- 風險點：
  - 一張許可證可能多個成分列，必須保留一對多關係。
  - 成分名稱可能英文、縮寫、鹽類或複方描述混雜，不可直接當唯一 generic。
  - 含量單位與劑型規格需標準化。

## 3. ATC / 成分分類資料

### 3.1 食藥署藥品藥理治療分類 ATC 碼資料集

- 資料名稱：藥品藥理治療分類 ATC 碼資料集
- 官方網址：
  - 政府資料開放平臺英文頁：https://data.gov.tw/en/datasets/9119
  - 食藥署安全資訊 open data 清單：https://www.fda.gov.tw/TC/siteList.aspx?sid=4253
- 提供機關：衛生福利部食品藥物管理署
- 檔案格式：CSV / JSON / XML；資料量大時以 ZIP 壓縮。
- 主要欄位：許可證字號、主或次項、代碼、英文分類名稱、中文分類名稱。
- 是否可下載：可由政府資料開放平臺 / 食藥署 Open Data 資源取得。
- 是否需授權或只能查詢：政府資料開放授權條款第 1 版，免費；仍需保留來源與版本。
- 是否適合放進 `reference_data/drug/atc/`：適合，尤其作為台灣許可證字號到 ATC code 的 bridge table。
- 更新頻率或版本日期：
  - 更新頻率：每 7 日。
  - 查得更新時間：2026-05-18 11:23。
- 建議用途：
  - 將 TFDA permit_no 對應到 ATC code。
  - 對 `drug_items` 補分類資料，但不要直接推論診斷碼或適應症。
- 風險點：
  - 一張許可證可能有主碼與次碼、多碼。
  - ATC code 可能到不同層級，不一定都是第五層成分碼。
  - 中文分類名稱可能空白或不完整，英文分類名稱較穩。

### 3.2 WHO / WHOCC ATC/DDD Index

- 資料名稱：ATC/DDD Index
- 官方網址：
  - WHO ATC/DDD 說明：https://www.who.int/standards/classifications/other-classifications/the-anatomical-therapeutic-chemical-classification-system-with-defined-daily-doses
  - WHO ATC/DDD Toolkit：https://www.who.int/tools/atc-ddd-toolkit/start-using
  - WHO Collaborating Centre ATC/DDD Index：https://atcddd.fhi.no/atc_ddd_index_and_guidelines/
- 檔案格式：
  - 網站提供免費線上查詢。
  - 完整電子版 ATC Index with DDDs 通常以 Excel 或 XML 形式，需透過註冊帳號 / Orders ATC/DDD 取得。
  - 新增與異動清單通常可免費取得。
- 是否可下載：完整資料可下載，但需走 WHOCC 的註冊/訂購流程；線上查詢免費。
- 是否需授權或只能查詢：
  - 不應假設完整 ATC/DDD Index 可自由再散布。
  - 匯入 `reference_data/drug/atc/` 前需保留授權、引用格式與版本年度。
- 是否適合放進 `reference_data/drug/atc/`：
  - 適合放「授權允許保存的年度 reference copy」與 metadata。
  - 若未確認授權，先只保存來源 URL、版本與手動查核紀錄。
- 更新頻率或版本日期：
  - WHO 說明 ATC/DDD 為年度更新。
  - Toolkit 說明 Index 通常每年 1 月更新。
  - 目前可查到 ATC/DDD Index 2026。
- 建議用途：
  - ATC 階層、DDD、分類名稱的權威 reference。
  - 校驗食藥署 ATC code 是否存在與層級。
- 風險點：
  - ATC 是分類工具，不是處方適應症或 diagnosis link。
  - WHO 說明 ATC coverage 不完整；某些國內品項、複方或特殊製劑可能沒有碼。
  - 同成分可能因給藥途徑、劑型或用途不同而有不同 ATC，不能只用成分名硬配。

## 建議後續工作

1. 先只建立來源 metadata inventory，不下載正式檔案。
2. 下一步若要落地，先建立 `reference_data/drug/README.md` 與 `reference_data/drug/source_manifest.csv`，記錄來源、版本、下載時間、授權、hash。
3. 第一批只下載健保署「健保用藥品項查詢項目檔」與食藥署「全部藥品許可證資料集」做 dry run schema profiling。
4. 不要直接更新 `drug_items`；先建 staging / reference 表或離線 CSV 對照報告。
5. 不要用 ATC 或成分資料推論 `drug_diagnosis_links`；它們只適合做藥品分類與品名/成分 normalization。

## 本次查找使用來源

- 健保用藥品項查詢項目檔：https://data.gov.tw/dataset/23715
- 健保署資料開放平台：https://info.nhi.gov.tw/IODE0000/
- 全部藥品許可證資料集：https://data.gov.tw/dataset/9122
- 藥品詳細處方成分資料集：https://data.gov.tw/dataset/9121
- 食藥署安全資訊 open data 清單：https://www.fda.gov.tw/TC/siteList.aspx?sid=4253
- 藥品藥理治療分類 ATC 碼資料集：https://data.gov.tw/en/datasets/9119
- WHO ATC/DDD 說明：https://www.who.int/standards/classifications/other-classifications/the-anatomical-therapeutic-chemical-classification-system-with-defined-daily-doses
- WHO ATC/DDD Toolkit：https://www.who.int/tools/atc-ddd-toolkit/start-using
- WHOCC ATC/DDD Index：https://atcddd.fhi.no/atc_ddd_index_and_guidelines/

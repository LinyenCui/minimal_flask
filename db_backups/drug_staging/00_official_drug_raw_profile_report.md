# 官方藥品 raw data schema profiling 報告

產生時間：2026-05-22 22:54:27

## 本階段目的

本報告只讀取 `reference_data/drug/raw/` 內原始檔，盤點欄位、編碼、筆數、範例資料與初步 join 可行性。未寫入資料庫、未建立 table、未清洗 raw data、未 apply。

## raw files 摘要與 manifest 驗證

| dataset | path | size | manifest_size | sha256_match |
| --- | --- | --- | --- | --- |
| NHI drug payment | reference_data/drug/raw/nhi_drug_payment_20260522.csv | 96708741 | 96708741 | yes |
| TFDA license | reference_data/drug/raw/tfda_drug_license_20260522.zip | 9969383 | 9969383 | yes |
| TFDA ingredient | reference_data/drug/raw/tfda_drug_ingredient_20260522.zip | 2010584 | 2010584 | yes |
| TFDA ATC | reference_data/drug/raw/tfda_atc_20260522.zip | 672519 | 672519 | yes |

- `reference_data/drug/raw/nhi_drug_payment_20260522.csv` sha256：`2968cacc020ebcddcf53749cf501ab4f5d3ca86217b6fdf2f1d9d6455cb6d90d`
- `reference_data/drug/raw/tfda_drug_license_20260522.zip` sha256：`94806d18b0ec9f5385ff2d1f4293b662049da01121a31801c5412d9f6cc230a9`
- `reference_data/drug/raw/tfda_drug_ingredient_20260522.zip` sha256：`5311bfeb96029776a80ef03d75d9c200de8ddfffbbfb0094713aeef9eae81555`
- `reference_data/drug/raw/tfda_atc_20260522.zip` sha256：`af8f9cf01b19c56b75cee1f4b709e5a1590dbeec8533536c840206b6d8b47ec3`

## NHI drug payment

| 項目 | 值 |
| --- | --- |
| local_path | reference_data/drug/raw/nhi_drug_payment_20260522.csv |
| inner_file_if_zip | - |
| encoding | utf-8-sig |
| delimiter | , |
| row_count | 224261 |
| column_count | 20 |

### 檔案前 5 行

```text
異動,藥品代號,藥品英文名稱,藥品中文名稱,成分,規格量,規格單位,單複方,支付價,有效起日,有效迄日,藥商,製造廠名稱,劑型,藥品分類,分類分組名稱,ATC代碼,給付規定章節,藥品代碼超連結,給付規定章節連結
,B015924100,FLUANXOL TABLETS 0.5MG,福祿安糖衣錠０．５公絲,FLUPENTIXOL (2HCL) .5 MG,,,單方,6.30,  840301,  890331,禾利行股份有限公司,H. LUNDBECK A/S,糖衣錠,研發廠,"FLUPENTIXOL , 一般錠劑膠囊劑 , .50 MG",N05AF01,,https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02015924,
,B020896229,MODECATE INJECTION,保利神注射液,FLUPHENAZINE DECANOATE 25 MG/ML,10,ML,單方,0.00,  840301,  860531,台灣必治妥施貴寶股份有限公司,BRISTOL-MYERS SQUIBB GMBH,注射劑,研發廠,"FLUPHENAZINE DECANOATE , 注射劑 , 250.00 MG",N05AB02,,https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02020896,
,B020896229,MODECATE INJECTION,保利神注射液,FLUPHENAZINE DECANOATE 25 MG/ML,10,ML,單方,1200.00,  860601,  890331,台灣必治妥施貴寶股份有限公司,BRISTOL-MYERS SQUIBB GMBH,注射劑,研發廠,"FLUPHENAZINE DECANOATE , 注射劑 , 250.00 MG",N05AB02,,https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02020896,
,B020896229,MODECATE INJECTION,保利神注射液,FLUPHENAZINE DECANOATE 25 MG/ML,10,ML,單方,1080.00,  890401,  900331,台灣必治妥施貴寶股份有限公司,BRISTOL-MYERS SQUIBB GMBH,注射劑,研發廠,"FLUPHENAZINE DECANOATE , 注射劑 , 250.00 MG",N05AB02,,https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02020896,
```

### 欄位名稱

`異動`, `藥品代號`, `藥品英文名稱`, `藥品中文名稱`, `成分`, `規格量`, `規格單位`, `單複方`, `支付價`, `有效起日`, `有效迄日`, `藥商`, `製造廠名稱`, `劑型`, `藥品分類`, `分類分組名稱`, `ATC代碼`, `給付規定章節`, `藥品代碼超連結`, `給付規定章節連結`

### 關鍵欄位判斷

| 判斷項目 | 結果 |
| --- | --- |
| 健保藥品代碼 | 有 |
| 許可證字號 | 未明確看到 |
| 中文藥名/品名 | 未明確看到 |
| 英文藥名/品名 | 有 |
| 成分 | 有 |
| 規格/含量 | 有 |
| 劑型 | 有 |
| 單位 | 有 |
| 價格/給付 | 有 |
| 生效日 | 有 |
| 停用/有效日期/狀態 | 未明確看到 |
| ATC code | 有 |
| 申請商/製造廠 | 有 |

### 前 5 筆樣本

| 異動 | 藥品代號 | 藥品英文名稱 | 藥品中文名稱 | 成分 | 規格量 | 規格單位 | 單複方 | 支付價 | 有效起日 | 有效迄日 | 藥商 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | B015924100 | FLUANXOL TABLETS 0.5MG | 福祿安糖衣錠０．５公絲 | FLUPENTIXOL (2HCL) .5 MG |  |  | 單方 | 6.30 | 840301 | 890331 | 禾利行股份有限公司 |
|  | B020896229 | MODECATE INJECTION | 保利神注射液 | FLUPHENAZINE DECANOATE 25 MG/ML | 10 | ML | 單方 | 0.00 | 840301 | 860531 | 台灣必治妥施貴寶股份有限公司 |
|  | B020896229 | MODECATE INJECTION | 保利神注射液 | FLUPHENAZINE DECANOATE 25 MG/ML | 10 | ML | 單方 | 1200.00 | 860601 | 890331 | 台灣必治妥施貴寶股份有限公司 |
|  | B020896229 | MODECATE INJECTION | 保利神注射液 | FLUPHENAZINE DECANOATE 25 MG/ML | 10 | ML | 單方 | 1080.00 | 890401 | 900331 | 台灣必治妥施貴寶股份有限公司 |
|  | B020896229 | MODECATE INJECTION | 保利神注射液 | FLUPHENAZINE DECANOATE 25 MG/ML | 10 | ML | 單方 | 540.00 | 900401 | 900930 | 台灣必治妥施貴寶股份有限公司 |

### 前 20 個主要欄位空值統計

| 欄位 | non_null | null_count | sample_values | inferred_role |
| --- | --- | --- | --- | --- |
| 異動 | 2567 | 221694 | Y | 其他 |
| 藥品代號 | 224261 | 0 | B015924100 / B020896229 / B020964100 | 健保藥品代碼候選 |
| 藥品英文名稱 | 224261 | 0 | FLUANXOL TABLETS 0.5MG / MODECATE INJECTION / SELEGOS TABLETS 5MG | 英文藥名/品名 |
| 藥品中文名稱 | 224175 | 86 | 福祿安糖衣錠０．５公絲 / 保利神注射液 / 舒立康錠 | 中文藥名/品名 |
| 成分 | 224240 | 21 | FLUPENTIXOL (2HCL) .5 MG / FLUPHENAZINE DECANOATE 25 MG/ML / DEPRENYL L- HCL (=SELEGILINE HCL) 5 MG | 成分 |
| 規格量 | 106251 | 118010 | 10 / 60 / 20 | 規格/含量 |
| 規格單位 | 106190 | 118071 | ML / MG / MCL | 規格/含量 |
| 單複方 | 224261 | 0 | 單方 / 複方 | 其他 |
| 支付價 | 224261 | 0 | 6.30 / 0.00 / 1200.00 | 價格/給付價 |
| 有效起日 | 224261 | 0 | 840301 / 860601 / 890401 | 生效日 |
| 有效迄日 | 224261 | 0 | 890331 / 860531 / 900331 | 其他 |
| 藥商 | 223885 | 376 | 禾利行股份有限公司 / 台灣必治妥施貴寶股份有限公司 / 雙正貿易股份有限公司 | 其他 |
| 製造廠名稱 | 222965 | 1296 | H. LUNDBECK A/S / BRISTOL-MYERS SQUIBB GMBH / MEDOCHEMIE LTD. | 廠商/申請商/製造廠 |
| 劑型 | 224244 | 17 | 糖衣錠 / 注射劑 / 錠劑 | 劑型 |
| 藥品分類 | 224172 | 89 | 研發廠 / 一般學名藥 / BA/BE學名藥 | 其他 |
| 分類分組名稱 | 222698 | 1563 | FLUPENTIXOL , 一般錠劑膠囊劑 , .50 MG / FLUPHENAZINE DECANOATE , 注射劑 , 250.00 MG / SELEGILINE , 一般錠劑膠囊劑 , 5.00 MG | 其他 |
| ATC代碼 | 224261 | 0 | N05AF01 / N05AB02 / N04BD01 | ATC code/classification |
| 給付規定章節 | 95547 | 128714 | 1.3.4. / 1.2.1. / 1.2.1.1. | 其他 |
| 藥品代碼超連結 | 224261 | 0 | https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02015924 / https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02020896 / https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02020964 | 健保藥品代碼候選 |
| 給付規定章節連結 | 95364 | 128897 | https://info.nhi.gov.tw/api/INAE3000/INAE3000S01/getPDF?DurgFileName=1.3.4._20220301.pdf / https://info.nhi.gov.tw/api/INAE3000/INAE3000S01/getPDF?DurgFileName=1.2.1._20180301_000.pdf / https://info.nhi.gov.tw/api/INAE3000/INAE3000S01/getPDF?DurgFileName=1.2.1.1._20101001_000.pdf | 其他 |

### 重複鍵候選

| 欄位 | non_null | unique_seen | has_duplicates |
| --- | --- | --- | --- |
| 藥品代號 | 224261 | 45044 | yes |
| 藥品代碼超連結 | 224261 | 23905 | yes |
| ATC代碼 | 224261 | 2240 | yes |

註：`藥品代號` 不是整份歷史給付檔的唯一鍵，因同一藥品會因支付價與有效起迄日有多筆歷史列；後續 staging 需以藥品代號加有效起日/有效迄日或版本批次判讀。

## TFDA license / 36_2.csv

| 項目 | 值 |
| --- | --- |
| local_path | reference_data/drug/raw/tfda_drug_license_20260522.zip |
| inner_file_if_zip | 36_2.csv |
| encoding | utf-8-sig |
| delimiter | , |
| row_count | 71804 |
| column_count | 28 |

### ZIP 內容
| inner_file | uncompressed_size | compressed_size |
| --- | --- | --- |
| 36_2.csv | 44247474 | 9969253 |

### 內部資料檔前 5 行

```text
"許可證字號","註銷狀態","註銷日期","註銷理由","有效日期","發證日期","許可證種類","舊證字號","通關簽審文件編號","中文品名","英文品名","適應症","劑型","包裝","藥品類別","管制藥品分類級別","主成分略述","申請商名稱","申請商地址","申請商統一編號","製造商名稱","製造廠廠址","製造廠公司地址","製造廠國別","製程","異動日期","用法用量","包裝與國際條碼"
"內衛成製字第000143號","已註銷","2013/10/16","自行鍵入","2003/05/01","1969/07/09","製　劑","","DHY01400014305","阿司匹靈錠","ASPIRIN TABLETS ""K.Y.""","解熱、鎮痛劑","錠劑","罐裝;;瓶裝","成藥","","ASPIRIN","洸洋化學製藥股份有限公司","板橋市信義路２６巷１０號","15013427","健康化學製藥股份有限公司","台中市大甲區幼獅工業區幼四路１２號","","TW","","2013/10/16","",
"內衛成製字第000182號","已註銷","2013/09/30","自行鍵入","2003/05/25","1969/09/16","製　劑","","DHY01400018202","綠芳油","RIFON OIL","頭眩鼻塞、頭痛牙痛、風濕骨痛、湯火燙傷、舟車暈浪、止癢消腫","外用液劑","瓶裝","成藥","","METHYL SALICYLATE;;MENTHOL","仙臺藥品工業股份有限公司","台南市新營區新營工業區新工路３５號","71078598","仙臺藥品工業股份有限公司","台南市新營區工業區新工路３５號","","TW","","2013/09/30","",
"內衛成製字第000195號","已註銷","2008/10/06","自請註銷","2008/05/25","1969/10/01","製　劑","","DHY01400019501","複方炭酸氫鈉錠","COMPOUND SODIUM BICARBONATE TABLETS ""PLP""","制酸劑","錠劑","瓶裝","成藥","","SODIUM BICARBONATE ( EQ TO SODIUM HYDROGEN CARBONATE)","臺南蓬萊企業有限公司","台南巿裕農路６６８巷７３號","68888882","仙臺藥品工業股份有限公司","台南縣新營市工業區新工路３５號","","TW","","2008/10/13","",
"內衛成製字第000320號","已註銷","1989/08/17","自請註銷","1990/05/25","1970/03/03","製　劑","","DHY01400032001","紅藥膏”人生”　　　　　　　　　　　　　　　　　　　　　　　 M","RBROMIN OINTMENT ""JEN SHENG""","刀傷、擦傷、火傷等創傷面的消毒","軟膏劑","管裝","成藥","","MERBROMIN","人生製藥股份有限公司","台中巿西屯區工業區五路３號","58003103","人生製藥股份有限公司","台中巿西屯區工業區五路３號","","TW","","2001/12/30","",
```

### 欄位名稱

`許可證字號`, `註銷狀態`, `註銷日期`, `註銷理由`, `有效日期`, `發證日期`, `許可證種類`, `舊證字號`, `通關簽審文件編號`, `中文品名`, `英文品名`, `適應症`, `劑型`, `包裝`, `藥品類別`, `管制藥品分類級別`, `主成分略述`, `申請商名稱`, `申請商地址`, `申請商統一編號`, `製造商名稱`, `製造廠廠址`, `製造廠公司地址`, `製造廠國別`, `製程`, `異動日期`, `用法用量`, `包裝與國際條碼`

### 關鍵欄位判斷

| 判斷項目 | 結果 |
| --- | --- |
| 健保藥品代碼 | 未明確看到 |
| 許可證字號 | 有 |
| 中文藥名/品名 | 有 |
| 英文藥名/品名 | 有 |
| 成分 | 有 |
| 規格/含量 | 未明確看到 |
| 劑型 | 有 |
| 單位 | 未明確看到 |
| 價格/給付 | 未明確看到 |
| 生效日 | 未明確看到 |
| 停用/有效日期/狀態 | 有 |
| ATC code | 未明確看到 |
| 申請商/製造廠 | 有 |

### 前 5 筆樣本

| 許可證字號 | 註銷狀態 | 註銷日期 | 註銷理由 | 有效日期 | 發證日期 | 許可證種類 | 舊證字號 | 通關簽審文件編號 | 中文品名 | 英文品名 | 適應症 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 內衛成製字第000143號 | 已註銷 | 2013/10/16 | 自行鍵入 | 2003/05/01 | 1969/07/09 | 製　劑 |  | DHY01400014305 | 阿司匹靈錠 | ASPIRIN TABLETS "K.Y." | 解熱、鎮痛劑 |
| 內衛成製字第000182號 | 已註銷 | 2013/09/30 | 自行鍵入 | 2003/05/25 | 1969/09/16 | 製　劑 |  | DHY01400018202 | 綠芳油 | RIFON OIL | 頭眩鼻塞、頭痛牙痛、風濕骨痛、湯火燙傷、舟車暈浪、止癢消腫 |
| 內衛成製字第000195號 | 已註銷 | 2008/10/06 | 自請註銷 | 2008/05/25 | 1969/10/01 | 製　劑 |  | DHY01400019501 | 複方炭酸氫鈉錠 | COMPOUND SODIUM BICARBONATE TABLETS "PLP" | 制酸劑 |
| 內衛成製字第000320號 | 已註銷 | 1989/08/17 | 自請註銷 | 1990/05/25 | 1970/03/03 | 製　劑 |  | DHY01400032001 | 紅藥膏”人生”　　　　　　　　　　　　　　　　　　　　　　　 M | RBROMIN OINTMENT "JEN SHENG" | 刀傷、擦傷、火傷等創傷面的消毒 |
| 內衛成製字第000379號 | 已註銷 | 2000/08/04 | 未展延而逾期者 | 1999/04/30 | 1970/04/04 | 製　劑 |  | DHY01400037908 | 山道年錠 | SANTONIUM TABLETS | 驅除蛔蟲 |

### 前 20 個主要欄位空值統計

| 欄位 | non_null | null_count | sample_values | inferred_role |
| --- | --- | --- | --- | --- |
| 許可證字號 | 71804 | 0 | 內衛成製字第000143號 / 內衛成製字第000182號 / 內衛成製字第000195號 | TFDA 許可證 join key 候選 |
| 註銷狀態 | 45472 | 26332 | 已註銷 / 已廢止 | 停用/有效日期/狀態 |
| 註銷日期 | 45654 | 26150 | 2013/10/16 / 2013/09/30 / 2008/10/06 | 停用/有效日期/狀態 |
| 註銷理由 | 45422 | 26382 | 自行鍵入 / 自請註銷 / 未展延而逾期者 | 停用/有效日期/狀態 |
| 有效日期 | 71804 | 0 | 2003/05/01 / 2003/05/25 / 2008/05/25 | 停用/有效日期/狀態 |
| 發證日期 | 71803 | 1 | 1969/07/09 / 1969/09/16 / 1969/10/01 | 其他 |
| 許可證種類 | 71804 | 0 | 製　劑 / 菌　疫 / 體外試劑 | TFDA 許可證 join key 候選 |
| 舊證字號 | 15955 | 55849 | 00000000 / 03007271 / 14003975 | 其他 |
| 通關簽審文件編號 | 69939 | 1865 | DHY01400014305 / DHY01400018202 / DHY01400019501 | 其他 |
| 中文品名 | 71803 | 1 | 阿司匹靈錠 / 綠芳油 / 複方炭酸氫鈉錠 | 中文藥名/品名 |
| 英文品名 | 71701 | 103 | ASPIRIN TABLETS "K.Y." / RIFON OIL / COMPOUND SODIUM BICARBONATE TABLETS "PLP" | 英文藥名/品名 |
| 適應症 | 71743 | 61 | 解熱、鎮痛劑 / 頭眩鼻塞、頭痛牙痛、風濕骨痛、湯火燙傷、舟車暈浪、止癢消腫 / 制酸劑 | 其他 |
| 劑型 | 71794 | 10 | 錠劑 / 外用液劑 / 軟膏劑 | 劑型 |
| 包裝 | 66593 | 5211 | 罐裝;;瓶裝 / 瓶裝 / 管裝 | 其他 |
| 藥品類別 | 71803 | 1 | 成藥 / 醫師藥師藥劑生指示藥品 / 乙類成藥 | 其他 |
| 管制藥品分類級別 | 2129 | 69675 | 第四級管制藥品 / 取消管制藥品註記 / 第三級管制藥品 | 其他 |
| 主成分略述 | 67816 | 3988 | ASPIRIN / METHYL SALICYLATE;;MENTHOL / SODIUM BICARBONATE ( EQ TO SODIUM HYDROGEN CARBONATE) | 成分 |
| 申請商名稱 | 71776 | 28 | 洸洋化學製藥股份有限公司 / 仙臺藥品工業股份有限公司 / 臺南蓬萊企業有限公司 | 廠商/申請商/製造廠 |
| 申請商地址 | 71775 | 29 | 板橋市信義路２６巷１０號 / 台南市新營區新營工業區新工路３５號 / 台南巿裕農路６６８巷７３號 | 廠商/申請商/製造廠 |
| 申請商統一編號 | 69159 | 2645 | 15013427 / 71078598 / 68888882 | 廠商/申請商/製造廠 |

### 重複鍵候選

| 欄位 | non_null | unique_seen | has_duplicates |
| --- | --- | --- | --- |
| 許可證字號 | 71804 | 66322 | yes |
| 許可證種類 | 71804 | 6 | yes |

## TFDA ingredient / 43_2.csv

| 項目 | 值 |
| --- | --- |
| local_path | reference_data/drug/raw/tfda_drug_ingredient_20260522.zip |
| inner_file_if_zip | 43_2.csv |
| encoding | utf-8-sig |
| delimiter | , |
| row_count | 125902 |
| column_count | 7 |

### ZIP 內容
| inner_file | uncompressed_size | compressed_size |
| --- | --- | --- |
| 43_2.csv | 14179951 | 2010454 |

### 內部資料檔前 5 行

```text
"許可證字號","處方標示","成分名稱","成分代碼","含量描述","含量","含量單位"
"內衛成製字第000012號","EACH GM CONTAINS:","UNDECYLENATE ZINC","8404801510","200","200.000000","MG"
"內衛成製字第000012號","EACH GM CONTAINS:","UNDECYLENIC ACID","8404801500","50","50.000000","MG"
"內衛成製字第000029號","EACH 100CC. CONTAINS:","MENTHOL","8408000300","25","25.000000","GM"
"內衛成製字第000029號","EACH 100CC. CONTAINS:","CAMPHOR","8408000100","10","10.000000","GM"
```

### 欄位名稱

`許可證字號`, `處方標示`, `成分名稱`, `成分代碼`, `含量描述`, `含量`, `含量單位`

### 關鍵欄位判斷

| 判斷項目 | 結果 |
| --- | --- |
| 健保藥品代碼 | 未明確看到 |
| 許可證字號 | 有 |
| 中文藥名/品名 | 未明確看到 |
| 英文藥名/品名 | 未明確看到 |
| 成分 | 有 |
| 規格/含量 | 有 |
| 劑型 | 未明確看到 |
| 單位 | 有 |
| 價格/給付 | 未明確看到 |
| 生效日 | 未明確看到 |
| 停用/有效日期/狀態 | 未明確看到 |
| ATC code | 未明確看到 |
| 申請商/製造廠 | 未明確看到 |

### 前 5 筆樣本

| 許可證字號 | 處方標示 | 成分名稱 | 成分代碼 | 含量描述 | 含量 | 含量單位 |
| --- | --- | --- | --- | --- | --- | --- |
| 內衛成製字第000012號 | EACH GM CONTAINS: | UNDECYLENATE ZINC | 8404801510 | 200 | 200.000000 | MG |
| 內衛成製字第000012號 | EACH GM CONTAINS: | UNDECYLENIC ACID | 8404801500 | 50 | 50.000000 | MG |
| 內衛成製字第000029號 | EACH 100CC. CONTAINS: | MENTHOL | 8408000300 | 25 | 25.000000 | GM |
| 內衛成製字第000029號 | EACH 100CC. CONTAINS: | CAMPHOR | 8408000100 | 10 | 10.000000 | GM |
| 內衛成製字第000030號 | EACH GRAM CONTAINS: | SULFADIAZINE | 0824000700 | 500 | 500.000000 | MG |

### 前 20 個主要欄位空值統計

| 欄位 | non_null | null_count | sample_values | inferred_role |
| --- | --- | --- | --- | --- |
| 許可證字號 | 125902 | 0 | 內衛成製字第000012號 / 內衛成製字第000029號 / 內衛成製字第000030號 | TFDA 許可證 join key 候選 |
| 處方標示 | 117577 | 8325 | EACH GM CONTAINS: / EACH 100CC. CONTAINS: / EACH GRAM CONTAINS: | 其他 |
| 成分名稱 | 125884 | 18 | UNDECYLENATE ZINC / UNDECYLENIC ACID / MENTHOL | 成分 |
| 成分代碼 | 125902 | 0 | 8404801510 / 8404801500 / 8408000300 | 成分 |
| 含量描述 | 93782 | 32120 | 200 / 50 / 25 | 規格/含量 |
| 含量 | 108837 | 17065 | 200.000000 / 50.000000 / 25.000000 | 規格/含量 |
| 含量單位 | 122112 | 3790 | MG / GM / I.U. | 規格/含量 |

### 重複鍵候選

| 欄位 | non_null | unique_seen | has_duplicates |
| --- | --- | --- | --- |
| 許可證字號 | 125902 | 62620 | yes |

## TFDA ATC / 41_2.csv

| 項目 | 值 |
| --- | --- |
| local_path | reference_data/drug/raw/tfda_atc_20260522.zip |
| inner_file_if_zip | 41_2.csv |
| encoding | utf-8-sig |
| delimiter | , |
| row_count | 80290 |
| column_count | 5 |

### ZIP 內容
| inner_file | uncompressed_size | compressed_size |
| --- | --- | --- |
| 41_2.csv | 5478587 | 672389 |

### 內部資料檔前 5 行

```text
"許可證字號","主或次項","代碼","英文分類名稱","中文分類名稱"
"內衛成製字第000039號","主","D08AA01","ethacridine lactate",""
"內衛成製字第000040號","主","D08AX01","hydrogen peroxide",""
"內衛成製字第000041號","主","D08AE","Phenol and derivatives",""
"內衛成製字第000042號","主","D08AK04","merbromin",""
```

### 欄位名稱

`許可證字號`, `主或次項`, `代碼`, `英文分類名稱`, `中文分類名稱`

### 關鍵欄位判斷

| 判斷項目 | 結果 |
| --- | --- |
| 健保藥品代碼 | 未明確看到 |
| 許可證字號 | 有 |
| 中文藥名/品名 | 未明確看到 |
| 英文藥名/品名 | 未明確看到 |
| 成分 | 未明確看到 |
| 規格/含量 | 未明確看到 |
| 劑型 | 未明確看到 |
| 單位 | 未明確看到 |
| 價格/給付 | 未明確看到 |
| 生效日 | 未明確看到 |
| 停用/有效日期/狀態 | 未明確看到 |
| ATC code | 有 |
| 申請商/製造廠 | 未明確看到 |

### 前 5 筆樣本

| 許可證字號 | 主或次項 | 代碼 | 英文分類名稱 | 中文分類名稱 |
| --- | --- | --- | --- | --- |
| 內衛成製字第000039號 | 主 | D08AA01 | ethacridine lactate |  |
| 內衛成製字第000040號 | 主 | D08AX01 | hydrogen peroxide |  |
| 內衛成製字第000041號 | 主 | D08AE | Phenol and derivatives |  |
| 內衛成製字第000042號 | 主 | D08AK04 | merbromin |  |
| 內衛成製字第000043號 | 主 | D08AG03 | iodine |  |

### 前 20 個主要欄位空值統計

| 欄位 | non_null | null_count | sample_values | inferred_role |
| --- | --- | --- | --- | --- |
| 許可證字號 | 80290 | 0 | 內衛成製字第000039號 / 內衛成製字第000040號 / 內衛成製字第000041號 | TFDA 許可證 join key 候選 |
| 主或次項 | 80290 | 0 | 主 / 次 | 其他 |
| 代碼 | 80290 | 0 | D08AA01 / D08AX01 / D08AE | 其他 |
| 英文分類名稱 | 75350 | 4940 | ethacridine lactate / hydrogen peroxide / Phenol and derivatives | 其他 |
| 中文分類名稱 | 0 | 80290 |  | 其他 |

### 重複鍵候選

| 欄位 | non_null | unique_seen | has_duplicates |
| --- | --- | --- | --- |
| 許可證字號 | 80290 | 38648 | yes |

## 初步 join 可行性分析

- NHI drug payment 對 `drug_items`：可優先用健保藥品代碼作穩定鍵；若現有 `drug_items` 沒有健保碼，需用中文/英文品名、成分、規格、劑型、廠商做模糊比對。
- TFDA license 對 `drug_items`：可用品名、英文品名、申請商、製造廠、劑型做比對；若 `drug_items` 未保存許可證字號，無法直接 exact join。
- TFDA ingredient 對 TFDA license：若兩者都有許可證字號，應可用許可證字號 join，ingredient 可補成分、含量、單位。
- TFDA ATC 對 TFDA license：若 ATC 檔含許可證字號，應可用許可證字號 join；ATC 可補分類碼。
- NHI 與 TFDA：初步看應先尋找是否有許可證字號或藥品代碼共同欄位；若沒有共同鍵，需要用品名/成分/規格/劑型/廠商做多欄位候選比對，不應直接自動覆蓋正式 `drug_items`。

## 風險點

- NHI 與 TFDA 可能沒有共同穩定鍵，品名與規格文字差異會造成誤配。
- 同一許可證可能有多筆成分或多筆 ATC，需 staging 後 review。
- 藥品支付價、有效日期、狀態欄位需確認語意與版本，不宜直接拿來覆蓋正式藥品資料。
- 原始檔編碼與欄位名稱可能隨下載版本變動，import 腳本需保留 schema profile 與 batch id。

## 下一步 staging schema 建議

- 建議建立獨立 staging，不直接寫 `drug_items`：
  - `official_nhi_drug_payment_staging`：保留健保藥品代碼、藥名、成分/規格/劑型/單位、價格/給付、生效停用欄位、source metadata。
  - `official_tfda_drug_license_staging`：保留許可證字號、中文/英文品名、劑型、申請商、製造廠、狀態、有效日期。
  - `official_tfda_drug_ingredient_staging`：以許可證字號 join license，保存成分、含量、單位與 source row。
  - `official_tfda_atc_staging`：以許可證字號或藥品鍵 join license，保存 ATC code 與分類資訊。
- 再建立 `drug_items_official_match_candidates` 作候選比對，不直接 update `drug_items`。

## 明確限制

本報告不修改資料庫、不建立 table、不清洗 raw data、不 apply、不修改 `drug_items` 或 `drug_diagnosis_links`。

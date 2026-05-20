# 剩餘缺 ICD-10 diagnosis_codes 分批策略報告

## 本階段目的
本報告只做唯讀分析，將剩餘缺 ICD-10 的 `diagnosis_codes` 依健保 ICD-9→ICD-10-CM 對照與官方 ICD-10-CM reference 分批，供後續人工 review。

本報告不修改資料庫、不產生 UPDATE SQL、不 apply、不處理藥品資料、不處理 OCR/photos/prescription。

## 資料來源
| 來源 | 用途 |
| --- | --- |
| diagnosis_codes | 正式診斷碼表，找出 icd10_code 空白者 |
| official_icd10_cm_reference_staging | 健保 ICD-10-CM 官方 reference，確認候選 code 存在與 USE |
| reference_data/icd/nhi_2001_icd9_to_2023_icd10_mapping.xlsx / ICD-9與2023年ICD-10-CM對應 | 健保 ICD-9→ICD-10-CM mapping 來源 |

## 剩餘缺 ICD-10 總覽
| 項目 | 筆數 |
| --- | --- |
| 缺 ICD-10 總筆數 | 175 |
| 缺 ICD-10 且有 ICD-9 | 175 |
| 缺 ICD-10 且缺 ICD-9 | 0 |
| ICD-9 組合碼/多重碼/非純數字 | 4 |
| ICD-9 單一純數字，可嘗試 mapping | 171 |

### name_zh 粗分類
| 分類 | 筆數 |
| --- | --- |
| 其他 | 60 |
| 腎臟 / 泌尿 | 44 |
| 肝膽腸胃 | 22 |
| 皮膚 | 16 |
| 感染 | 16 |
| 糖尿病 / 代謝 | 14 |
| 神經 | 2 |
| 高血壓 / 心血管 | 1 |

## ICD-9 → ICD-10 mapping 分析
| mapping 狀態 | 筆數 |
| --- | --- |
| multiple_mapping | 102 |
| single_mapping | 60 |
| no_mapping | 9 |
| combo_or_non_numeric_icd9 | 4 |

## 分批建議
| 批次 | 定義 | 筆數 |
| --- | --- | --- |
| Batch A | 高信心、單一 mapping、USE=1、語意明確，可優先 review | 50 |
| Batch B | 需要更多來源；含一對多、語意需確認、USE 非 1 等 | 112 |
| Batch C | 不建議自動補；找不到 mapping 或候選不在官方 reference | 9 |
| Batch D | 缺 ICD-9 或 ICD-9 組合碼/多重碼/非純數字，暫緩 | 4 |

### Batch A：最適合下一批 review 的候選
| id | ICD-9 | name_zh | 候選 ICD-10 | 官方中文名 | USE | mapping_count | batch | status | 建議 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 7821 | 皮疹 | R21 | 皮疹及其他非特定性皮膚出疹 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 13 | 2149 | 脂肪瘤 | D17.9 | 良性脂肪瘤 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 18 | 1104 | 足癬 | B35.3 | 足癬 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 19 | 1110 | 汗斑 | B36.0 | 變色糠疹(汗斑) | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 20 | 7089 | 蕁麻疹 | L50.9 | 蕁麻疹 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 21 | 7854 | 壞疽 | I96 | 壞疽，他處未歸類者 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 22 | 71940 | 關節痛 | M25.50 | 關節痛 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 30 | 71610 | 創傷後關節炎 | M12.50 | 未明示部位創傷性關節病變 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 32 | 7231 | 頸椎痛 | M54.2 | 頸椎痛 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 33 | 72479 | 尾椎痛 | M53.3 | 薦尾椎骨疾患，他處未歸類者 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 40 | 7222 | 椎間盤脫出 | M51.9 | 未明示胸椎、胸腰椎及腰薦椎椎間盤疾患 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 41 | 73300 | 骨質疏鬆 | M81.0 | 老年性骨質疏鬆症未伴有病理性骨折 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 42 | 7241 | 胸椎痛 | M54.6 | 胸椎痛 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 52 | 72700 | 肌腱炎 | M65.9 | 其他滑膜炎及腱鞘炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 57 | 73025 | 骨髓炎（骨盆） | M86.9 | 骨髓炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 58 | 73027 | 骨髓炎（踝及腳） | M86.9 | 骨髓炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 63 | 28521 | 腎性貧血 | D63.1 | 慢性腎臟疾病導致的貧血 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 68 | 78841 | 頻尿 | R35.0 | 頻尿 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 71 | 5990 | 泌尿道感染 | N39.0 | 未明示部位之泌尿道感染症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 75 | 5809 | 急性腎絲球腎炎 | N00.9 | 急性腎炎症候群伴有非特異性的組織形態改變 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 77 | 5960 | 膀胱頸攣縮 | N32.0 | 膀胱頸阻塞 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 78 | 5829 | 慢性腎絲球腎炎 | N03.9 | 慢性腎炎症候群伴有非特異性的組織形態改變 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 79 | 59000 | 慢性腎盂腎炎 | N11.0 | 與非阻塞性逆流相關的慢性腎盂腎炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 92 | 6019 | 攝護腺炎 | N41.9 | 攝護腺炎性疾病 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 97 | 5921 | 輸尿管結石 | N20.1 | 輸尿管結石 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 98 | 5932 | 腎囊腫 | N28.1 | 後天性腎囊腫 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 101 | 586 | 尿毒症／慢性腎衰竭，未明示者（末期腎臟病） | N19 | 腎衰竭 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 104 | 78830 | 尿失禁 | R32 | 尿失禁 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 106 | 5941 | 膀胱結石 | N21.0 | 膀胱內結石 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 131 | 2767 | 血鉀過高 | E87.5 | 高血鉀症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 133 | 2810 | 惡性貧血 | D51.0 | 內因子缺乏所致的維生素Ｂ12缺乏性貧血 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 138 | 2875 | 血小板低下 | D69.6 | 血小板缺乏症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 139 | 28521 | 末期腎病導致貧血 | D63.1 | 慢性腎臟疾病導致的貧血 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 142 | 2769 | 電解質及體液失調症 | E87.8 | 其他電解質及體液平衡疾患，他處未歸類者 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 147 | 27540 | 鈣代謝失調 | E83.50 | 未明示之鈣代謝疾患 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 149 | 27542 | 高血鈣 | E83.52 | 高血鈣症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 151 | 2760 | 高滲壓及血鈉過高 | E87.0 | 高滲壓及高血鈉 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 152 | 2761 | 低滲壓及血鈉過高 | E87.1 | 低滲壓及低血鈉 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 154 | 2768 | 血鉀過低 | E87.6 | 低血鉀症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 156 | 0529 | 水痘 | B01.9 | 水痘未伴有併發症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 159 | 0539 | 帶狀泡疹 | B02.9 | 帶狀疱疹未伴有併發症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 161 | 0559 | 麻疹 | B05.9 | 麻疹未伴有併發症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 162 | 0569 | 德國麻疹 | B06.9 | 德國麻疹未伴有併發症 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 163 | 0979 | 梅毒 | A53.9 | 梅毒 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 165 | 57510 | 膽囊炎 | K81.9 | 膽囊炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 167 | 07054 | C 型肝炎 | B18.2 | 慢性病毒性C型肝炎 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 177 | 5724 | 肝腎徵候群 | K76.7 | 肝腎徵候群 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 183 | 86400 | 肝損傷 | S36.119A | 肝臟損傷之初期照護 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 184 | 7824 | 黃疸 | R17 | 黃疸 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |
| 185 | 7892 | 脾腫大 | R16.1 | 脾腫大，他處未歸類者 | 1 | 1 | Batch A | single_mapping_high_confidence | 可列下一批人工 review / approve 候選。 |

### Batch B：需要更多來源（前 40 筆）
| id | ICD-9 | name_zh | 候選 ICD-10 | 官方中文名 | USE | mapping_count | batch | status | 建議 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 6918 | 異位性皮膚炎（過敏性皮膚炎） | L20.0 | 貝斯尼耶氏癢疹 | 1 | 7 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 2 | 69289 | 濕疹 | L23.4 | 染料所致之過敏性接觸性皮膚炎 | 1 | 14 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 3 | 6929 | 接觸性皮膚炎 | L23.9 | 過敏性接觸性皮膚炎，未明示原因 | 1 | 7 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 4 | 7061 | 座瘡（痤瘡） | L70.0 | 尋常性痤瘡 | 1 | 8 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 5 | 9490 | 燙傷 | T30.0 | 未明示身體部位燒傷 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 6 | 6819 | 蜂窩組織炎 | L03.019 | 未明示側性手指蜂窩組織炎 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 7 | 2168 | 皮膚良性腫瘤 | D22.9 | 黑色素細胞痣 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 9 | 6809 | 癤、癰 | L02.92 | 癤 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 10 | 1119 | 癬 | B36.9 | 表淺性黴菌病 | 1 | 1 | Batch B | single_mapping_name_mismatch | 需要人工 review；不可自動補。 |
| 11 | 6829 | 蜂窩組織炎及膿瘍 | L02.91 | 皮膚膿瘍 | 1 | 6 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 12 | 6826 | 其他蜂窩組織炎及膿瘍（下肢、足） | L02.415 | 右側下肢皮膚膿瘍 | 1 | 9 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 14 | 70909 | 白斑症 | L57.3 | Civatte型多形皮膚萎縮症 | 1 | 10 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 15 | 68102 | 甲溝炎 | L03.011 | 右側手指蜂窩組織炎 | 1 | 3 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 16 | 9190 | 表淺損傷 | T07.XXXA | 多處損傷之初期照護 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 23 | 2740 | 痛風性關節病變 | M10.00 | 未明示部位特發性痛風 | 1 | 263 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 25 | 7245 | 下背痛 | M54.89 | 其他背痛 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 26 | 7906 | 尿酸過高 | E79.0 | 高尿酸血症未伴有關節炎及痛風石 | 1 | 9 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 28 | 71600 | 關節炎 | M12.10 | 未明示部位Kaschin-Beck氏病 | 1 | 1 | Batch B | single_mapping_name_mismatch | 需要人工 review；不可自動補。 |
| 29 | 72190 | 僵直性脊椎炎 | M47.20 | 未明示部位其他退化性脊椎炎伴有神經根病變 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 31 | 72982 | 痙攣（四肢） | G47.62 | 睡眠相關之腿抽筋 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 34 | 78039 | 痙攣 | G40.909 | 癲癇，非難治之癲癇，未伴有癲癇重積狀態 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 35 | 8290 | 閉鎖性骨折 | T14.8XXA | 其他身體損傷之初期照護 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 36 | 8291 | 開放性骨折 | T14.8XXA | 其他身體損傷之初期照護 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 37 | 7290 | 纖維組織炎／風濕症 | M79.0 | 風濕病 | 1 | 1 | Batch B | single_mapping_name_mismatch | 需要人工 review；不可自動補。 |
| 38 | 7260 | 冷凍肩（五十肩） | M75.00 | 未明示側性肩部粘連性囊炎 | 1 | 3 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 39 | 72290 | 椎間盤疾患 | M46.40 | 未明示部位椎間盤炎 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 43 | 7140 | 類風濕性關節炎 | M05.70 | 未明示部位類風濕性關節炎伴有類風濕因子，未侵及器官及系統 | 1 | 149 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 44 | 71590 | 骨關節炎（退化性關節炎） | M15.9 | 多發性骨關節炎 | 1 | 2 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 45 | 71696 | 膝關節炎 | M12.9 | 關節病變 | 1 | 1 | Batch B | single_mapping_needs_semantic_review | 需要更多來源確認語意範圍。 |
| 46 | 8489 | 肌肉扭傷拉傷 | T14.90XA | 損傷之初期照護 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 47 | 84500 | 踝扭傷 | S93.401A | 右側踝部韌帶扭傷之初期照護 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 48 | 84210 | 手扭傷 | S63.90XA | 未明示側性腕部及手部未明示部位扭傷之初期照護 | 1 | 6 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 49 | 84200 | 腕扭傷 | S63.501A | 右側腕部扭傷之初期照護 | 1 | 6 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 50 | 8419 | 手肘和前臂扭傷 | S53.401A | 右側手肘扭傷之初期照護 | 1 | 39 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 51 | 3540 | 腕部隧道徵候群 | G56.00 | 未明示側性腕隧道症候群 | 1 | 4 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 53 | 72703 | 扳機指 | M65.30 | 扳機指 | 1 | 16 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 54 | 72705 | 手及手腕肌腱炎 | M65.831 | 右側前臂其他滑膜炎及腱鞘炎 | 1 | 6 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 55 | 72706 | 足及踝肌腱炎 | M65.871 | 右側踝部及足部其他滑膜炎及腱鞘炎 | 1 | 3 | Batch B | multiple_mapping_needs_review | 需要更多來源或人工選碼。 |
| 59 | 27411 | 尿酸腎石病（標記 ✗，見備註） | N20.0 | 腎結石 | 1 | 1 | Batch B | single_mapping_name_mismatch | 需要人工 review；不可自動補。 |
| 60 | 27419 | 其他痛風性腎病變 | M10.30 | 未明示部位腎功能損傷所致的痛風 | 1 | 1 | Batch B | single_mapping_name_mismatch | 需要人工 review；不可自動補。 |

### candidate_status 分布
| candidate_status | 筆數 |
| --- | --- |
| multiple_mapping_needs_review | 102 |
| single_mapping_high_confidence | 50 |
| no_mapping | 9 |
| single_mapping_name_mismatch | 7 |
| combo_or_non_numeric_icd9 | 4 |
| single_mapping_needs_semantic_review | 3 |

## 診所常用類型標記
### 高血壓 / 心血管
| batch | 筆數 |
| --- | --- |
| Batch A | 0 |
| Batch B | 0 |
| Batch C | 1 |
| Batch D | 0 |

### 糖尿病 / 代謝
| batch | 筆數 |
| --- | --- |
| Batch A | 1 |
| Batch B | 11 |
| Batch C | 1 |
| Batch D | 1 |

### 腎臟 / 泌尿
| batch | 筆數 |
| --- | --- |
| Batch A | 15 |
| Batch B | 26 |
| Batch C | 3 |
| Batch D | 0 |

### 肝膽腸胃
| batch | 筆數 |
| --- | --- |
| Batch A | 3 |
| Batch B | 16 |
| Batch C | 1 |
| Batch D | 2 |

### 皮膚
| batch | 筆數 |
| --- | --- |
| Batch A | 6 |
| Batch B | 10 |
| Batch C | 0 |
| Batch D | 0 |

### 感染
| batch | 筆數 |
| --- | --- |
| Batch A | 4 |
| Batch B | 10 |
| Batch C | 1 |
| Batch D | 1 |

### 神經
| batch | 筆數 |
| --- | --- |
| Batch A | 0 |
| Batch B | 2 |
| Batch C | 0 |
| Batch D | 0 |

### 精神
| batch | 筆數 |
| --- | --- |
| Batch A | 0 |
| Batch B | 0 |
| Batch C | 0 |
| Batch D | 0 |

### 其他
| batch | 筆數 |
| --- | --- |
| Batch A | 21 |
| Batch B | 37 |
| Batch C | 2 |
| Batch D | 0 |

## 風險與安全原則
1. 不直接 UPDATE `diagnosis_codes`。
2. 不產生可直接執行的 UPDATE SQL。
3. 一對多 mapping 不可硬選唯一 ICD-10。
4. ICD-9 組合碼/非純數字應暫緩，需人工拆解或其他 evidence。
5. `USE=0` 或官方 reference 查不到者不應自動補。
6. 下一步應先針對 Batch A 產生人工 decision CSV，再走 dry-run / apply plan。

## 輸出
- Markdown：`db_backups/diagnosis_backup_20260505_085955/00_remaining_icd10_batch_strategy_report.md`
- CSV：`db_backups/diagnosis_backup_20260505_085955/remaining_icd10_batch_candidates.csv`

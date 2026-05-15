# Rewrite Handoff v8 — 2026-05-15

> v7（2026-05-11）後一週的密集工作。重點：**「車資試算」外掛搬回**、**skill prompt today 凍結 bug 修**、**Master Agent 結構性改造（1.89x speedup）**。
>
> 目前 dev_line_channel 上面比 main 多 1 個未推的 commit — Master Agent，用戶正在實機驗證中。

---

## 0. TL;DR

| Commit | 狀態 | 重點 |
|---|---|---|
| `df016eb` | **已推 main** | feat(rewrite): 搬「車資試算」回 rewrite — atomic tool + router fast-path |
| `f86da10` | **已推 main** | fix(rewrite/sandbox): skill prompt today 凍結 — 每次 _init 都重 build _skills |
| `4aa846d` + merge | **僅在 dev_line_channel**，**尚未推 main** | feat(rewrite/ai): Master Agent — 合一 25+ atomic tools 成單一 LLM call |

**下個對話一進來該知道**：
1. 用戶在實機驗 Master Agent（dev_line_channel + ngrok）
2. 用戶驗 OK 才協助 merge → main → push（Render auto-deploy）
3. 用戶在中途提了一個小外掛需求（日期 → 下一週/第11週/第12週卡片），尚未實作（見 §6）

---

## 1. 「車資試算」搬回（已推 main）

### 起因
用戶問搬遷時忘了留的「車資試算」還找得到嗎。從 git 找到是 commit `ce39304` (Phase C Wave 2b) 砍掉的：
- `modules/handlers/fare_calc_handler.py` (64 行)
- `modules/services/fare_calculator.py` (262 行)
- `config/taxi_fares.yml` **沒砍**，還在

### 設計判準（重要的哲學定調）
用戶分類「**外掛 vs 主體**」：
- **外掛**特徵：流程固定、可預測、不需 AI 解語意、跟主體 DB 操作獨立
- **主體**特徵：要 AI 解意圖、各種自然語法、多 filter 組合

| 類別 | 性質 | 進入機制 |
|---|---|---|
| 車資試算 | 外掛（純算）| router exact ✓ 本次新增 |
| 資料庫同步 / 幫助 | 外掛（系統）| exact match |
| LIFF 10 個入口 | 外掛（觸發後封閉表單）| exact match set |
| 狀態管理 picker | 用戶提議當外掛（**未實作**，見 §5）| 現在 regex `(.+)的狀態$`（過窄）|
| 班次 / 客戶 / 已完成 / 固定班次 / 帳務 | 主體 | AI |

### 實作（commit `42c8644` → merge `df016eb`）

**新增**：
- `rewrite/tools/fare_calc.py` — atomic tool
  - `calculate_fare(*, distance_km, waiting_min, period, ...)` → ToolResult
  - `format_text(result)` → 純文字渲染
  - `parse_command(text)` → 解析「車資試算 X Y 日間/夜間」（支援全形數字 / # 前綴）
  - **純函數無 session、無 audit log**（不碰 DB）
  - str 參數 coerce（CLAUDE.md 規範）
- `rewrite/tools/test_fare_calc.py` — 7 case regression（起跳內/跨多跳/夜間/coerce/邊界/parse/format）

**改**：
- `rewrite/router.py`
  - import + `_RE_FARE = r'^車資試算\b'` + `rewrite_prefixes` 加 `'車資試算'`
  - `try_route` 早於開 session 走純算路徑
  - `_handle_fare_calc` handler
  - `_send_help` 補車資試算說明
- `rewrite/handlers/sandbox_handler.py`
  - `_QUICK_COMMAND_PREFIXES` 加 `'車資試算'`（v7 §3 規範 — 讓群組無 `/` 也能用 callback）
- `scripts/test_fare_calc.py` — 改 import 指 `rewrite.tools.fare_calc`

### 用法
- 私聊 `車資試算 10 5 夜間` → 「🚕 台南車資試算 ... 合計 385 元」
- 群組 `/車資試算 10 5 夜間` 同上
- 不過 AI，router fast-path，零成本秒回

### 副產品
`config/taxi_fares.yml:29` 結尾殘留 `---` 文件分隔符讓 `yaml.safe_load` 拋 multi-document 例外，目前 fallback 預設值跟 yaml 內容完全一致所以行為對，但 log 會冒警告。已 spawn 一個 task chip（用戶可決定何時做），1 行刪除即可。

---

## 2. Skill prompt today 凍結 bug（已推 main）

### 症狀
用戶 5/14 查「今天 5386 已完成班次」，AI 回 **5/11**（星期一）的結果。今天明明是星期四。

### Root cause
3 個 skill 中招（`completed_trip` / `trip_query` / `trip_mutation`），都這樣寫：

```python
# rewrite/ai/skills/completed_trip.py:28-39
def _system_prompt() -> str:
    today = date.today()   # 算一次
    return f"...今天 = {today.isoformat()}..."

def build_completed_trip_skill() -> Skill:
    return Skill(
        ...
        system_prompt=_system_prompt(),   # f-string 結果存死進 dataclass
    )
```

`sandbox_handler.py:247-258` 的 `_init()` 是 lazy-init：第一次 call 才建 `_skills` dict，之後整個 process 都用同一份。Server 5/11 啟動 → prompt 烤死「今天 = 2026-05-11」→ 不重啟就凍結。

AI 完全照 prompt 行事，所以查「今天」會用 5/11 去找 → 結果是 5/11 的 4 筆，不是 5/14。

### Fix（commit `06880ce` → merge `f86da10`）

把 `_skills = {...}` 從 `if _llm is None:` 內**拉出來**，每次 `_init()` 都重 build：

```python
def _init():
    global _llm, _skills
    if _llm is None:
        _llm = GeminiClient()
    # 每次都重 build — 讓 prompt 內的「今天」跟上系統時鐘
    _skills = { ... 5 skills ... }
```

成本：5 個 dataclass instantiation + 字串 interpolation，亞毫秒級。

驗證：mock `date.today()` 從 5/11 → 5/14 後 rebuild，3 個 skill `system_prompt` 都更新到 5/14。

`customer` / `fixed_schedule` 用 `_SYSTEM_PROMPT` 常數（不含 today），不受影響。intent classifier 也安全。

---

## 3. Master Agent 結構性改造（**dev_line_channel only，未推 main**）

### 動機
用戶反映：
- 「最常用的查詢反而最爛」— 慢（每次 ~5s）、偶爾搞錯
- 不想回指令模式 — 哲學是「自然語言 → AI 解意圖 → 操作 DB」
- 想未來支援圖片 / 多語言

### 現狀（改造前）AI pipeline 慢的根因
```
LLM Call 1: intent.classify(2285 字 prompt, 沒 tools)   ~1.5s
LLM Call 2+: skill agent function calling              ~1.5s × N turns
─────────────────────────
總延遲 3-5s（最壞 6+s）
```

兩個 LLM call 疊加 + 每個 call 用 Gemini 2.5 Flash。

### PoC 驗證

寫了 `scripts/poc_master_agent.py`：對 35 個真實 case 比 baseline vs master agent 的 accuracy + latency。

**結果**（PoC v2 prompt 迭代版）：

| 指標 | Baseline (2 calls) | Master (1 call) |
|---|---|---|
| Accuracy | 32/35 (91%) | **32/35 (91%)** 持平 |
| 平均延遲 | 4.73s | **2.50s** |
| Speedup | — | **1.89x**（砍 2.23s/訊息）|
| Tool 一致 | — | 34/35 (97%) |

3 個兩邊都 fail 的 case 都是 mutation 沒給 reason（AI 想先問用戶 — 是 production 設計，不是 bug）。

### 實作（commit `4aa846d` → merge dev_line_channel）

**新增 `rewrite/ai/skills/master.py`**：
- `build_master_skill()` 合 5 個 sub-skill 的 atomic tools（去重 tool name）成單一 Skill
- `_system_prompt()` 含 `date.today()` — 跟 §2 對齊每次重 build
- prompt 內容：三時間態判別、Tool prefix 分組、地點 query 規則、改類別 mutation 判別等（PoC v2 驗過版本）

**改 `rewrite/handlers/sandbox_handler.py`**：
- `_init()` 加 `_master_skill = build_master_skill()`，仍保留 `_skills` 給 `multi_skill_agent` / `test_multi_skill.py` 用（跑穩可再砍）
- 整段 dispatch 重寫（line 498-635 → 約 50 行）：
  - 砍 intent classify call
  - 砍 last_skill bypass classifier 那段 hack
  - 砍 unknown fallback「不太懂」cliff（master 不會 misroute）
  - 改用 `Agent(_llm, _master_skill).process(...)`
  - `history` prepend 邏輯保留
  - state payload 仍寫 `'last_skill': 'master'`（給 webhook 群組過濾用）
- 砍 `from rewrite.ai.intent import classify` 死 import

**新增 `scripts/poc_master_agent.py`** — 保留供後續 prompt 迭代用。

### 上限預估
- 當前 34 atomic tools 跑得穩
- ~50 tools 預估 OK（業界共識）
- 超過 80-100 切 hierarchical（dispatch agent + domain agent 兩層）
- 預留升級路：tool 物理分組保留（`rewrite/ai/skills/X.py` 結構不動）

### 用戶實機驗證點（**進行中**）

用戶在 dev_line_channel + ngrok 跑這些 case：

1. **速度感**：`查太子龍` / `今天診所班次` / `今天 5386 已完成` — 應該明顯比之前快（PoC 2.5s vs 之前 5s）
2. **多輪對話**：「1077 請假」→ AI 問 reason → 「化療 -30」→ 應接得上（history prepend 邏輯）
3. **純文字 / 閒聊**：「今天是幾月幾日」/「你好嗎」— 之前撞 unknown fallback，現在 master 應該純文字回答
4. **邊界**：「明天龍埔街的狀態」仍走 0b' regex picker（沒改）

### **下個對話該做的（如果用戶驗 OK）**

```bash
git checkout main
git merge dev_line_channel --no-ff -m "merge: Master Agent — 合一 25+ tools 成單一 LLM call"
git push origin main
git checkout dev_line_channel
```

---

## 4. 「狀態管理 vs AI 查詢」分流 — **討論中，未實作**

### 用戶反映的 bug
- `今天龍埔街的狀態` → 命中 0b' regex → status picker（有批次按鈕）
- `今天龍埔街狀態`（少「的」） → 漏接 → AI → trip_query → 普通列表（沒批次按鈕）

**一個「的」字差，整個 UX 路線不同**。

### 用戶想要的分流規則
> **含「狀態」 → 狀態管理 picker（外掛、不過 AI）**
> **不含「狀態」 → AI（任何欄位當查詢條件）**

### 三步實作計畫（**沒動工**）

1. **放寬 picker 入口辨識**：`_RE_STATUS_QUERY = re.compile(r'^/?(.+?)的狀態$')` 改成「含『狀態』字」keyword match。剝掉「狀態」「的」「如何」等綴字後，剩下的丟給 `_parse_status_query` 拆 date + 條件
2. **擴大 picker query 能力**（這是真正限制）— 現在 picker 只用 `customer_short_name`（`sandbox_handler.py:735`），所以「今天診所的狀態」回 0 筆。要擴成：customer_short_name / location / category / driver_id（純數字）
3. **AI 拿掉「狀態」誘惑詞**：`intent.py:44` 「狀態 + 客戶名 = trip_query」/ `trip_query.py:44`「『狀態』通常指班次列表」全清掉

### 邊界 case（要用戶決）
- 「狀態改成請假」「請假狀態」這種 mutation 上下文
- 「批量請假 X」(`_QUICK_COMMAND_PREFIXES` line 290) 跟 picker「全部請假」邏輯重疊，要不要合一？
- 「狀態」單獨一字（沒帶日期/條件）行不行？預設「今天全部」走 picker？
- 跨日 / 區間（`5/9-5/11 龍埔街的狀態`）

### 用戶當前態度
> 「雖然怪，但是目前也運作正常沒出問題」— 用戶選擇**先放著**，優先處理 Master Agent。

下個對話：用戶實機驗 Master Agent OK 後可能會回來談這個。

---

## 5. 用戶中途提的「日期計算」小外掛 — **未實作，用戶取消請求**

用戶在 Master Agent 實機驗證期間提了個小外掛需求，後來中斷了沒讓我做：

> **規格**：用戶輸入特殊字元前綴（`~` 或 `!`），後面加日期（年份可選，沒給就今年）。回 Flex 精美卡片，列：
> - 該日期**下一週**的日期
> - **第 11 週**的日期（**抽血**）
> - **第 12 週**的日期（**回診**）
> - 完整：YYYY 年 MM 月 DD 日 星期 X
> - 例：「據此日期的下一週為 xxxx 年 xx 月 xx 日 星期 x，第十一週為 xxxx 年 xx 月 xx 日 星期 x（抽血）...」

### 設計暗示
- 這是**外掛性質**（跟車資試算同類型）— 純算、不碰 DB
- 應該走 router fast-path（不過 AI）
- 跟「太陽週」概念可能無關（用戶說「下一週/第11週/第12週」是「**該日期 + 7/77/84 天**」這種臨床語境）

### 實作落點建議
- `rewrite/tools/date_calc.py`（atomic tool 純函數）
- `rewrite/views/date_calc_flex.py`（Flex bubble 渲染）
- `rewrite/router.py` 加 `_RE_DATE_CALC = re.compile(r'^[~!]\s*(.+)$')`（謹慎，會跟既有 `!前綴` 衝突！詳見下方）
- `rewrite/handlers/sandbox_handler.py:_QUICK_COMMAND_PREFIXES` 加觸發詞

### **重要的衝突警示**
`!` 前綴目前是 **legacy sandbox 觸發詞**（CLAUDE.md 提到「!明天龍埔街的狀態」），不能直接搶。建議：
- 用 `~` 當前綴（更安全，沒衝突）
- 或要求後面必須接 `日期/` 之類專屬指示詞

下個對話開做前，**先跟用戶確認用 `~` 還是 `!`**，以及衝突處理。

---

## 6. 環境與工作流（不變）

### 部署架構（v7 §7）
| Pair | LINE channel | LIFF Endpoint | Bot 跑在 |
|---|---|---|---|
| **dev** | 派班 dev | ngrok | Mac + ngrok (`dev_line_channel`) |
| **prod** | Linyan | Render | Render (`main` push 自動 deploy) |

### 工作流（**用戶嚴格要求**）
1. 所有改動先 `dev_line_channel` 分支（或 worktree 分支 → merge 進 dev）
2. 本地 Mac + ngrok 連 dev pair 驗證
3. **用戶說 OK** 才 `git checkout main && git merge dev_line_channel --no-ff && git push origin main`
4. 推完切回 `dev_line_channel`
5. **Claude 不直接推 main**

### Worktree
本次工作在 `claude/stupefied-goldwasser-e52c15` worktree（路徑 `/Users/linyancui/minimal_flask/.claude/worktrees/stupefied-goldwasser-e52c15/`），所有 commit 先在 worktree 分支，再從主 repo merge 進 `dev_line_channel`。

---

## 7. 已知 / 待辦

### 🟢 已解決（v8）
- ✅ 車資試算搬回 rewrite
- ✅ skill prompt today 凍結
- ✅ Master Agent（待用戶實機驗）

### 🟡 待用戶決定
- **Master Agent 推 main** — 等用戶驗 OK
- **狀態管理分流** — 用戶說「先放著」
- **日期計算外掛** — 用戶中斷，下次再開

### 🟡 spawn_task chip 未處理
- `config/taxi_fares.yml` 結尾的 `---` 多文件分隔符（1 行刪除即修）

### 🔴 預存問題（跟我們無關）
- `rewrite/tools/test_customer.py` T2 `medical_record_no='001026'` 本機 DB 缺資料 — 永遠 fail，跟改動無關。**不要被誤導以為 commit 弄壞了**

---

## 8. 下個對話的指示

1. **先讀本 handoff**（v8 = `docs/logs/REWRITE_HANDOFF_2026-05-15.md`）
2. **問用戶 Master Agent 驗到哪了**
   - 驗 OK → 協助推 main（指令見 §3 末）
   - 還在驗 / 有問題 → 看 log debug
3. **如果用戶要繼續其他主題**：
   - 「日期計算外掛」見 §5 — 開做前先問 `~` vs `!`
   - 「狀態管理分流」見 §4 — 已規劃好三步驟
4. **絕對不直接推 main** — 用戶嚴格要求
5. **跑 6 regression** 前要 `cd /Users/linyancui/minimal_flask`（在主 repo，不在 worktree，有 venv + service-account key）

### 6 regression（必跑）
```bash
cd /Users/linyancui/minimal_flask
for t in rewrite/tools/test_completed_trip.py \
         rewrite/tools/test_completed_trip_mutations.py \
         rewrite/tools/test_trip.py \
         rewrite/tools/test_customer.py \
         rewrite/views/test_trip_flex_pagination.py \
         rewrite/ai/test_multi_skill.py; do
  venv/bin/python "$t" 2>&1 | tail -2
done
```

預期：5 pass / 1 fail（test_customer T2 預存）。

### Master Agent 端到端 PoC（可重跑）
```bash
cd /Users/linyancui/minimal_flask
venv/bin/python scripts/poc_master_agent.py
# 跑 ~3-5 分鐘，35 case 比對 baseline vs master accuracy + latency
```

---

## 附錄：commit 對照表

```
v7 baseline: ca780b4 docs: handoff v7
v8 累計 commit:

42c8644 feat(rewrite): 搬「車資試算」回 rewrite — atomic tool + router fast-path
96f5941 merge: 搬「車資試算」回 rewrite (router fast-path)
df016eb merge: 搬「車資試算」回 rewrite — atomic tool + router fast-path     ← 推到 main

06880ce fix(rewrite/sandbox): skill prompt today 凍結 — 每次 _init 都重 build _skills
3e1b0d4 merge: fix skill prompt today 凍結（每次 _init 都重 build _skills）
f86da10 merge: fix skill prompt today 凍結（每次 _init 都重 build _skills）   ← 推到 main

4aa846d feat(rewrite/ai): Master Agent — 合一 25+ atomic tools 成單一 LLM call
        merge: Master Agent — 合一 25+ tools 成單一 LLM call (PoC 1.89x speedup)   ← 在 dev_line_channel，未推 main
```

**main 跟 dev_line_channel 差距**：Master Agent merge commit + `4aa846d`（feat commit）。

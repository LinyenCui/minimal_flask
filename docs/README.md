# 文檔目錄結構

> **最後整理**：2026-01-13

---

## 目錄說明

```
docs/
├── architecture/       # 系統架構設計
├── planning/          # 發展計劃與規劃（⭐ 重點）
├── guides/            # 核心功能指南（三時間態、請假邏輯等）
├── user-guides/       # 用戶使用手冊
├── development/       # 開發指南（重構、清理等）
├── installation/      # 安裝與設置指南
├── troubleshooting/   # 故障排除
├── design/            # 設計文檔
├── logs/              # 開發日誌（歷史對話記錄）
└── archive/           # 歸檔（過時但保留的文檔）
```

---

## 重點文檔

### 必讀
| 文檔 | 位置 | 說明 |
|-----|------|------|
| **CLAUDE.md** | 根目錄 | 系統核心指南，開發前必讀 |
| **發展計劃** | `planning/NATURAL_LANGUAGE_DB_EVOLUTION.md` | 沙盒取代主系統的遷移計劃 |

### 核心概念
| 文檔 | 位置 | 說明 |
|-----|------|------|
| 三時間態指南 | `guides/` | 未來態、現在態、過去態的設計 |
| 請假邏輯 | `guides/TRIPS_LEAVE_LOGIC_GUIDE.md` | 三層障眼法設計 |
| AI 架構 | `architecture/AI_AGENT_ARCHITECTURE.md` | Gemini 整合架構 |

### 用戶指南
| 文檔 | 位置 | 說明 |
|-----|------|------|
| 快速入門 | `user-guides/QUICK_START.md` | 基本使用方法 |
| AI 使用指南 | `user-guides/AI_SIMPLE_USAGE_GUIDE.md` | 自然語言操作 |
| 報表指南 | `user-guides/REPORTS_GUIDE.md` | 週報、月報生成 |

---

## 系統特色

### 三時間態設計（生產線思維）
- **未來態** (`fixed_schedules`): 模板，尚未匯入
- **現在態** (`trips`): 生產線上的班次
- **過去態** (`completed_trips`): 已完成的班次

### AI 智能操作
- **自然語言理解**: Gemini Function Calling
- **沙盒系統**: 新架構試驗田
- **雙軌制**: AI + 傳統命令並行

### 請假三層障眼法
- 用戶看：「班次已請假」
- 系統實現：狀態維持「準備」
- 業務邏輯：正常流轉，保持統計準確

---

## 快速開始

1. **環境設置**: 參考 [安裝指南](./installation/SETUP_GUIDE.md)
2. **核心概念**: 閱讀根目錄的 `CLAUDE.md`
3. **發展方向**: 查看 `planning/NATURAL_LANGUAGE_DB_EVOLUTION.md`

---

## 歸檔說明

`archive/` 目錄包含：
- 過去的 Session 記錄
- 已完成的修復摘要
- 舊版本的設計文檔

這些文檔**不再維護**，僅供歷史參考。

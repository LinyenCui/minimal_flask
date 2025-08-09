# modules/flex_designs/help_flex.py
def get_help_flex():
    """生成幫助信息的Flex Message"""
    help_bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📚 系統功能總覽", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#4682B4", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                # 第一層：常用功能
                {"type": "text", "text": "🎯 常用功能", "weight": "bold", "size": "sm", "color": "#2E8B57", "margin": "md"},
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔍 東洋班次", "text": "東洋班次"},
                    "style": "primary", "color": "#1E90FF", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🏥 診所班次", "data": "action=query_clinic_trips_date_select", "displayText": "診所班次"},
                    "style": "primary", "color": "#6A5ACD", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "📝 預約叫車", "text": "預約叫車"},
                    "style": "primary", "color": "#FF6B6E", "margin": "sm", "height": "sm"
                },
                
                # 新增：系統指南
                {"type": "text", "text": "📖 系統指南", "weight": "bold", "size": "sm", "color": "#FF8C00", "margin": "md"},
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🏭 生產線思維指南", "data": "action=help_production_line", "displayText": "生產線思維指南"},
                    "style": "primary", "color": "#FF8C00", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "⚡ 快速參考", "data": "action=help_quick_reference", "displayText": "快速參考"},
                    "style": "primary", "color": "#32CD32", "margin": "sm", "height": "sm"
                },
                
                # 第二層：進階功能
                {"type": "text", "text": "🚀 進階功能", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🤖 AI功能說明", "data": "action=help_ai_features", "displayText": "AI功能說明"},
                    "style": "secondary", "color": "#32CD32", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🔮 未來時間態", "data": "action=help_future_mode", "displayText": "未來時間態說明"},
                    "style": "secondary", "color": "#9370DB", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "📋 固定班次功能", "data": "action=help_fixed_schedule", "displayText": "固定班次功能"},
                    "style": "secondary", "color": "#DDA0DD", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🔧 請假與狀態", "data": "action=help_leave_status", "displayText": "請假與狀態"},
                    "style": "secondary", "color": "#20B2AA", "margin": "sm", "height": "sm"
                },
                
                # 第三層：管理功能
                {"type": "text", "text": "⚙️ 管理功能", "weight": "bold", "size": "sm", "color": "#8B4513", "margin": "md"},
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "📊 報表與匯出", "data": "action=help_reports", "displayText": "報表與匯出"},
                    "style": "secondary", "color": "#4169E1", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🛠️ 維護工具", "data": "action=help_maintenance", "displayText": "維護工具"},
                    "style": "secondary", "color": "#B22222", "margin": "sm", "height": "sm"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "💡 點擊按鈕查看詳細說明", "size": "xs", "color": "#888888", "align": "center"},
                {"type": "text", "text": "或輸入「完整指令」查看所有指令", "size": "xs", "color": "#888888", "align": "center"}
            ]
        }
    }
    return help_bubble


def get_future_mode_help():
    """未來時間態功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔮 未來時間態功能", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#9370DB", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📅 太陽週次匯入", "weight": "bold", "size": "sm", "color": "#9370DB"},
                {"type": "text", "text": "• 匯入固定班次 本週", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 匯入固定班次 下週", "size": "xs"},
                {"type": "text", "text": "• 支援太陽週次（週日到週六）", "size": "xs"},
                {"type": "text", "text": "• 本週：追加模式（不清空現有）", "size": "xs"},
                {"type": "text", "text": "• 下週：規劃模式（清空重新規劃）", "size": "xs"},
                
                {"type": "text", "text": "🔄 覆蓋功能", "weight": "bold", "size": "sm", "color": "#FF8C00", "margin": "md"},
                {"type": "text", "text": "• 匯入固定班次 [週次] 覆蓋", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 覆蓋已存在的該週次固定班次", "size": "xs"},
                {"type": "text", "text": "• 警告：會讓原先的班次修改失效", "size": "xs"},
                
                {"type": "text", "text": "🗑️ 清理功能（獨立）", "weight": "bold", "size": "sm", "color": "#DC143C", "margin": "md"},
                {"type": "text", "text": "• 清理trips 已完成", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 清理trips 過去", "size": "xs"},
                {"type": "text", "text": "• 清理trips 全部", "size": "xs"},
                {"type": "text", "text": "• 不影響當前和未來的班次", "size": "xs"},
                
                {"type": "text", "text": "🚫 安全限制", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 不允許匯入過去時間態", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 禁止：匯入固定班次 上週", "size": "xs"},
                {"type": "text", "text": "• 防止：過去時間態數據污染", "size": "xs"},
                
                {"type": "text", "text": "📝 預約系統", "weight": "bold", "size": "sm", "color": "#FF6B6E", "margin": "md"},
                {"type": "text", "text": "• 預約叫車 - AI自然語言預約", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 支援未來日期預約", "size": "xs"},
                {"type": "text", "text": "• 智能時間規劃", "size": "xs"},
                
                {"type": "text", "text": "🔧 固定班表管理", "weight": "bold", "size": "sm", "color": "#DDA0DD", "margin": "md"},
                {"type": "text", "text": "• /固定班表 [客戶簡稱]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 查詢與編輯固定排程", "size": "xs"},
                {"type": "text", "text": "• 長期請假管理", "size": "xs"},
                
                {"type": "text", "text": "💡 使用範例", "weight": "bold", "size": "sm", "color": "#32CD32", "margin": "md"},
                {"type": "text", "text": "匯入固定班次 下週", "size": "xs", "margin": "sm", "color": "#0066CC"},
                {"type": "text", "text": "匯入固定班次 本週 覆蓋", "size": "xs", "color": "#0066CC"},
                {"type": "text", "text": "清理trips 已完成", "size": "xs", "color": "#0066CC"},
                {"type": "text", "text": "預約叫車", "size": "xs", "color": "#0066CC"},
                {"type": "text", "text": "/固定班表 信智", "size": "xs", "color": "#0066CC"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_ai_features_help():
    """AI功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🤖 智能助手系統", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#32CD32", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🧠 智能命令解析", "weight": "bold", "size": "sm", "color": "#2E8B57"},
                {"type": "text", "text": "自然語言理解，不需要記憶指令格式", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 匯入本週固定班次 → 系統自動理解", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 今天診所班次查詢 → 自動轉換", "size": "xs"},
                {"type": "text", "text": "• 班次1896請假感冒 → 智能處理", "size": "xs"},
                
                {"type": "text", "text": "🎯 上下文引導", "weight": "bold", "size": "sm", "color": "#2E8B57", "margin": "md"},
                {"type": "text", "text": "當不確定意圖時，提供友善選項", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 自動提供可能的操作選項", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 避免「未識別命令」的困擾", "size": "xs"},
                {"type": "text", "text": "• 像真人一樣引導操作", "size": "xs"},
                
                {"type": "text", "text": "🔍 真正的AI查詢", "weight": "bold", "size": "sm", "color": "#2E8B57", "margin": "md"},
                {"type": "text", "text": "使用Gemini API進行深度理解", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 7/12司機5386診所班次 ✓", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 查詢今天車資 ✓", "size": "xs"},
                {"type": "text", "text": "• 修改班次123車資500 ✓", "size": "xs"},
                
                {"type": "text", "text": "⚡ 使用體驗", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 像跟真人對話一樣自然", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 自動選擇最適合的處理方式", "size": "xs"},
                {"type": "text", "text": "• 智能後備，確保操作成功", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_fixed_schedule_help():
    """固定班次功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📋 固定班次功能", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#DDA0DD", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔍 查詢固定班次", "weight": "bold", "size": "sm", "color": "#8B008B"},
                {"type": "text", "text": "• /固定班表 [客戶簡稱]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: /固定班表 診所", "size": "xs"},
                
                {"type": "text", "text": "📥 匯入功能", "weight": "bold", "size": "sm", "color": "#8B008B", "margin": "md"},
                {"type": "text", "text": "• 匯入固定班次 [月/日]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: 匯入固定班次 6/1", "size": "xs"},
                
                {"type": "text", "text": "🔵 長期請假功能", "weight": "bold", "size": "sm", "color": "#8B008B", "margin": "md"},
                {"type": "text", "text": "適用於住院、出國等長期請假", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 固定班次請假 [ID] [加成] [原因]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 固定班次恢復 [ID]", "size": "xs"},
                {"type": "text", "text": "• 範例: 固定班次請假 5 -50 住院", "size": "xs"},
                
                {"type": "text", "text": "💡 特色", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 一次設定，自動應用所有匯入", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 支援負加成（車資減免）", "size": "xs"},
                {"type": "text", "text": "• 可隨時恢復正常狀態", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_leave_status_help():
    """請假與狀態功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔧 請假與狀態", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#20B2AA", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔵 乘客請假", "weight": "bold", "size": "sm", "color": "#008B8B"},
                {"type": "text", "text": "• 乘客請假 [班次ID] [加成] [原因]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: 乘客請假 123 -30 生病", "size": "xs"},
                
                {"type": "text", "text": "🔄 狀態修改", "weight": "bold", "size": "sm", "color": "#008B8B", "margin": "md"},
                {"type": "text", "text": "• 班次詳情 [ID] - 查看並修改", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 可改為：準備/註銷/衝突/請假", "size": "xs"},
                
                {"type": "text", "text": "⏰ 30分鐘限制", "weight": "bold", "size": "sm", "color": "#008B8B", "margin": "md"},
                {"type": "text", "text": "執行前30分鐘內不可修改狀態", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 防止臨時變更影響排班", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 確保有充足準備時間", "size": "xs"},
                {"type": "text", "text": "• 指派司機功能不受限制", "size": "xs"},
                
                {"type": "text", "text": "💡 統一邏輯", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 請假不改變業務流程狀態", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 請假班次依然會正常執行", "size": "xs"},
                {"type": "text", "text": "• 只影響車資（通常為負加成）", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_reports_help():
    """報表與匯出功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📊 報表與匯出", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#4169E1", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📈 週報表功能", "weight": "bold", "size": "sm", "color": "#0000CD"},
                {"type": "text", "text": "• 生成周報表 [類別]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: 生成周報表 東洋", "size": "xs"},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": "📅 月報表功能", "weight": "bold", "size": "sm", "color": "#0000CD"},
                {"type": "text", "text": "• 生成月報表 [類別]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: 生成月報表 診所", "size": "xs"},
                {"type": "text", "text": "• 類別: 診所/東洋/全部", "size": "xs"},
                
                {"type": "text", "text": "☁️ Google Drive", "weight": "bold", "size": "sm", "color": "#0000CD", "margin": "md"},
                {"type": "text", "text": "自動上傳到對應資料夾", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "• 診所報表 → 診所資料夾", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 東洋報表 → 東洋資料夾", "size": "xs"},
                {"type": "text", "text": "• 包含修改原因和請假原因", "size": "xs"},
                
                {"type": "text", "text": "🔍 其他查詢", "weight": "bold", "size": "sm", "color": "#0000CD", "margin": "md"},
                {"type": "text", "text": "• 查已完成 [日期] [類別]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 範例: 查已完成 6/1 東洋", "size": "xs"},
                {"type": "text", "text": "• 查看 [ID] - 已完成班次詳情", "size": "xs"},
                
                {"type": "text", "text": "💡 報表特色", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• Excel格式，包含所有必要欄位", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 動態標題（診所/東洋/全部）", "size": "xs"},
                {"type": "text", "text": "• 合併說明欄位", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_maintenance_help():
    """維護工具功能說明"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🛠️ 維護工具", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#B22222", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "⚙️ 系統維護", "weight": "bold", "size": "sm", "color": "#8B0000"},
                {"type": "text", "text": "• 更新已完成班次", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 待派班次 - 查看未指派班次", "size": "xs"},
                {"type": "text", "text": "• 指派司機 [ID] - 指派司機", "size": "xs"},
                {"type": "text", "text": "• 資料庫同步 - 檢查並確認同步", "size": "xs"},
                {"type": "text", "text": "• 確認同步 - 執行快速同步（群組回覆）", "size": "xs"},
                {"type": "text", "text": "• 同步結果 - 查看最後同步詳細結果", "size": "xs"},
                
                {"type": "text", "text": "🔧 資料修復", "weight": "bold", "size": "sm", "color": "#8B0000", "margin": "md"},
                {"type": "text", "text": "• /fix-sequence - 修復序列", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 解決資料匯入後的ID衝突", "size": "xs"},
                {"type": "text", "text": "• 自動檢測並修復序列問題", "size": "xs"},
                {"type": "text", "text": "• 網頁版工具: 輸入 /fix-sequence 查看網址", "size": "xs"},
                
                {"type": "text", "text": "💰 車資管理", "weight": "bold", "size": "sm", "color": "#8B0000", "margin": "md"},
                {"type": "text", "text": "• 記錄車資 [ID] [錶價] [加成]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 修改車資 [ID] [錶價] [加成]", "size": "xs"},
                {"type": "text", "text": "• 修改類別 [ID] [新類別]", "size": "xs"},
                {"type": "text", "text": "• 範例: 記錄車資 123 450 50", "size": "xs"},
                
                {"type": "text", "text": "💎 批量加成功能", "weight": "bold", "size": "sm", "color": "#FFD700", "margin": "md"},
                {"type": "text", "text": "問答式批量加成，適用於春節、颱風假等", "size": "xs", "color": "#666666", "wrap": True},
                {"type": "text", "text": "1️⃣ 輸入: 批量加成", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "2️⃣ 日期: 7/7 或 7/7-7/10", "size": "xs"},
                {"type": "text", "text": "3️⃣ 類別: 診所/東洋/全部", "size": "xs"},
                {"type": "text", "text": "4️⃣ 金額: 50 (正整數)", "size": "xs"},
                {"type": "text", "text": "5️⃣ 原因: 春節假期加成", "size": "xs"},
                {"type": "text", "text": "6️⃣ 確認: 確認 (執行批量更新)", "size": "xs"},
                
                {"type": "text", "text": "⚠️ 注意事項", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 維護工具需謹慎使用", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 資料修復前建議先備份", "size": "xs"},
                {"type": "text", "text": "• 有問題時建議查看日誌", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_production_line_help():
    """生產線思維指南"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🏭 生產線派班思維", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#FF8C00", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🎯 核心概念", "weight": "bold", "size": "sm", "color": "#FF6347"},
                {"type": "text", "text": "將班次管理比喻為日夜不停的自動化生產線", "size": "xs", "color": "#666666", "wrap": True},
                
                {"type": "text", "text": "⏰ 三時間態架構", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 未來態（整備區域）：fixed_schedules", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "  原料模板，規劃準備中", "size": "xs", "margin": "sm", "color": "#666666"},
                {"type": "text", "text": "• 現在態（生產線）：trips表", "size": "xs"},
                {"type": "text", "text": "  正在流動執行的產品", "size": "xs", "margin": "sm", "color": "#666666"},
                {"type": "text", "text": "• 過去態（成品倉庫）：completed_trips", "size": "xs"},
                {"type": "text", "text": "  已完成的產品記錄", "size": "xs", "margin": "sm", "color": "#666666"},
                
                {"type": "text", "text": "👨‍🔧 工作人員干預", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 請假：標記瑕疵但繼續流程", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 註銷/衝突：從生產線拿掉", "size": "xs"},
                {"type": "text", "text": "• 指派司機：分配工作人員", "size": "xs"},
                
                {"type": "text", "text": "🤖 AI智能理解", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 「明天司機5386所有班次」", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• AI理解：查詢生產線上明天的班次", "size": "xs"},
                {"type": "text", "text": "• 自動生成正確查詢條件", "size": "xs"},
                
                {"type": "text", "text": "📋 實際操作", "weight": "bold", "size": "sm", "color": "#32CD32", "margin": "md"},
                {"type": "text", "text": "• 匯入固定班次 = 投料到生產線", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 更新已完成班次 = 自動收成", "size": "xs"},
                {"type": "text", "text": "• 查詢班次 = 監控生產狀況", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "📚 高級請假系統", "data": "action=help_advanced_leave", "displayText": "高級請假系統"},
                    "style": "primary", "color": "#9370DB", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_quick_reference_help():
    """快速參考指南"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "⚡ 快速參考指南", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#32CD32", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔮 未來態操作", "weight": "bold", "size": "sm", "color": "#9370DB"},
                {"type": "text", "text": "• 匯入固定班次 [本週/下週]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 預約叫車", "size": "xs"},
                {"type": "text", "text": "• /固定班表 [客戶]", "size": "xs"},
                {"type": "text", "text": "• 固定班次請假 [ID] [加成] [原因]", "size": "xs"},
                
                {"type": "text", "text": "⏰ 現在態操作", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 東洋班次 / 診所班次", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 班次詳情 [ID]", "size": "xs"},
                {"type": "text", "text": "• 指派司機 [ID]", "size": "xs"},
                {"type": "text", "text": "• 乘客請假 [ID] [加成] [原因]", "size": "xs"},
                
                {"type": "text", "text": "📚 過去態操作", "weight": "bold", "size": "sm", "color": "#2E8B57", "margin": "md"},
                {"type": "text", "text": "• 查已完成 [日期] [類別]", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 記錄車資 [ID] [錶價] [加成]", "size": "xs"},
                {"type": "text", "text": "• 生成周報表 [類別]", "size": "xs"},
                {"type": "text", "text": "• 生成月報表 [類別]", "size": "xs"},
                
                {"type": "text", "text": "🎯 狀態快速識別", "weight": "bold", "size": "sm", "color": "#FF8C00", "margin": "md"},
                {"type": "text", "text": "• 待派：紅色 🔴 需要指派司機", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 準備：綠色 🟢 已準備好執行", "size": "xs"},
                {"type": "text", "text": "• 請假：黃色 🟡 請假(原因)", "size": "xs"},
                {"type": "text", "text": "• 註銷：灰色 ⚫ 不執行", "size": "xs"},
                {"type": "text", "text": "• 衝突：橙色 🟠 時間衝突", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_advanced_leave_help():
    """高級請假系統解析"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📚 高級請假系統", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#9370DB", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🎭 三層次障眼法", "weight": "bold", "size": "sm", "color": "#8B008B"},
                {"type": "text", "text": "請假是一種巧妙的「障眼法」設計", "size": "xs", "color": "#666666", "wrap": True},
                
                {"type": "text", "text": "第一層（表面顯示）", "weight": "bold", "size": "xs", "color": "#8B008B", "margin": "md"},
                {"type": "text", "text": "• 用戶看到「請假(感冒)」", "size": "xs", "margin": "sm"},
                
                {"type": "text", "text": "第二層（系統實現）", "weight": "bold", "size": "xs", "color": "#8B008B", "margin": "md"},
                {"type": "text", "text": "• status='準備'（正常狀態）", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• passenger_leave_reason='感冒'", "size": "xs"},
                
                {"type": "text", "text": "第三層（生產線邏輯）", "weight": "bold", "size": "xs", "color": "#8B008B", "margin": "md"},
                {"type": "text", "text": "• 正常執行所有業務流程", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 自動掉入 completed_trips", "size": "xs"},
                {"type": "text", "text": "• 車資通常為負數或零", "size": "xs"},
                
                {"type": "text", "text": "🔄 三種請假模式", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 臨時請假（現在態）：trips表", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 長期請假（未來態）：fixed_schedules", "size": "xs"},
                {"type": "text", "text": "• 跨時間態恢復：自動傳承機制", "size": "xs"},
                
                {"type": "text", "text": "🎯 設計哲學", "weight": "bold", "size": "sm", "color": "#32CD32", "margin": "md"},
                {"type": "text", "text": "讓複雜的業務需求在簡潔的技術架構上優雅地運行", "size": "xs", "color": "#666666", "wrap": True, "margin": "sm"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }


def get_complete_commands_help():
    """完整指令列表"""
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📜 完整指令列表", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#4682B4", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔮 未來時間態", "weight": "bold", "size": "sm", "color": "#9370DB"},
                {"type": "text", "text": "• 匯入固定班次 [週次] - 太陽週次匯入", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 預約叫車 - AI自然語言預約", "size": "xs"},
                {"type": "text", "text": "• /固定班表 [客戶] - 查詢固定班次", "size": "xs"},
                
                {"type": "text", "text": "⏰ 現在時間態", "weight": "bold", "size": "sm", "color": "#FF6347", "margin": "md"},
                {"type": "text", "text": "• 東洋班次 - 查詢東洋/臨時班次", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 診所班次 - 查詢診所班次", "size": "xs"},
                {"type": "text", "text": "• 班次詳情 [ID] - 查看班次詳情", "size": "xs"},
                {"type": "text", "text": "• 指派司機 [ID] - 指派司機", "size": "xs"},
                {"type": "text", "text": "• 乘客請假 [ID] [加成] [原因]", "size": "xs"},
                
                {"type": "text", "text": "📚 過去時間態", "weight": "bold", "size": "sm", "color": "#2E8B57", "margin": "md"},
                {"type": "text", "text": "• 查已完成 [日期] [類別] - 查已完成班次", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 查看 [ID] - 查看已完成班次詳情", "size": "xs"},
                {"type": "text", "text": "• 記錄車資 [ID] [錶價] [加成]", "size": "xs"},
                {"type": "text", "text": "• 生成周報表 [類別] - 週報表", "size": "xs"},
                {"type": "text", "text": "• 生成月報表 [類別] - 月報表", "size": "xs"},
                
                {"type": "text", "text": "🛠️ 特殊功能", "weight": "bold", "size": "sm", "color": "#32CD32", "margin": "md"},
                {"type": "text", "text": "• 批量加成 - 問答式批量加成", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 查詢[地點/日期]車資 - AI車資查詢", "size": "xs"},
                {"type": "text", "text": "• 修改班次[ID]車資[金額] - AI車資修改", "size": "xs"},
                
                {"type": "text", "text": "📖 系統指南", "weight": "bold", "size": "sm", "color": "#FF8C00", "margin": "md"},
                {"type": "text", "text": "• 生產線思維指南 - 核心概念與架構", "size": "xs", "margin": "sm"},
                {"type": "text", "text": "• 快速參考 - 操作速查與狀態識別", "size": "xs"},
                {"type": "text", "text": "• 高級請假系統 - 障眼法設計解析", "size": "xs"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔙 返回幫助", "text": "幫助"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        }
    }

# modules/flex_designs/help_flex.py
def get_help_flex():
    """生成幫助信息的Flex Message"""
    help_bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "常用功能", "weight": "bold", "size": "md", "color": "#ffffff"}
            ],
            "backgroundColor": "#4682B4", "paddingTop": "8px", "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔍 查詢班次", "text": "查詢班次"},
                    "style": "primary", "color": "#1E90FF", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🏥 診所班次", "data": "action=query_clinic_trips_date_select", "displayText": "診所班次"},
                    "style": "primary", "color": "#6A5ACD", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "📝 預約叫車 (AI推薦)", "text": "預約叫車"},
                    "style": "primary", "color": "#FF6B6E", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "📋 固定班表查詢", "text": "/固定班表 "},
                    "style": "primary", "color": "#32CD32", "margin": "sm", "height": "sm"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "📄 顯示完整指令", "data": "action=help_text", "displayText": "幫助文字"},
                    "style": "secondary", "margin": "sm", "height": "sm"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "輸入「預約叫車幫助」或「幫助文字」查看指令", "size": "xs", "color": "#888888", "align": "center"}
            ]
        }
    }
    return help_bubble

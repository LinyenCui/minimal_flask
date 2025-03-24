# modules/flex_designs/help_flex.py
def get_help_flex():
    """生成幫助信息的Flex Message"""
    help_bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "可用命令列表",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#4682B4",
            "paddingTop": "8px",
            "paddingBottom": "8px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "🔍 查詢班次",
                        "data": "action=query_trips",
                        "displayText": "查詢班次"
                    },
                    "style": "primary",
                    "color": "#1E90FF",
                    "margin": "sm",
                    "height": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "📋 查詢固定班次",
                        "data": "action=query_fixed_trips",
                        "displayText": "查詢固定班次"
                    },
                    "style": "primary",
                    "color": "#6A5ACD",
                    "margin": "sm",
                    "height": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "🔄 修改班次狀態",
                        "data": "action=update_status",
                        "displayText": "修改狀態"
                    },
                    "style": "primary",
                    "color": "#FF8C00",
                    "margin": "sm",
                    "height": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "📄 顯示文字版幫助",
                        "data": "action=help",
                        "displayText": "幫助文字"
                    },
                    "style": "secondary",
                    "margin": "sm",
                    "height": "sm"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "按鈕操作在群組中無需使用前綴",
                    "size": "xs",
                    "color": "#888888",
                    "align": "center"
                }
            ]
        }
    }
    
    return help_bubble

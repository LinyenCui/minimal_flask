"""
互動式 REPL — 在 Mac 終端機跟 rewrite agent 聊天，看實際反應

使用：
  cd /Users/linyancui/minimal_flask
  source venv/bin/activate
  python rewrite/ai/repl.py

輸入 :q 或 :quit 或 ctrl-d 退出。
flex 訊息會簡化成文字（顯示 altText + bubble header），實際 LINE 上會是
富格式卡片。
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from rewrite.ai.multi_skill_agent import build_default_multi_skill_agent


def render_msg_for_terminal(msg: dict) -> str:
    """LINE message dict → 終端機可讀文字"""
    t = msg.get('type')
    if t == 'text':
        return msg.get('text', '')

    if t == 'flex':
        alt = msg.get('altText', '')
        c = msg.get('contents', {})
        ct = c.get('type')
        out = [f"📱 [flex] {alt}"]

        if ct == 'bubble':
            header_parts = c.get('header', {}).get('contents', [])
            if header_parts:
                out.append(f"   ┌─ {header_parts[0].get('text', '')}")
            body_parts = c.get('body', {}).get('contents', [])
            for bp in body_parts[:30]:
                if bp.get('type') == 'box':
                    items = bp.get('contents', [])
                    line = '   │ '
                    for it in items:
                        if it.get('type') == 'text':
                            line += it.get('text', '') + '  '
                    out.append(line.rstrip())
                elif bp.get('type') == 'separator':
                    out.append('   │ ───')

        elif ct == 'carousel':
            bubbles = c.get('contents', [])
            out.append(f"   ┌─ carousel ({len(bubbles)} 張)")
            for i, b in enumerate(bubbles):
                hp = b.get('header', {}).get('contents', [])
                if hp:
                    title = hp[0].get('text', '')
                    sub = hp[1].get('text', '') if len(hp) > 1 else ''
                    out.append(f"   │  {i+1}. {title} / {sub}")

        if msg.get('quickReply'):
            qr_labels = [
                i['action']['label']
                for i in msg['quickReply'].get('items', [])
            ]
            out.append(f"   └─ 快速回覆：{qr_labels}")
        return '\n'.join(out)

    return str(msg)


def main():
    print('🤖 rewrite v0.1 agent REPL')
    print('   (3 skill：trip_query / trip_mutation / customer)')
    print('   輸入 :q 退出，:reset 重新建 agent')
    print()

    agent = build_default_multi_skill_agent()
    print('✅ Agent 初始化完成')

    while True:
        try:
            text = input('\n💬 你> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n👋 bye')
            return

        if not text:
            continue
        if text in (':q', ':quit', ':exit'):
            print('👋 bye')
            return
        if text == ':reset':
            agent = build_default_multi_skill_agent()
            print('🔄 Agent 重新初始化')
            continue

        try:
            msg = agent.process(text, user_id='repl_user')
            print('\n🤖 ' + render_msg_for_terminal(msg))
        except Exception as e:
            import traceback
            print(f'\n⚠️ 錯誤：{e}')
            traceback.print_exc()


if __name__ == '__main__':
    main()

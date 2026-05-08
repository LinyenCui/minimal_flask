"""Phase A 健康檢查 — 用來驗 blueprint 註冊 / env / idToken 流程

- GET  /liff/health        無需 auth，看 env 是否設好
- GET  /liff/whoami_test   無需 auth，回 HTML 測試頁（在 LINE in-app browser 開）
- POST /liff/whoami        需 idToken，驗證成功回 user_id
"""
import os

from flask import jsonify, render_template, request

from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required


@liff_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'ok': True,
        'liff_id_set': bool(os.environ.get('LIFF_ID')),
        'channel_id_set': bool(os.environ.get('LIFF_CHANNEL_ID')),
    })


@liff_bp.route('/whoami', methods=['POST'])
@liff_auth_required
def whoami():
    return jsonify({
        'ok': True,
        'user_id': request.line_user_id,
        'name': request.line_user_name,
    })


@liff_bp.route('/whoami_test', methods=['GET'])
def whoami_test():
    return render_template('liff/whoami_test.html', liff_id=os.environ.get('LIFF_ID', ''))

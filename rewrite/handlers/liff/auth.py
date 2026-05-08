"""LIFF idToken 驗證

LIFF 前端 liff.getIDToken() 會回一個 JWT，前端把它放 Authorization: Bearer <token>
送來。後端打 LINE 的 verify endpoint 驗簽 + 校驗 client_id 一致，成功的話 claims
裡的 sub 就是這次請求的 LINE userId。
"""
import functools
import logging
import os
from typing import Callable, Optional

import requests
from flask import jsonify, request

logger = logging.getLogger(__name__)

LIFF_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"


def verify_line_id_token(id_token: str) -> Optional[dict]:
    channel_id = os.environ.get('LIFF_CHANNEL_ID')
    if not channel_id:
        logger.error("LIFF_CHANNEL_ID 未設定，無法驗證 idToken")
        return None
    try:
        resp = requests.post(
            LIFF_VERIFY_URL,
            data={'id_token': id_token, 'client_id': channel_id},
            timeout=5,
        )
    except requests.RequestException as e:
        logger.warning(f"LIFF idToken 驗證請求失敗: {e}")
        return None
    if resp.status_code != 200:
        logger.info(f"LIFF idToken 驗證失敗 status={resp.status_code} body={resp.text[:200]}")
        return None
    return resp.json()


def liff_auth_required(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'ok': False, 'error': 'missing_bearer_token'}), 401
        id_token = auth_header[len('Bearer '):].strip()
        if not id_token:
            return jsonify({'ok': False, 'error': 'empty_id_token'}), 401
        claims = verify_line_id_token(id_token)
        if not claims:
            return jsonify({'ok': False, 'error': 'invalid_id_token'}), 401
        request.line_user_id = claims.get('sub')
        request.line_user_name = claims.get('name')
        return fn(*args, **kwargs)
    return wrapper

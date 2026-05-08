"""LIFF blueprint — 客戶 form / 之後其他 form 的入口

routes 註冊在子模組（health.py / customer.py …）裡，import 它們會觸發
@liff_bp.route 的裝飾器，把 url 掛到這個 blueprint 上。
"""
from flask import Blueprint

liff_bp = Blueprint('liff', __name__, url_prefix='/liff')

from rewrite.handlers.liff import health, customer, booking, import_form, fixed_schedule, report  # noqa: E402, F401

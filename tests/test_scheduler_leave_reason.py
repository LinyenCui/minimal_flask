#!/usr/bin/env python3
"""
測試：請假原因(passenger_leave_reason) 會從 trips 正確轉入 completed_trips。
場景：
- 在 trips 插入一筆狀態=準備、且 passenger_leave_reason 有值的班次
- 執行 update_completed_trips() 將逾期班次轉入 completed_trips
- 斷言 completed_trips.passenger_leave_reason 與 trips 一致
"""
import os
import pytest
from datetime import date, time, timedelta
from sqlalchemy import text

from modules.models.base import db
from modules.services.scheduler_service import update_completed_trips

@pytest.mark.usefixtures()
def test_leave_reason_migrates_to_completed_trips(app=None):
    # 準備：插入一筆過去時間的準備狀態班次，含請假原因
    trip_date = date.today() - timedelta(days=1)
    insert_trip_sql = text(
        """
        INSERT INTO trips
        (trip_id, date, time, start_point, via_point, end_point,
         meter_fare, extra_fare, category, driver_id, status,
         trip_type, passenger_name, passenger_leave_reason, modification_reason)
        VALUES
        (:trip_id, :date, :time, :start_point, :via_point, :end_point,
         :meter_fare, :extra_fare, :category, :driver_id, '準備',
         'fixed', :passenger_name, :passenger_leave_reason, :modification_reason)
        """
    )
    params = {
        "trip_id": 987654,
        "date": trip_date,
        "time": time(8, 0, 0),
        "start_point": "測試起點",
        "via_point": None,
        "end_point": "測試終點",
        "meter_fare": 0,
        "extra_fare": 0,
        "category": "診所",
        "driver_id": 5386,
        "passenger_name": "測試乘客",
        "passenger_leave_reason": "乘客出國請假",
        "modification_reason": None,
    }

    # 先刪除可能存在的殘留資料
    db.session.execute(text("DELETE FROM completed_trips WHERE original_trip_id = :tid OR unique_code LIKE :uc"), {"tid": params["trip_id"], "uc": f"T_{params['trip_id']}%"})
    db.session.execute(text("DELETE FROM trips WHERE trip_id = :tid"), {"tid": params["trip_id"]})
    db.session.commit()

    db.session.execute(insert_trip_sql, params)
    db.session.commit()

    # 執行轉移
    result_msg = update_completed_trips()
    assert "✅" in result_msg or "更新已完成班次任務結束" in result_msg

    # 查驗 completed_trips 是否寫入請假原因
    select_sql = text(
        """
        SELECT passenger_leave_reason, modification_reason
        FROM completed_trips
        WHERE (unique_code = :uc) OR (original_trip_id = :tid) OR (date = :d AND category = :c)
        ORDER BY id DESC
        LIMIT 1
        """
    )
    uc = f"T_{params['trip_id']}_{trip_date.strftime('%Y%m%d')}"
    row = db.session.execute(select_sql, {"uc": uc, "tid": params["trip_id"], "d": trip_date, "c": params["category"]}).fetchone()
    assert row is not None, "應該有已完成班次記錄"
    leave_reason, mod_reason = row
    assert leave_reason == params["passenger_leave_reason"], "請假原因應該被正確轉移到 completed_trips"
    # 修改原因允許為 None

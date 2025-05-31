# modules/models/trip.py
from modules.models.base import db
from datetime import datetime, timedelta

class Trip(db.Model):
    __tablename__ = 'trips'
    
    trip_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fixed_trip_id = db.Column(db.Integer, db.ForeignKey('fixed_schedules.id'), nullable=True)
    week_number = db.Column(db.Integer)
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'), nullable=True)
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    status = db.Column(db.String(20))
    unique_code = db.Column(db.String(50))
    
    # 關聯
    driver = db.relationship('Driver', backref='trips')
    
    def __repr__(self):
        return f"<Trip {self.trip_id} {self.date} {self.time}>"
    
    def can_modify_status(self):
        """檢查班次狀態是否可以修改（執行前30分鐘內不可修改）"""
        if not self.date or not self.time:
            return True  # 如果沒有日期時間，允許修改
        
        from datetime import datetime, timedelta
        import pytz
        
        # 設置台灣時區
        taiwan_tz = pytz.timezone('Asia/Taipei')
        
        # 獲取當前台灣時間
        current_time = datetime.now(taiwan_tz)
        
        # 組合班次的完整執行時間（台灣時區）
        trip_datetime = datetime.combine(self.date, self.time)
        trip_datetime = taiwan_tz.localize(trip_datetime)
        
        # 計算30分鐘前的時間點
        restriction_start_time = trip_datetime - timedelta(minutes=30)
        
        # 如果當前時間已經超過限制開始時間，則不能修改
        return current_time < restriction_start_time
    
    def minutes_until_restriction(self):
        """返回距離進入限制期還有多少分鐘（正數表示還可以修改的時間）"""
        if not self.date or not self.time:
            return float('inf')  # 沒有時間限制
        
        from datetime import datetime, timedelta
        import pytz
        
        # 設置台灣時區
        taiwan_tz = pytz.timezone('Asia/Taipei')
        
        # 獲取當前台灣時間
        current_time = datetime.now(taiwan_tz)
        
        # 組合班次的完整執行時間（台灣時區）
        trip_datetime = datetime.combine(self.date, self.time)
        trip_datetime = taiwan_tz.localize(trip_datetime)
        
        # 計算30分鐘前的時間點
        restriction_start_time = trip_datetime - timedelta(minutes=30)
        
        # 計算差值（分鐘）
        time_diff = restriction_start_time - current_time
        return max(0, int(time_diff.total_seconds() / 60))
    
    def get_restriction_message(self):
        """獲取限制提示訊息"""
        if self.can_modify_status():
            return None
        
        if not self.date or not self.time:
            return None
            
        from datetime import datetime, timedelta
        import pytz
        
        # 設置台灣時區
        taiwan_tz = pytz.timezone('Asia/Taipei')
        
        # 獲取當前台灣時間
        current_time = datetime.now(taiwan_tz)
        
        # 組合班次的完整執行時間（台灣時區）
        trip_datetime = datetime.combine(self.date, self.time)
        trip_datetime = taiwan_tz.localize(trip_datetime)
        
        # 檢查是班次前30分鐘限制還是班次已過期
        if current_time >= trip_datetime:
            return f"⚠️ 班次已過執行時間，無法修改狀態 (執行時間: {self.time.strftime('%H:%M')})"
        else:
            # 30分鐘限制期內
            restriction_start_time = trip_datetime - timedelta(minutes=30)
            remaining_time = trip_datetime - current_time
            remaining_minutes = int(remaining_time.total_seconds() / 60)
            
            return f"⏰ 執行前30分鐘內不可修改狀態 (還有 {remaining_minutes} 分鐘執行，{restriction_start_time.strftime('%H:%M')}後即不可修改)"

class FixedSchedule(db.Model):
    __tablename__ = 'fixed_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(10))
    departure_time = db.Column(db.Time, nullable=False)
    start_point = db.Column(db.String(100))
    via_point = db.Column(db.String(100), nullable=True)
    end_point = db.Column(db.String(100))
    base_fare = db.Column(db.Integer)
    surcharge = db.Column(db.Integer)
    total_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.String(10))
    direction = db.Column(db.String(50))
    
    def __repr__(self):
        return f"<FixedSchedule {self.id} {self.departure_time}>"

class CompletedTrip(db.Model):
    __tablename__ = 'completed_trips'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'), nullable=True)
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    unique_code = db.Column(db.String(50))
    
    # 關聯
    driver = db.relationship('Driver', backref='completed_trips')
    
    def __repr__(self):
        return f"<CompletedTrip {self.id} {self.date}>"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Driver, Schedule, CompletedSchedule
from datetime import datetime
import re

class FleetManager:
    def __init__(self):
        self.engine = create_engine('sqlite:///database.db')
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
    def _parse_time(self, time_str):
        """解析時間字符串，返回datetime對象"""
        hour = int(re.search(r'\d+', time_str).group())
        minute = 0
        if '分' in time_str:
            minute = int(re.search(r'(\d+)分', time_str).group(1))
        now = datetime.now()
        return datetime(now.year, now.month, now.day, hour, minute)
    
    def create_assignment(self, user_id, times, locations):
        """創建新的派車任務"""
        try:
            if not times or len(times) < 1:
                return {'status': 'error', 'message': '請指定派車時間'}
            if not locations or len(locations) < 2:
                return {'status': 'error', 'message': '請指定起點和終點'}
            
            # 解析時間
            start_time = self._parse_time(times[0][0])
            
            # 查找可用車輛
            available_vehicle = self.session.query(Vehicle)\
                .filter_by(is_available=True)\
                .first()
            
            if not available_vehicle:
                return {'status': 'error', 'message': '當前沒有可用車輛'}
            
            # 查找可用司機
            available_driver = self.session.query(Driver)\
                .filter_by(is_available=True)\
                .first()
            
            if not available_driver:
                return {'status': 'error', 'message': '當前沒有可用司機'}
            
            # 創建派車任務
            assignment = Assignment(
                driver_id=available_driver.id,
                vehicle_id=available_vehicle.id,
                start_time=start_time,
                pickup_location=locations[0],
                dropoff_location=locations[1],
                status='pending'
            )
            
            # 更新車輛和司機狀態
            available_vehicle.is_available = False
            available_driver.is_available = False
            
            self.session.add(assignment)
            self.session.commit()
            
            return {
                'status': 'success',
                'message': f'派車成功！\n訂單編號：{assignment.id}\n司機：{available_driver.name}\n車牌號：{available_vehicle.plate_number}\n接送時間：{start_time.strftime("%H:%M")}\n起點：{locations[0]}\n終點：{locations[1]}'
            }
            
        except Exception as e:
            self.session.rollback()
            return {'status': 'error', 'message': f'派車失敗：{str(e)}'}
    
    def query_assignments(self, user_id):
        """查詢派車任務"""
        try:
            assignments = self.session.query(Assignment)\
                .filter(Assignment.status != 'cancelled')\
                .order_by(Assignment.start_time.desc())\
                .limit(5)\
                .all()
            
            if not assignments:
                return {'status': 'success', 'message': '沒有找到相關派車記錄'}
            
            response = "最近的派車記錄：\n"
            for assignment in assignments:
                driver = self.session.query(Driver).get(assignment.driver_id)
                vehicle = self.session.query(Vehicle).get(assignment.vehicle_id)
                response += f"\n訂單編號：{assignment.id}\n"
                response += f"狀態：{assignment.status}\n"
                response += f"司機：{driver.name}\n"
                response += f"車牌號：{vehicle.plate_number}\n"
                response += f"接送時間：{assignment.start_time.strftime('%H:%M')}\n"
                response += f"起點：{assignment.pickup_location}\n"
                response += f"終點：{assignment.dropoff_location}\n"
                response += "-------------------"
            
            return {'status': 'success', 'message': response}
            
        except Exception as e:
            return {'status': 'error', 'message': f'查詢失敗：{str(e)}'}
    
    def cancel_assignment(self, user_id, order_id):
        """取消派車任務"""
        try:
            assignment = self.session.query(Assignment).get(order_id)
            
            if not assignment:
                return {'status': 'error', 'message': f'未找到訂單編號：{order_id}'}
            
            if assignment.status == 'cancelled':
                return {'status': 'error', 'message': '該訂單已經取消'}
            
            if assignment.status == 'completed':
                return {'status': 'error', 'message': '該訂單已經完成，無法取消'}
            
            # 更新訂單狀態
            assignment.status = 'cancelled'
            
            # 釋放車輛和司機資源
            vehicle = self.session.query(Vehicle).get(assignment.vehicle_id)
            driver = self.session.query(Driver).get(assignment.driver_id)
            
            vehicle.is_available = True
            driver.is_available = True
            
            self.session.commit()
            
            return {'status': 'success', 'message': f'訂單 {order_id} 已成功取消'}
            
        except Exception as e:
            self.session.rollback()
            return {'status': 'error', 'message': f'取消失敗：{str(e)}'}
    
    def get_status(self, user_id):
        """獲取系統狀態"""
        try:
            available_vehicles = self.session.query(Vehicle)\
                .filter_by(is_available=True)\
                .count()
            
            available_drivers = self.session.query(Driver)\
                .filter_by(is_available=True)\
                .count()
            
            pending_assignments = self.session.query(Assignment)\
                .filter_by(status='pending')\
                .count()
            
            in_progress_assignments = self.session.query(Assignment)\
                .filter_by(status='in_progress')\
                .count()
            
            response = "系統狀態：\n"
            response += f"可用車輛數：{available_vehicles}\n"
            response += f"可用司機數：{available_drivers}\n"
            response += f"待處理訂單數：{pending_assignments}\n"
            response += f"進行中訂單數：{in_progress_assignments}"
            
            return {'status': 'success', 'message': response}
            
        except Exception as e:
            return {'status': 'error', 'message': f'獲取狀態失敗：{str(e)}'} 
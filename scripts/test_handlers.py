from app import app, db
from handlers.trip_handler import handle_pending_trips
from handlers.driver_handler import handle_assign_driver

# 將 app 的 db 實例傳遞給 handlers 模塊
import handlers.trip_handler
import handlers.driver_handler
handlers.trip_handler.db = db
handlers.driver_handler.db = db

with app.app_context():
    print("測試待派班次功能:")
    print(handle_pending_trips())
    
    print("\n測試指派司機功能:")
    print(handle_assign_driver("指派 629 5386"))  # 使用實際存在的班次ID和司機ID 
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, abort
from linebot.v3.messaging import Configuration, MessagingApi, ApiClient
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import calendar

# 讀取環境變數
load_dotenv()
app = Flask(__name__)

# LINE 設置
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError("Missing LINE_CHANNEL_TOKEN or LINE_CHANNEL_SECRET in .env")

# 初始化 MessagingApi 和 WebhookHandler
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(CHANNEL_SECRET)

# 初始化資料庫
def init_db():
    conn = sqlite3.connect('database.db')  # 本地用 ./database.db，Render 改成 /data/database.db
    c = conn.cursor()
    
    # 客戶表
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                 client_id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 address TEXT,
                 short_name TEXT UNIQUE,
                 category TEXT,
                 remarks TEXT)''')
    
    # 司機表
    c.execute('''CREATE TABLE IF NOT EXISTS drivers (
                 driver_id TEXT PRIMARY KEY,
                 name TEXT,
                 license_plate TEXT,
                 car_brand TEXT,
                 car_model TEXT)''')
    
    # 固定班次表
    c.execute('''CREATE TABLE IF NOT EXISTS fixed_trips (
                 fixed_trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                 cycle TEXT,
                 time TEXT,
                 start_point TEXT,
                 via_point TEXT,
                 end_point TEXT,
                 meter_fare INTEGER,
                 extra_fare INTEGER,
                 actual_fare INTEGER,
                 category TEXT,
                 driver_id TEXT,
                 FOREIGN KEY (start_point) REFERENCES clients(short_name),
                 FOREIGN KEY (via_point) REFERENCES clients(short_name),
                 FOREIGN KEY (end_point) REFERENCES clients(short_name),
                 FOREIGN KEY (category) REFERENCES clients(category),
                 FOREIGN KEY (driver_id) REFERENCES drivers(driver_id))''')
    
    # 總覽表
    c.execute('''CREATE TABLE IF NOT EXISTS trips (
                 trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                 fixed_trip_id INTEGER,
                 week_number INTEGER,
                 date TEXT,
                 time TEXT,
                 start_point TEXT,
                 via_point TEXT,
                 end_point TEXT,
                 meter_fare INTEGER,
                 extra_fare INTEGER,
                 actual_fare INTEGER,
                 category TEXT,
                 driver_id TEXT,
                 status TEXT,
                 FOREIGN KEY (start_point) REFERENCES clients(short_name),
                 FOREIGN KEY (via_point) REFERENCES clients(short_name),
                 FOREIGN KEY (end_point) REFERENCES clients(short_name),
                 FOREIGN KEY (category) REFERENCES clients(category),
                 FOREIGN KEY (driver_id) REFERENCES drivers(driver_id))''')
    
    # 預設資料（客戶）
    c.executemany("INSERT OR IGNORE INTO clients (name, address, short_name, category, remarks) VALUES (?, ?, ?, ?, ?)", [
        ("洗腎診所", "台南市永康區大灣二街", "大灣診所", "診所", "固定接送"),
        ("東洋公司", "台南市北區中華北路一段", "東洋公司", "東洋", "公務出行"),
    ])
    
    # 預設資料（司機，移除補 0，加入第一筆資料）
    c.executemany("INSERT OR IGNORE INTO drivers (driver_id, name, license_plate, car_brand, car_model) VALUES (?, ?, ?, ?, ?)", [
        ("5386", "崔林彥", "TDE-5386", "Toyota", "RAV4"),  # 第一筆資料
        ("1", "張先生", "ABC-1234", "Toyota", "Corolla"),  # 原有數據，編號改為不補 0
        ("2", "李先生", "XYZ-5678", "Honda", "Civic"),    # 原有數據，編號改為不補 0
    ])
    
    # 預設資料（固定班次，更新 driver_id 為不補 0 的值）
    c.executemany("INSERT OR IGNORE INTO fixed_trips (cycle, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        ("一三五", "08:30", "大灣診所", "", "大灣診所", 275, 0, 275, "診所", "5386"),  # 更新 driver_id
        ("二四六", "09:00", "東洋公司", "", "東洋公司", 200, 0, 200, "東洋", "1"),    # 更新 driver_id
    ])
    
    conn.commit()
    conn.close()

# 計算一年中的第幾週
def get_week_number(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    return date.isocalendar()[1]

# 檢查固定班次是否需要匯入
def import_fixed_trips(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    weekday = calendar.day_name[date.weekday()].lower()  # 星期一 -> monday
    weekday_map = {"monday": "一", "tuesday": "二", "wednesday": "三", "thursday": "四", "friday": "五", "saturday": "六"}
    weekday_ch = weekday_map.get(weekday, "")
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # 查固定班次
    c.execute("SELECT * FROM fixed_trips")
    fixed_trips = c.fetchall()
    for ft in fixed_trips:
        fixed_trip_id, cycle, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id = ft
        if weekday_ch in cycle:  # 檢查該週期是否包含今天
            # 檢查是否已有相同班次
            c.execute("SELECT trip_id FROM trips WHERE fixed_trip_id = ? AND date = ? AND status NOT IN ('取消', '請假')", 
                      (fixed_trip_id, date_str))
            if not c.fetchone():
                # 匯入班次，預設狀態為「準備」
                week_number = get_week_number(date_str)
                c.execute("INSERT INTO trips (fixed_trip_id, week_number, date, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (fixed_trip_id, week_number, date_str, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id, "準備"))
    
    conn.commit()
    conn.close()

# 自動更新狀態
def update_trip_status():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    now = datetime.now()
    
    # 將「準備」和「待派」過期的班次設為「完成」
    c.execute("SELECT trip_id, date, time FROM trips WHERE status IN ('準備', '待派')")
    trips = c.fetchall()
    for trip in trips:
        trip_id, date, time = trip
        trip_datetime = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
        if now > trip_datetime:
            c.execute("UPDATE trips SET status = '完成' WHERE trip_id = ? AND status IN ('準備', '待派')", (trip_id,))
    
    conn.commit()
    conn.close()

@app.route("/")
def hello():
    return "Hello from minimal_flask with LINE Bot!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print(f"Received Webhook request: signature={signature}, body={body}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        print(f"Signature verification failed: {e}")
        abort(400)
    except Exception as e:
        print(f"Unexpected error during handling: {e}")
        abort(500)
    return "OK"

# 註冊事件處理器
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text.lower()
    print(f"Handling message: {text}")
    try:
        update_trip_status()  # 每次訊息檢查狀態
    except Exception as e:
        print(f"Error in update_trip_status: {e}")
        raise
    
    if text.startswith("新增固定 "):
        try:
            _, cycle, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id = text.split(" ", 10)
            meter_fare, extra_fare, actual_fare = int(meter_fare), int(extra_fare), int(actual_fare)
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            # 檢查起點、經由、到達、分類、司機是否存在
            for point in [start_point, via_point, end_point]:
                if point:
                    c.execute("SELECT short_name FROM clients WHERE short_name = ?", (point,))
                    if not c.fetchone():
                        conn.close()
                        reply_message(event, f"找不到地點 {point}")
                        return
            
            c.execute("SELECT category FROM clients WHERE category = ?", (category,))
            if not c.fetchone():
                conn.close()
                reply_message(event, f"找不到分類 {category}")
                return
            
            c.execute("SELECT driver_id FROM drivers WHERE driver_id = ?", (driver_id,))
            if not c.fetchone():
                conn.close()
                reply_message(event, f"找不到司機 {driver_id}")
                return
            
            # 插入固定班次
            c.execute("INSERT INTO fixed_trips (cycle, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (cycle, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id))
            conn.commit()
            conn.close()
            reply_message(event, f"新增固定班次成功！{cycle} {time} {start_point} -> {end_point}")
        except:
            reply_message(event, "格式錯誤，請用：新增固定 週期 時間 起點 經由 到達 錶價 加成 實收 分類 司機")

    elif text.startswith("匯入固定 "):
        try:
            _, date = text.split(" ", 1)
            import_fixed_trips(date)
            reply_message(event, f"已匯入 {date} 的固定班次")
        except:
            reply_message(event, "格式錯誤，請用：匯入固定 YYYY-MM-DD")

    elif text.startswith("新增 "):
        try:
            _, date, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category = text.split(" ", 9)
            meter_fare, extra_fare, actual_fare = int(meter_fare), int(extra_fare), int(actual_fare)
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            # 檢查地點和分類
            for point in [start_point, via_point, end_point]:
                if point:
                    c.execute("SELECT short_name FROM clients WHERE short_name = ?", (point,))
                    if not c.fetchone():
                        conn.close()
                        reply_message(event, f"找不到地點 {point}")
                        return
            
            c.execute("SELECT category FROM clients WHERE category = ?", (category,))
            if not c.fetchone():
                conn.close()
                reply_message(event, f"找不到分類 {category}")
                return
            
            # 插入臨時班次，預設狀態為「待派」
            week_number = get_week_number(date)
            c.execute("INSERT INTO trips (week_number, date, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (week_number, date, time, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, "待派"))
            conn.commit()
            conn.close()
            reply_message(event, f"新增臨時班次成功！{date} {time} {start_point} -> {end_point}")
        except:
            reply_message(event, "格式錯誤，請用：新增 日期 時間 起點 經由 到達 錶價 加成 實收 分類")

    elif text.startswith("指派 "):
        try:
            _, trip_id, driver_id = text.split(" ", 2)
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            # 檢查班次和司機
            c.execute("SELECT status FROM trips WHERE trip_id = ?", (trip_id,))
            trip = c.fetchone()
            if not trip:
                conn.close()
                reply_message(event, f"找不到班次 {trip_id}")
                return
            if trip[0] != "待派":
                conn.close()
                reply_message(event, f"班次 {trip_id} 狀態不是待派，無法指派")
                return
            
            c.execute("SELECT driver_id FROM drivers WHERE driver_id = ?", (driver_id,))
            if not c.fetchone():
                conn.close()
                reply_message(event, f"找不到司機 {driver_id}")
                return
            
            # 指派司機，狀態變為「準備」
            c.execute("UPDATE trips SET driver_id = ?, status = '準備' WHERE trip_id = ?", (driver_id, trip_id))
            conn.commit()
            conn.close()
            reply_message(event, f"已指派司機 {driver_id} 給班次 {trip_id}")
        except:
            reply_message(event, "格式錯誤，請用：指派 班次ID 司機ID")

    elif text.startswith("更改狀態 "):
        try:
            _, trip_id, new_status = text.split(" ", 2)
            if new_status not in ["準備", "待派", "取消", "請假", "衝突", "完成"]:
                reply_message(event, "狀態必須是：準備、待派、取消、請假、衝突、完成")
                return
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            # 檢查班次
            c.execute("SELECT fixed_trip_id FROM trips WHERE trip_id = ?", (trip_id,))
            trip = c.fetchone()
            if not trip:
                conn.close()
                reply_message(event, f"找不到班次 {trip_id}")
                return
            fixed_trip_id = trip[0]
            
            # 如果設為「請假」，更新後續週期的班次
            if new_status == "請假" and fixed_trip_id:
                c.execute("UPDATE trips SET status = '請假' WHERE fixed_trip_id = ? AND trip_id >= ? AND status NOT IN ('取消', '衝突', '完成')", 
                          (fixed_trip_id, trip_id))
            
            # 更新狀態
            c.execute("UPDATE trips SET status = ? WHERE trip_id = ?", (new_status, trip_id))
            conn.commit()
            conn.close()
            reply_message(event, f"已將班次 {trip_id} 狀態設為 {new_status}")
        except:
            reply_message(event, "格式錯誤，請用：更改狀態 班次ID 新狀態")

    elif text.startswith("查車 "):
        try:
            _, driver_id, date = text.split(" ", 2)
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT t.trip_id, t.date, t.time, t.start_point, t.via_point, t.end_point, t.meter_fare, t.actual_fare, t.status FROM trips t WHERE t.driver_id = ? AND t.date = ?", (driver_id, date))
            trips = c.fetchall()
            conn.close()
            if trips:
                reply = f"{driver_id} {date} 班次：\n" + "\n".join([f"ID:{t[0]} {t[1]} {t[2]} {t[3]} -> {t[4]} -> {t[5]} 錶價:{t[6]} 實收:{t[7]} 狀態:{t[8]}" for t in trips])
            else:
                reply = "當天無紀錄"
            reply_message(event, reply)
        except:
            reply_message(event, "格式錯誤，請用：查車 司機ID 日期")

    else:
        reply = "指令：新增固定 週期 時間 起點 經由 到達 錶價 加成 實收 分類 司機 / 新增 日期 時間 起點 經由 到達 錶價 加成 實收 分類 / 匯入固定 日期 / 指派 班次ID 司機ID / 更改狀態 班次ID 新狀態 / 查車 司機ID 日期"
        reply_message(event, reply)

def reply_message(event, reply_text):
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=3000)

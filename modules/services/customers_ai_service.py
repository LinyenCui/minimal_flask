import logging
import json
from datetime import datetime
from flask import current_app
from modules.models.base import db
from modules.services.ai_service import init_vertexai, PROJECT_ID, LOCATION, MODEL_ID
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    Tool,
    FunctionDeclaration,
    Content,
    Part
)
from sqlalchemy import text
from modules.services.booking.booking_service import create_booking_record

logger = logging.getLogger(__name__)

# --- 1. Model Definition (Sandbox) ---
class CustomerSandbox(db.Model):
    __tablename__ = 'customers'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(50), unique=True)
    address = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    contact_phone = db.Column(db.String(50))  # New field as per requirements

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "address": self.address,
            "category": self.category,
            "remarks": self.remarks,
            "contact_phone": self.contact_phone
        }

# --- 2. Tool Implementations ---

def _tool_customer_lookup(query_kwargs):
    """Executes the lookup. Supported keys: name, short_name, address, contact_phone (partial match)."""
    try:
        q = CustomerSandbox.query
        filters = []
        
        # Enhanced Lookup Logic:
        # If 'name' is provided, check BOTH name and short_name (OR condition)
        if 'name' in query_kwargs and query_kwargs['name']:
            val = query_kwargs['name']
            filters.append(db.or_(
                CustomerSandbox.name.ilike(f"%{val}%"),
                CustomerSandbox.short_name.ilike(f"%{val}%")
            ))
            
        if 'short_name' in query_kwargs and query_kwargs['short_name']:
            filters.append(CustomerSandbox.short_name.ilike(f"%{query_kwargs['short_name']}%"))

        if 'address' in query_kwargs and query_kwargs['address']:
            filters.append(CustomerSandbox.address.ilike(f"%{query_kwargs['address']}%"))
        
        if not filters:
            results = q.limit(5).all()
        else:
            for f in filters:
                q = q.filter(f)
            results = q.limit(10).all()

        return json.dumps([r.to_dict() for r in results], ensure_ascii=False)
    except Exception as e:
        logger.error(f"Lookup error: {e}")
        return json.dumps({"error": str(e)})

def _tool_customer_create(kwargs):
    """Creates a customer. Returns dummy success message for proposal, or executes if verify=False (not used here direclty)."""
    # This function is used to PREVIEW what would happen, or actually do it?
    # For the "Proposal" phase, we just return the intention? 
    # NO, the system design says: Gemini produces Function Call -> Logic intercepts -> if unsafe, ask user.
    # So this function is the ACTUAL execution function.
    try:
        new_customer = CustomerSandbox(**kwargs)
        db.session.add(new_customer)
        db.session.commit()
        return json.dumps({"status": "success", "message": f"Created customer {kwargs.get('name')}", "data": new_customer.to_dict()}, ensure_ascii=False)
    except Exception as e:
        db.session.rollback()
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

def _tool_customer_update(kwargs):
    """Updates a customer.
    
    kwargs 來自 execute_proposal 的轉換：
    - '_identify_short_name', '_identify_name' 用於識別目標客戶（必須使用這些，不能 fallback）
    - 其他欄位（已去除 new_ 前綴）是要更新的值
    """
    try:
        logger.info(f"🔧 _tool_customer_update 收到參數: {kwargs}")
        
        # 獲取識別用的參數（只用 _identify_* 前綴的，不要 fallback 到可能被覆蓋的值）
        identify_short_name = kwargs.pop('_identify_short_name', None)
        identify_name = kwargs.pop('_identify_name', None)
        
        logger.info(f"🔧 識別參數: short_name={identify_short_name}, name={identify_name}")
        
        # 如果沒有識別參數，嘗試用 name 查找（但 short_name 可能已被新值覆蓋，不能用）
        if not identify_short_name and not identify_name:
            # 最後手段：用 name 欄位（如果它不是要更新的值）
            identify_name = kwargs.get('name')
        
        # Identify target
        target = None
        if identify_short_name:
            target = CustomerSandbox.query.filter_by(short_name=identify_short_name).first()
        if not target and identify_name:
            # 嘗試用 name 或 short_name 查找
            target = CustomerSandbox.query.filter_by(name=identify_name).first()
            if not target:
                target = CustomerSandbox.query.filter_by(short_name=identify_name).first()
            if not target:
                # 模糊搜索
                target = CustomerSandbox.query.filter(
                    db.or_(
                        CustomerSandbox.name.ilike(f"%{identify_name}%"),
                        CustomerSandbox.short_name.ilike(f"%{identify_name}%")
                    )
                ).first()
        
        if not target:
            search_term = identify_short_name or identify_name or "未知"
            return json.dumps({"status": "error", "message": f"找不到客戶：{search_term}"}, ensure_ascii=False)
        
        # 更新欄位
        changes = []
        updatable_fields = ['name', 'short_name', 'address', 'contact_phone', 'category', 'remarks']
        
        for field in updatable_fields:
            if field not in kwargs:
                continue
            
            new_value = kwargs[field]
            
            # 跳過識別用的值（不是要更新的）
            if field == 'short_name' and new_value == identify_short_name:
                continue
            if field == 'name' and new_value == identify_name:
                continue
            
            if hasattr(target, field):
                old_val = getattr(target, field)
                if old_val != new_value:
                    # 檢查 short_name 唯一性
                    if field == 'short_name':
                        existing = CustomerSandbox.query.filter_by(short_name=new_value).first()
                        if existing and existing.id != target.id:
                            return json.dumps({"status": "error", "message": f"簡稱「{new_value}」已被使用"}, ensure_ascii=False)
                    
                    setattr(target, field, new_value)
                    changes.append(f"{field}: {old_val} -> {new_value}")
        
        if not changes:
            return json.dumps({"status": "success", "message": f"「{target.name}」沒有需要更新的內容"}, ensure_ascii=False)
        
        db.session.commit()
        return json.dumps({"status": "success", "message": f"已更新「{target.name}」", "changes": changes}, ensure_ascii=False)
    except Exception as e:
        db.session.rollback()
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

def _tool_customer_delete(kwargs):
    """Deletes a customer."""
    try:
        target = None
        if 'short_name' in kwargs:
            target = CustomerSandbox.query.filter_by(short_name=kwargs['short_name']).first()
        elif 'name' in kwargs:
            target = CustomerSandbox.query.filter_by(name=kwargs['name']).first()
            
        if not target:
            return json.dumps({"status": "error", "message": "Customer not found"}, ensure_ascii=False)
            
        name = target.name
        db.session.delete(target)
        db.session.commit()
        return json.dumps({"status": "success", "message": f"Deleted customer {name}"}, ensure_ascii=False)
    except Exception as e:
        db.session.rollback()
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

# --- Booking Tools ---

from modules.utils.unified_date_parser import parse_date_input
from datetime import datetime, date

def _tool_booking_create(kwargs):
    """Creates a booking record."""
    try:
        # 1. Parse Date
        date_str = kwargs.get('date')
        try:
            date_obj = parse_date_input(date_str)
        except Exception:
             # Fallback or error? AI usually gives ISO or readable format.
             # If parse fails, return error to AI prompt
             return json.dumps({"status": "error", "message": f"無法識別日期：{date_str}"}, ensure_ascii=False)
             
        # 2. Parse Time
        time_str = kwargs.get('time')
        try:
            if ":" in time_str:
                hour, minute = time_str.split(":")
                time_obj = datetime.strptime(f"{hour.zfill(2)}:{minute.zfill(2)}", "%H:%M").time()
            else:
                 return json.dumps({"status": "error", "message": f"無法識別時間：{time_str}"}, ensure_ascii=False)
        except Exception:
             return json.dumps({"status": "error", "message": f"無法識別時間：{time_str}"}, ensure_ascii=False)

        # 3. Prepare Data
        booking_data = {
            'date': date_obj,
            'time': time_obj,
            'start_point': kwargs.get('start_point'),
            'end_point': kwargs.get('end_point'),
            'via_point': kwargs.get('via_point'),
            'category': kwargs.get('category', '東洋'),
            'passenger_name': kwargs.get('passenger_name'),
            'meter_fare': kwargs.get('meter_fare'),
            'driver_id': kwargs.get('driver_id')
        }
        
        # 4. Execute
        success, result = create_booking_record(booking_data)
        
        if success:
            msg = f"已預約 {date_str} {time_str} (ID: {result['trip_id']})"
                
            return json.dumps({
                "status": "success", 
                "message": msg, 
                "data": result
            }, ensure_ascii=False)
        else:
            return json.dumps({"status": "error", "message": str(result)}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

def _tool_trip_update(kwargs):
    """Updates a trip record."""
    try:
        trip_id = kwargs.get('trip_id')
        if not trip_id:
             return json.dumps({"status": "error", "message": "Missing trip_id"}, ensure_ascii=False)
             
        updates = {}
        if kwargs.get('date'):
            try:
                updates['date'] = parse_date_input(kwargs.get('date'))
            except:
                pass
        if kwargs.get('time'):
            # Parse time logic duplicate... ideally refactor
            time_str = kwargs.get('time')
            try:
                if ":" in time_str:
                    updates['time'] = datetime.strptime(f"{time_str.zfill(5)}", "%H:%M").time()
                elif len(time_str) == 4:
                    updates['time'] = datetime.strptime(f"{time_str[:2]}:{time_str[2:]}", "%H:%M").time()
            except:
                pass
                
        if kwargs.get('start_point'): updates['start_point'] = kwargs.get('start_point')
        if kwargs.get('end_point'): updates['end_point'] = kwargs.get('end_point')
        if kwargs.get('via_point'): updates['via_point'] = kwargs.get('via_point')
        if kwargs.get('category'): updates['category'] = kwargs.get('category')
        if kwargs.get('passenger_name'): updates['passenger_name'] = kwargs.get('passenger_name')
        if kwargs.get('meter_fare'): updates['meter_fare'] = kwargs.get('meter_fare')
        if kwargs.get('driver_id'): updates['driver_id'] = kwargs.get('driver_id')
        
        if not updates:
            return json.dumps({"status": "success", "message": "No changes detected"}, ensure_ascii=False)
            
        # Build SQL
        set_clauses = [f"{k} = :{k}" for k in updates.keys()]
        query = text(f"UPDATE trips SET {', '.join(set_clauses)} WHERE trip_id = :trip_id")
        
        updates['trip_id'] = trip_id
        db.session.execute(query, updates)
        db.session.commit()
        
        return json.dumps({"status": "success", "message": f"Updated trip {trip_id}", "changes": kwargs}, ensure_ascii=False)
    except Exception as e:
        db.session.rollback()
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

def _tool_trip_delete(kwargs):
    """Deletes a trip record."""
    try:
        trip_id = kwargs.get('trip_id')
        if not trip_id:
             return json.dumps({"status": "error", "message": "Missing trip_id"}, ensure_ascii=False)
             
        query = text("DELETE FROM trips WHERE trip_id = :trip_id")
        result = db.session.execute(query, {'trip_id': trip_id})
        db.session.commit()
        
        if result.rowcount > 0:
            return json.dumps({"status": "success", "message": f"Deleted trip {trip_id}"}, ensure_ascii=False)
        else:
            return json.dumps({"status": "error", "message": f"Trip {trip_id} not found"}, ensure_ascii=False)
    except Exception as e:
        db.session.rollback()
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


# --- Fixed Schedule Tools ---

def _tool_fixed_schedule_lookup(kwargs):
    """查詢固定班次。支援用客戶名稱、班次ID查詢。"""
    try:
        schedule_id = kwargs.get('schedule_id')
        customer_name = kwargs.get('customer_name')
        
        if schedule_id:
            # 用 ID 查詢單一班次
            query = text("""
                SELECT id, route_number, departure_time, start_point, via_point, end_point,
                       base_fare, surcharge, total_fare, category, driver_id, direction, status, note
                FROM fixed_schedules WHERE id = :schedule_id
            """)
            results = db.session.execute(query, {"schedule_id": schedule_id}).fetchall()
        elif customer_name:
            # 用客戶名稱查詢相關班次
            query = text("""
                SELECT id, route_number, departure_time, start_point, via_point, end_point,
                       base_fare, surcharge, total_fare, category, driver_id, direction, status, note
                FROM fixed_schedules 
                WHERE start_point ILIKE :name OR via_point ILIKE :name OR end_point ILIKE :name
                ORDER BY departure_time
                LIMIT 10
            """)
            results = db.session.execute(query, {"name": f"%{customer_name}%"}).fetchall()
        else:
            # 無條件，返回前 5 筆
            query = text("""
                SELECT id, route_number, departure_time, start_point, via_point, end_point,
                       base_fare, surcharge, total_fare, category, driver_id, direction, status, note
                FROM fixed_schedules ORDER BY departure_time LIMIT 5
            """)
            results = db.session.execute(query).fetchall()
        
        schedules = []
        for r in results:
            schedules.append({
                "id": r[0],
                "route_number": r[1],
                "departure_time": r[2].strftime("%H:%M") if r[2] else None,
                "start_point": r[3],
                "via_point": r[4],
                "end_point": r[5],
                "base_fare": r[6],
                "surcharge": r[7],
                "total_fare": r[8],
                "category": r[9],
                "driver_id": r[10],
                "direction": r[11],
                "status": r[12] or "準備",
                "note": r[13]
            })
        
        return json.dumps(schedules, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Fixed schedule lookup error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _tool_fixed_schedule_leave(kwargs):
    """設置固定班次請假。需要 schedule_id, reason, surcharge。"""
    try:
        schedule_id = kwargs.get('schedule_id')
        reason = kwargs.get('reason')
        surcharge = kwargs.get('surcharge')
        
        if not schedule_id:
            return json.dumps({"status": "error", "message": "缺少固定班次 ID"}, ensure_ascii=False)
        
        # 查詢班次是否存在
        check_query = text("""
            SELECT id, status, note, surcharge, start_point, end_point, departure_time
            FROM fixed_schedules WHERE id = :schedule_id
        """)
        schedule = db.session.execute(check_query, {"schedule_id": schedule_id}).fetchone()
        
        if not schedule:
            return json.dumps({"status": "error", "message": f"找不到固定班次 #{schedule_id}"}, ensure_ascii=False)
        
        current_status = schedule[1] or '準備'
        if current_status == '請假':
            return json.dumps({
                "status": "error", 
                "message": f"固定班次 #{schedule_id} 已經是請假狀態，原因：{schedule[2] or '無'}"
            }, ensure_ascii=False)
        
        # 更新為請假狀態
        update_query = text("""
            UPDATE fixed_schedules
            SET status = '請假',
                note = :reason,
                surcharge = :surcharge,
                modification_time = :mod_time
            WHERE id = :schedule_id
        """)
        
        db.session.execute(update_query, {
            "schedule_id": schedule_id,
            "reason": reason,
            "surcharge": surcharge,
            "mod_time": datetime.now()
        })
        db.session.commit()
        
        original_surcharge = schedule[3] or 0
        return json.dumps({
            "status": "success",
            "message": f"固定班次 #{schedule_id} 已設為請假\n路線：{schedule[4]} → {schedule[5]}\n時間：{schedule[6]}\n原因：{reason}\n加成：{original_surcharge} → {surcharge}"
        }, ensure_ascii=False)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fixed schedule leave error: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


def _tool_fixed_schedule_update(kwargs):
    """修改固定班次（時間、地點、車資等）。"""
    try:
        schedule_id = kwargs.get('schedule_id')
        
        if not schedule_id:
            return json.dumps({"status": "error", "message": "缺少固定班次 ID"}, ensure_ascii=False)
        
        # 查詢班次是否存在
        check_query = text("""
            SELECT id, departure_time, start_point, via_point, end_point, 
                   base_fare, surcharge, driver_id, category, note
            FROM fixed_schedules WHERE id = :schedule_id
        """)
        schedule = db.session.execute(check_query, {"schedule_id": schedule_id}).fetchone()
        
        if not schedule:
            return json.dumps({"status": "error", "message": f"找不到固定班次 #{schedule_id}"}, ensure_ascii=False)
        
        # 可更新的欄位
        updatable_fields = {
            'departure_time': ('時間', schedule[1]),
            'start_point': ('起點', schedule[2]),
            'via_point': ('途經', schedule[3]),
            'end_point': ('終點', schedule[4]),
            'base_fare': ('基本車資', schedule[5]),
            'surcharge': ('加成', schedule[6]),
            'driver_id': ('司機', schedule[7]),
            'category': ('類別', schedule[8]),
            'note': ('備註', schedule[9])
        }
        
        changes = []
        update_parts = []
        update_params = {"schedule_id": schedule_id, "mod_time": datetime.now()}
        
        for field, (label, old_val) in updatable_fields.items():
            new_val = kwargs.get(field)
            if new_val is not None:
                # 時間需要特別處理
                if field == 'departure_time':
                    # 解析時間字串（支援 "10:15", "10:30", "下午3點" 等格式）
                    import re
                    time_val = new_val
                    if isinstance(new_val, str):
                        # 嘗試解析 HH:MM 格式
                        time_match = re.match(r'^(\d{1,2}):(\d{2})$', new_val)
                        if time_match:
                            hour, minute = int(time_match.group(1)), int(time_match.group(2))
                            from datetime import time as dt_time
                            time_val = dt_time(hour, minute)
                        else:
                            # 嘗試解析中文格式（下午3點、上午10點半等）
                            cn_match = re.match(r'(上午|下午)?(\d{1,2})[:點](\d{0,2})?', new_val)
                            if cn_match:
                                period, hour, minute = cn_match.groups()
                                hour = int(hour)
                                minute = int(minute) if minute else 0
                                if period == '下午' and hour < 12:
                                    hour += 12
                                from datetime import time as dt_time
                                time_val = dt_time(hour, minute)
                    
                    old_display = old_val.strftime('%H:%M') if old_val else '無'
                    new_display = time_val.strftime('%H:%M') if hasattr(time_val, 'strftime') else str(time_val)
                    new_val = time_val
                else:
                    old_display = old_val if old_val is not None else '無'
                    new_display = new_val
                
                update_parts.append(f"{field} = :{field}")
                update_params[field] = new_val
                changes.append(f"{label}：{old_display} → {new_display}")
        
        if not changes:
            return json.dumps({"status": "error", "message": "沒有指定要修改的內容"}, ensure_ascii=False)
        
        # 執行更新
        update_query = text(f"""
            UPDATE fixed_schedules
            SET {', '.join(update_parts)}, modification_time = :mod_time
            WHERE id = :schedule_id
        """)
        
        db.session.execute(update_query, update_params)
        db.session.commit()
        
        return json.dumps({
            "status": "success",
            "message": f"固定班次 #{schedule_id} 已更新\n" + '\n'.join(changes)
        }, ensure_ascii=False)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fixed schedule update error: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


def _tool_fixed_schedule_restore(kwargs):
    """恢復固定班次（從請假狀態恢復為準備）。"""
    try:
        schedule_id = kwargs.get('schedule_id')
        
        if not schedule_id:
            return json.dumps({"status": "error", "message": "缺少固定班次 ID"}, ensure_ascii=False)
        
        # 查詢班次是否存在
        check_query = text("""
            SELECT id, status, note, start_point, end_point, departure_time
            FROM fixed_schedules WHERE id = :schedule_id
        """)
        schedule = db.session.execute(check_query, {"schedule_id": schedule_id}).fetchone()
        
        if not schedule:
            return json.dumps({"status": "error", "message": f"找不到固定班次 #{schedule_id}"}, ensure_ascii=False)
        
        current_status = schedule[1] or '準備'
        if current_status != '請假':
            return json.dumps({
                "status": "error", 
                "message": f"固定班次 #{schedule_id} 不是請假狀態，無需恢復"
            }, ensure_ascii=False)
        
        # 恢復為準備狀態
        update_query = text("""
            UPDATE fixed_schedules
            SET status = '準備',
                note = NULL,
                surcharge = 0,
                modification_time = :mod_time
            WHERE id = :schedule_id
        """)
        
        db.session.execute(update_query, {
            "schedule_id": schedule_id,
            "mod_time": datetime.now()
        })
        db.session.commit()
        
        return json.dumps({
            "status": "success",
            "message": f"固定班次 #{schedule_id} 已恢復為準備狀態\n路線：{schedule[3]} → {schedule[4]}\n時間：{schedule[5]}\n原請假原因：{schedule[2] or '無'}"
        }, ensure_ascii=False)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fixed schedule restore error: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)


# --- 3. Gemini Configuration ---

def get_gemini_tools():
    # Define Tool Declarations
    customer_lookup_func = FunctionDeclaration(
        name="customer_lookup",
        description="Query customer information from database. Use this to find customers.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer name or partial name"},
                "short_name": {"type": "string", "description": "Exact short name"},
                "address": {"type": "string", "description": "Address partial match"},
                "contact_phone": {"type": "string", "description": "Phone number"}
            }
        }
    )

    customer_create_func = FunctionDeclaration(
        name="customer_create",
        description="Create a new customer in the database.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name"},
                "short_name": {"type": "string", "description": "Unique short name (abbreviation)"},
                "address": {"type": "string", "description": "Full address"},
                "contact_phone": {"type": "string", "description": "Phone number"},
                "category": {"type": "string", "description": "Category (e.g. 診所, 學校, 住家)"},
                "remarks": {"type": "string", "description": "Notes"}
            },
            "required": ["name", "address", "short_name", "category"]
        }
    )

    customer_update_func = FunctionDeclaration(
        name="customer_update",
        description="""Update an existing customer's information.
IMPORTANT: 
- Use 'short_name' or 'name' to IDENTIFY which customer to update (the CURRENT value in database).
- Use 'new_*' fields for the NEW values you want to set.
- Example: To change customer '太子龍' short_name to '龍哥', use: short_name='太子龍', new_short_name='龍哥'""",
        parameters={
            "type": "object",
            "properties": {
                "short_name": {"type": "string", "description": "CURRENT short_name to identify the customer (the value currently in database)"},
                "name": {"type": "string", "description": "CURRENT name to identify the customer (use if short_name unknown)"},
                "new_name": {"type": "string", "description": "NEW name value to change to"},
                "new_short_name": {"type": "string", "description": "NEW short_name value to change to"},
                "new_address": {"type": "string", "description": "NEW address value to change to"},
                "new_phone": {"type": "string", "description": "NEW phone number to change to"},
                "new_category": {"type": "string", "description": "NEW category to change to"},
                "new_remarks": {"type": "string", "description": "NEW remarks to change to"}
            }
        }
    )

    customer_delete_func = FunctionDeclaration(
        name="customer_delete",
        description="Delete a customer from the database.",
        parameters={
            "type": "object",
            "properties": {
                "short_name": {"type": "string", "description": "Identify by short_name"},
                "name": {"type": "string", "description": "Identify by name"}
            }
        }
    )

    # --- Booking Tools Definitions ---
    booking_create_func = FunctionDeclaration(
        name="booking_create",
        description="Create a new trip booking.",
        parameters={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date (Format: YYYY-MM-DD). Do NOT use relative terms like 'tomorrow'."},
                "time": {"type": "string", "description": "Time (HH:MM)"},
                "start_point": {"type": "string", "description": "Starting location"},
                "end_point": {"type": "string", "description": "Destination"},
                "via_point": {"type": "string", "description": "Intermediate stop. Extract text after '經/經過'. Exclude '經/經過'."},
                "category": {"type": "string", "description": "Category (default '東洋')"},
                "passenger_name": {"type": "string", "description": "Passenger name. Extract after '乘客/送/載'."},
                "meter_fare": {"type": "integer", "description": "Fare amount (integer). Extract after '金額/車資/費用'."},
                "driver_id": {"type": "integer", "description": "Driver ID. Extract after '司機' or '指定'."}
            },
            "required": ["date", "time", "start_point"]
        }
    )

    trip_update_func = FunctionDeclaration(
        name="trip_update",
        description="Update an existing trip booking.",
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {"type": "integer", "description": "Trip ID to update"},
                "date": {"type": "string", "description": "New date"},
                "time": {"type": "string", "description": "New time"},
                "start_point": {"type": "string", "description": "New start point"},
                "end_point": {"type": "string", "description": "New end point"},
                "via_point": {"type": "string", "description": "New via point"},
                "passenger_name": {"type": "string", "description": "New passenger name"},
                "meter_fare": {"type": "integer", "description": "New fare"},
                "driver_id": {"type": "integer", "description": "New driver ID"}
            },
            "required": ["trip_id"]
        }
    )

    trip_delete_func = FunctionDeclaration(
        name="trip_delete",
        description="Delete (cancel) a trip booking.",
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {"type": "integer", "description": "Trip ID to delete"}
            },
            "required": ["trip_id"]
        }
    )

    # --- Fixed Schedule Tools Definitions ---
    fixed_schedule_lookup_func = FunctionDeclaration(
        name="fixed_schedule_lookup",
        description="Query fixed schedules (固定班次/固定班表). Use this to find recurring trip templates.",
        parameters={
            "type": "object",
            "properties": {
                "schedule_id": {"type": "integer", "description": "Fixed schedule ID to lookup"},
                "customer_name": {"type": "string", "description": "Customer name to search in start/via/end points"}
            }
        }
    )

    fixed_schedule_leave_func = FunctionDeclaration(
        name="fixed_schedule_leave",
        description="Set a fixed schedule to leave status (請假). Requires schedule_id, reason, and surcharge (negative adjustment like -50).",
        parameters={
            "type": "object",
            "properties": {
                "schedule_id": {"type": "integer", "description": "Fixed schedule ID"},
                "reason": {"type": "string", "description": "Leave reason (e.g., '乘客出國', '長期住院')"},
                "surcharge": {"type": "integer", "description": "Surcharge adjustment (usually negative, e.g., -50, -100). This affects total_fare."}
            },
            "required": ["schedule_id", "reason", "surcharge"]
        }
    )

    fixed_schedule_update_func = FunctionDeclaration(
        name="fixed_schedule_update",
        description="Update a fixed schedule's information (修改固定班次). Can update time, location, fare, driver, etc.",
        parameters={
            "type": "object",
            "properties": {
                "schedule_id": {"type": "integer", "description": "Fixed schedule ID to update (required)"},
                "departure_time": {"type": "string", "description": "New departure time (e.g., '10:15', '下午3點')"},
                "start_point": {"type": "string", "description": "New start point"},
                "via_point": {"type": "string", "description": "New via point"},
                "end_point": {"type": "string", "description": "New end point"},
                "base_fare": {"type": "integer", "description": "New base fare"},
                "surcharge": {"type": "integer", "description": "New surcharge"},
                "driver_id": {"type": "integer", "description": "New driver ID"},
                "category": {"type": "string", "description": "New category"},
                "note": {"type": "string", "description": "New note/remarks"}
            },
            "required": ["schedule_id"]
        }
    )

    fixed_schedule_restore_func = FunctionDeclaration(
        name="fixed_schedule_restore",
        description="Restore a fixed schedule from leave status back to ready (從請假恢復為準備).",
        parameters={
            "type": "object",
            "properties": {
                "schedule_id": {"type": "integer", "description": "Fixed schedule ID to restore"}
            },
            "required": ["schedule_id"]
        }
    )

    tools = Tool(
        function_declarations=[
            customer_lookup_func,
            customer_create_func,
            customer_update_func,
            customer_delete_func,
            booking_create_func,
            trip_update_func,
            trip_delete_func,
            fixed_schedule_lookup_func,
            fixed_schedule_leave_func,
            fixed_schedule_update_func,
            fixed_schedule_restore_func
        ]
    )
    return tools


def process_sandbox_message(user_id, text_input, additional_context=""):
    """
    Process message for Customers Sandbox.
    Returns:
        dict: {
            "type": "response" | "proposal" | "missing_info",
            "content": str | dict
        }
    """
    init_vertexai()
    model = GenerativeModel(
        MODEL_ID, # Use the project-configured Gemini 2.5 model
        tools=[get_gemini_tools()]
    )
    
    chat = model.start_chat()
    
    prompt = f"""
    You are a helpful assistant for managing 'customers', 'trip bookings', and 'fixed schedules' (固定班次).
    
    Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Context Info:
    {additional_context}
    
    User Query: "{text_input}"
    
    Instructions:
    1. Analyze the user's intent.
       - Customer management: Create, Update, Delete, Lookup customers.
       - Trip Booking: Create (New Booking), Update, Delete/Cancel trips.
       - Fixed Schedule (固定班次/固定班表): Lookup, Update (修改時間/地點等), Leave (請假), Restore (恢復).
    2. PROACTIVELY call the corresponding tool function.
    3. For 'customer_create', 'short_name' and 'category' are REQUIRED.
       - If missing, CALL THE TOOL ANYWAY with available data (pass null/empty).
    4. For 'booking_create':
       - 'date', 'time', and 'start_point' are REQUIRED. If missing, CALL THE TOOL ANYWAY.
       - Infer dates: "明天" -> YYYY-MM-DD.
       - **Via Point**: Look for '經', '經過', '經由'. Extract the location but EXCLUDE the trigger word.
       - **Category**: Default to '東洋' if not specified.
       - **Passenger Name**: Extract from '乘客', '送', '載'.
       - **Meter Fare**: Extract integer from '金額', '車資', '費用'.
    5. For 'trip_update' / 'trip_delete':
       - You MUST provide 'trip_id'. Infer it from Context Info if user says "that one".
       - If trip_id is unknown/ambiguous, ASK the user to clarify.
    6. For 'fixed_schedule_leave' (固定班次請假):
       - ALL THREE parameters are REQUIRED: schedule_id, reason, surcharge.
       - **surcharge** is usually NEGATIVE (e.g., -50, -100) to reduce fare. If user doesn't specify, CALL THE TOOL ANYWAY to trigger missing_info.
       - Example: "把固定班次#14設為請假，原因是出國" -> fixed_schedule_leave(schedule_id=14, reason="出國", surcharge=null)
    7. For 'fixed_schedule_restore' (固定班次恢復):
       - Only schedule_id is required.
    8. Always answer in Traditional Chinese (Taiwan).

    Few-Shot Examples:
    - User: "預約明天下午兩點從高鐵站經文南路到東洋後門，乘客多多良，金額680"
      Call: booking_create(date="明天", time="14:00", start_point="高鐵站", end_point="東洋後門", via_point="文南路", passenger_name="多多良", meter_fare=680, category="東洋")
    
    - User: "把剛剛那筆改成後天"
      Call: trip_update(trip_id=..., date="後天")
    
    - User: "查太子龍的固定班表"
      Call: fixed_schedule_lookup(customer_name="太子龍")
    
    - User: "把固定班次#21設為請假，乘客出國，加成-50"
      Call: fixed_schedule_leave(schedule_id=21, reason="乘客出國", surcharge=-50)
    
    - User: "恢復固定班次#21"
      Call: fixed_schedule_restore(schedule_id=21)
    
    - User: "將固定班次32的時間改成10:15"
      Call: fixed_schedule_update(schedule_id=32, departure_time="10:15")
    
    - User: "把固定班次#14的起點改成高鐵站"
      Call: fixed_schedule_update(schedule_id=14, start_point="高鐵站")
    
    - User: "將太子龍的簡稱改成龍哥"
      Call: customer_update(short_name="太子龍", new_short_name="龍哥")
      NOTE: short_name="太子龍" identifies the customer, new_short_name="龍哥" is the new value.
    
    - User: "把增添的地址改成台南市東區"
      Call: customer_update(name="增添", new_address="台南市東區")
    """
    
    response = chat.send_message(prompt)
    
    # Check for function calls
    function_call = None
    for part in response.candidates[0].content.parts:
        if part.function_call:
            function_call = part.function_call
            break
            
    if function_call:
        fc = function_call
        fname = fc.name
        fargs = dict(fc.args)
        logger.info(f"🤖 Gemini Function Call: {fname}, args={fargs}")
        
        # Classification - Safe operations (lookup) execute immediately
        if fname == 'customer_lookup':
            result_json = _tool_customer_lookup(fargs)
            response2 = chat.send_message(
                Part.from_function_response(
                    name=fname,
                    response={"content": result_json}
                )
            )
            return {
                "type": "text_response",
                "content": response2.text
            }
        
        if fname == 'fixed_schedule_lookup':
            result_json = _tool_fixed_schedule_lookup(fargs)
            response2 = chat.send_message(
                Part.from_function_response(
                    name=fname,
                    response={"content": result_json}
                )
            )
            return {
                "type": "text_response",
                "content": response2.text
            }
            
        # Unsafe operations -> PROPOSAL
        else:
            # Unsafe operations -> PROPOSAL
            
            # --- CUSTOMER LOGIC ---
            target_name = fargs.get('name')
            target_short = fargs.get('short_name')
            found_target = None
            
            if fname in ['customer_update', 'customer_delete']:
                # ... existing logic ...
                if target_short:
                    found_target = CustomerSandbox.query.filter_by(short_name=target_short).first()
                elif target_name:
                    found_target = CustomerSandbox.query.filter_by(name=target_name).first()
                    
                if not found_target and target_name:
                    filters = []
                    filters.append(CustomerSandbox.name.ilike(f"%{target_name}%"))
                    filters.append(CustomerSandbox.short_name.ilike(f"%{target_name}%"))
                    candidates = CustomerSandbox.query.filter(db.or_(*filters)).limit(5).all()
                    
                    if len(candidates) == 1:
                        found_target = candidates[0]
                        fargs['name'] = found_target.name
                        if found_target.short_name:
                             fargs['short_name'] = found_target.short_name
                    elif len(candidates) > 1:
                        names = [f"{c.name} ({c.short_name})" if c.short_name else c.name for c in candidates]
                        return {"type": "text_response", "content": f"找到多筆類似客戶：\n{', '.join(names)}"}
            
            if fname in ['customer_update', 'customer_delete'] and not found_target:
                 return {"type": "text_response", "content": f"找不到名稱為「{target_short or target_name}」的客戶。"}

            if fname == 'customer_create':
                required_fields = ["name", "address", "short_name", "category"]
                missing = [field for field in required_fields if not fargs.get(field)]
                if missing:
                    field_map = {"name": "名稱", "address": "地址", "short_name": "簡稱", "category": "類別", "contact_phone": "電話"}
                    missing_zh = [field_map.get(m, m) for m in missing]
                    return {
                        "type": "missing_info",
                        "content": f"新增客戶請提供「{'、'.join(missing_zh)}」。",
                        "missing_fields": missing,
                        "draft_data": fargs
                    }
                # Duplicate Check
                check_short = fargs.get('short_name')
                if check_short:
                    existing = CustomerSandbox.query.filter_by(short_name=check_short).first()
                    if existing:
                        return {"type": "text_response", "content": f"簡稱「{check_short}」已被使用，請更換。"}

            # --- BOOKING LOGIC ---
            if fname == 'booking_create':
                required_fields = ["date", "time", "start_point"]
                missing = [field for field in required_fields if not fargs.get(field)]
                if missing:
                    field_map = {"date": "日期", "time": "時間", "start_point": "出發地"}
                    missing_zh = [field_map.get(m, m) for m in missing]
                    return {
                        "type": "missing_info",
                        "content": f"預約叫車請提供「{'、'.join(missing_zh)}」。",
                        "missing_fields": missing,
                        "draft_data": fargs
                    }
            
            if fname in ['trip_update', 'trip_delete']:
                if not fargs.get('trip_id'):
                    return {"type": "text_response", "content": "請問您要修改哪一筆訂單？請提供編號或更多資訊。"}

            # --- FIXED SCHEDULE LOGIC ---
            if fname == 'fixed_schedule_leave':
                required_fields = ["schedule_id", "reason", "surcharge"]
                missing = [field for field in required_fields if fargs.get(field) is None]
                if missing:
                    field_map = {"schedule_id": "班次ID", "reason": "請假原因", "surcharge": "加成調整（通常為負數，如 -50）"}
                    missing_zh = [field_map.get(m, m) for m in missing]
                    return {
                        "type": "missing_info",
                        "content": f"固定班次請假請提供「{'、'.join(missing_zh)}」。\n\n💡 範例：出國一個月 -50",
                        "missing_fields": missing,
                        "draft_data": fargs
                    }
                # 檢查班次是否存在
                check_query = text("SELECT id, status, start_point, end_point FROM fixed_schedules WHERE id = :sid")
                schedule = db.session.execute(check_query, {"sid": fargs.get('schedule_id')}).fetchone()
                if not schedule:
                    return {"type": "text_response", "content": f"找不到固定班次 #{fargs.get('schedule_id')}"}
                if schedule[1] == '請假':
                    return {"type": "text_response", "content": f"固定班次 #{fargs.get('schedule_id')} 已經是請假狀態"}

            if fname == 'fixed_schedule_update':
                if not fargs.get('schedule_id'):
                    return {"type": "text_response", "content": "請問您要修改哪一個固定班次？請提供班次 ID。"}
                # 檢查班次是否存在
                check_query = text("SELECT id, departure_time, start_point, end_point FROM fixed_schedules WHERE id = :sid")
                schedule = db.session.execute(check_query, {"sid": fargs.get('schedule_id')}).fetchone()
                if not schedule:
                    return {"type": "text_response", "content": f"找不到固定班次 #{fargs.get('schedule_id')}"}
                # 檢查是否有指定要修改的內容
                update_fields = ['departure_time', 'start_point', 'via_point', 'end_point', 'base_fare', 'surcharge', 'driver_id', 'category', 'note']
                has_update = any(fargs.get(f) is not None for f in update_fields)
                if not has_update:
                    return {"type": "text_response", "content": "請問您要修改什麼內容？可修改：時間、起點、途經、終點、車資、加成、司機、類別、備註"}

            if fname == 'fixed_schedule_restore':
                if not fargs.get('schedule_id'):
                    return {"type": "text_response", "content": "請問您要恢復哪一個固定班次？請提供班次 ID。"}
                # 檢查班次是否存在且是請假狀態
                check_query = text("SELECT id, status FROM fixed_schedules WHERE id = :sid")
                schedule = db.session.execute(check_query, {"sid": fargs.get('schedule_id')}).fetchone()
                if not schedule:
                    return {"type": "text_response", "content": f"找不到固定班次 #{fargs.get('schedule_id')}"}
                if schedule[1] != '請假':
                    return {"type": "text_response", "content": f"固定班次 #{fargs.get('schedule_id')} 不是請假狀態，無需恢復"}

            # --- SUMMARY GENERATION ---
            summary = ""
            if fname == 'customer_create':
                summary = (
                    f"📝 新增客戶\n"
                    f"┌─────────────\n"
                    f"│ 名稱：{fargs.get('name', '未指定')}\n"
                    f"│ 簡稱：{fargs.get('short_name', '未指定')}\n"
                    f"│ 類別：{fargs.get('category', '未指定')}\n"
                    f"│ 地址：{fargs.get('address', '未指定')}\n"
                    f"└─────────────"
                )
            elif fname == 'customer_update':
                # 美化變更顯示
                target = fargs.get('short_name') or fargs.get('name')
                field_map = {
                    'new_name': '名稱',
                    'new_short_name': '簡稱', 
                    'new_address': '地址',
                    'new_phone': '電話',
                    'new_category': '類別',
                    'new_remarks': '備註'
                }
                changes = []
                for k, label in field_map.items():
                    if fargs.get(k):
                        changes.append(f"│ {label}：{fargs.get(k)}")
                
                changes_text = '\n'.join(changes) if changes else "│ （無變更）"
                summary = (
                    f"✏️ 修改客戶「{target}」\n"
                    f"┌─────────────\n"
                    f"{changes_text}\n"
                    f"└─────────────"
                )
            elif fname == 'customer_delete':
                summary = f"🗑️ 刪除客戶「{fargs.get('short_name') or fargs.get('name')}」"
            elif fname == 'booking_create':
                summary = (
                    f"【預約叫車】\n"
                    f"時間: {fargs.get('date')} {fargs.get('time')}\n"
                    f"起點: {fargs.get('start_point')}\n"
                    f"途經: {fargs.get('via_point') or '無'}\n"
                    f"終點: {fargs.get('end_point') or '無'}\n"
                    f"類別: {fargs.get('category') or '東洋'}"
                )
                if fargs.get('passenger_name'):
                    summary += f"\n乘客: {fargs.get('passenger_name')}"
                if fargs.get('meter_fare'):
                    summary += f"\n金額: {fargs.get('meter_fare')}"
                if fargs.get('driver_id'):
                    summary += f"\n指定司機: {fargs.get('driver_id')}"
            elif fname in ['trip_update', 'trip_delete']:
                tid = fargs.get('trip_id')
                trip_info = "（查無此行程）"
                try:
                    t_sql = text("SELECT date, time, start_point, end_point FROM trips WHERE trip_id = :tid")
                    row = db.session.execute(t_sql, {"tid": tid}).fetchone()
                    if row:
                        t_time = row[1].strftime('%H:%M') if row[1] else "??:??"
                        trip_info = f"{row[0]} {t_time}\n{row[2]} -> {row[3] or '無'}"
                except Exception as e:
                    trip_info = f"（查詢失敗: {str(e)}）"

                if fname == 'trip_update':
                    summary = f"【修改行程 #{tid}】\n原訂:\n{trip_info}\n\n變更內容:\n{json.dumps(fargs, ensure_ascii=False, indent=2)}"
                else:
                    summary = f"【取消行程 #{tid}】\n原訂:\n{trip_info}"
            
            elif fname == 'fixed_schedule_leave':
                sid = fargs.get('schedule_id')
                schedule_info = "（查無此班次）"
                try:
                    s_sql = text("SELECT departure_time, start_point, end_point, surcharge FROM fixed_schedules WHERE id = :sid")
                    row = db.session.execute(s_sql, {"sid": sid}).fetchone()
                    if row:
                        s_time = row[0].strftime('%H:%M') if row[0] else "??:??"
                        schedule_info = f"時間：{s_time}\n路線：{row[1]} → {row[2]}\n原加成：{row[3] or 0}"
                except Exception as e:
                    schedule_info = f"（查詢失敗: {str(e)}）"
                
                summary = (
                    f"【固定班次請假 #{sid}】\n"
                    f"{schedule_info}\n\n"
                    f"📝 請假原因：{fargs.get('reason')}\n"
                    f"💰 新加成：{fargs.get('surcharge')}"
                )
            
            elif fname == 'fixed_schedule_update':
                sid = fargs.get('schedule_id')
                schedule_info = "（查無此班次）"
                try:
                    s_sql = text("SELECT departure_time, start_point, end_point FROM fixed_schedules WHERE id = :sid")
                    row = db.session.execute(s_sql, {"sid": sid}).fetchone()
                    if row:
                        s_time = row[0].strftime('%H:%M') if row[0] else "??:??"
                        schedule_info = f"時間：{s_time}\n路線：{row[1]} → {row[2]}"
                except Exception as e:
                    schedule_info = f"（查詢失敗: {str(e)}）"
                
                # 美化變更顯示
                field_map = {
                    'departure_time': '時間',
                    'start_point': '起點',
                    'via_point': '途經',
                    'end_point': '終點',
                    'base_fare': '基本車資',
                    'surcharge': '加成',
                    'driver_id': '司機',
                    'category': '類別',
                    'note': '備註'
                }
                changes = []
                for k, label in field_map.items():
                    if fargs.get(k) is not None:
                        changes.append(f"│ {label}：{fargs.get(k)}")
                
                changes_text = '\n'.join(changes) if changes else "│ （無變更）"
                summary = (
                    f"✏️ 修改固定班次 #{sid}\n"
                    f"┌─────────────\n"
                    f"│ 原班次：{schedule_info}\n"
                    f"├─────────────\n"
                    f"{changes_text}\n"
                    f"└─────────────"
                )
            
            elif fname == 'fixed_schedule_restore':
                sid = fargs.get('schedule_id')
                schedule_info = "（查無此班次）"
                try:
                    s_sql = text("SELECT departure_time, start_point, end_point, note FROM fixed_schedules WHERE id = :sid")
                    row = db.session.execute(s_sql, {"sid": sid}).fetchone()
                    if row:
                        s_time = row[0].strftime('%H:%M') if row[0] else "??:??"
                        schedule_info = f"時間：{s_time}\n路線：{row[1]} → {row[2]}\n請假原因：{row[3] or '無'}"
                except Exception as e:
                    schedule_info = f"（查詢失敗: {str(e)}）"
                
                summary = f"【恢復固定班次 #{sid}】\n{schedule_info}\n\n將恢復為「準備」狀態，加成歸零"
                
            return {
                "type": "proposal",
                "content": {
                    "func_name": fname,
                    "func_args": fargs,
                    "summary_text": summary
                }
            }
            
    else:
        return {
            "type": "text_response",
            "content": response.text
        }

def execute_proposal(func_name, func_args):
    """Executes a previously proposed function."""
    if func_name == 'customer_create':
        return _tool_customer_create(func_args)
    elif func_name == 'customer_update':
        # 轉換參數：
        # 1. 識別用：short_name/name → _identify_short_name/_identify_name
        # 2. 更新值：new_xxx → xxx（去除 new_ 前綴）
        clean_args = {}
        
        # 先提取識別用參數
        identify_short_name = func_args.get('short_name')
        identify_name = func_args.get('name')
        
        if identify_short_name:
            clean_args['_identify_short_name'] = identify_short_name
        if identify_name:
            clean_args['_identify_name'] = identify_name
        
        # 再處理更新值（new_xxx → xxx）
        for k, v in func_args.items():
            if k.startswith('new_'):
                # new_short_name → short_name, new_name → name, etc.
                clean_key = k[4:]
                clean_args[clean_key] = v
            # 跳過原始的 short_name/name（已轉成 _identify_* 了）
        
        logger.info(f"🔧 execute_proposal 轉換後參數: {clean_args}")
        return _tool_customer_update(clean_args)
    elif func_name == 'customer_delete':
        return _tool_customer_delete(func_args)
    elif func_name == 'booking_create':
        return _tool_booking_create(func_args)
    elif func_name == 'trip_update':
        return _tool_trip_update(func_args)
    elif func_name == 'trip_delete':
        return _tool_trip_delete(func_args)
    elif func_name == 'fixed_schedule_leave':
        return _tool_fixed_schedule_leave(func_args)
    elif func_name == 'fixed_schedule_update':
        return _tool_fixed_schedule_update(func_args)
    elif func_name == 'fixed_schedule_restore':
        return _tool_fixed_schedule_restore(func_args)
    else:
        return json.dumps({"status": "error", "message": "Unknown function"})

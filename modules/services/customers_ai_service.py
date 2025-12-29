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
    """Updates a customer."""
    try:
        # Identify target. Prefer short_name or id if available, else name.
        target = None
        if 'short_name' in kwargs:
            target = CustomerSandbox.query.filter_by(short_name=kwargs['short_name']).first()
        elif 'name' in kwargs:
            target = CustomerSandbox.query.filter_by(name=kwargs['name']).first()
        
        if not target:
            return json.dumps({"status": "error", "message": "Customer not found"}, ensure_ascii=False)
        
        # Update fields
        changes = []
        for k, v in kwargs.items():
            if k in ['name', 'short_name'] and k != 'short_name': # allow updating name if referenced by short_name?
                # Simplify: just update whatever is passed except identity if ambiguous
                pass
            
            if hasattr(target, k):
                old_val = getattr(target, k)
                if old_val != v:
                    setattr(target, k, v)
                    changes.append(f"{k}: {old_val} -> {v}")
        
        db.session.commit()
        return json.dumps({"status": "success", "message": f"Updated {target.name}", "changes": changes}, ensure_ascii=False)
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
        description="Update an existing customer's information.",
        parameters={
            "type": "object",
            "properties": {
                "short_name": {"type": "string", "description": "Identify by short_name (preferred)"},
                "name": {"type": "string", "description": "Identify by name (if short_name unknown) OR new name value"},
                "new_address": {"type": "string", "description": "New address value"},
                "new_phone": {"type": "string", "description": "New phone number"},
                "new_category": {"type": "string", "description": "New category"},
                "new_remarks": {"type": "string", "description": "New remarks"}
                # Note: Schema slightly complicated for updates, keeping it flat for ease
                # Mapped to kwargs in execution: new_address -> address
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

    tools = Tool(
        function_declarations=[
            customer_lookup_func,
            customer_create_func,
            customer_update_func,
            customer_delete_func,
            booking_create_func,
            trip_update_func,
            trip_delete_func
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
    You are a helpful assistant for managing 'customers' and 'trip bookings'.
    
    Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    Context Info:
    {additional_context}
    
    User Query: "{text_input}"
    
    Instructions:
    1. Analyze the user's intent.
       - Customer management: Create, Update, Delete, Lookup customers.
       - Trip Booking: Create (New Booking), Update, Delete/Cancel trips.
    2. PROACTIVELY call the corresponding tool function.
    3. For 'customer_create', 'short_name' and 'category' are REQUIRED.
       - If missing, CALL THE TOOL ANYWAY with available data (pass null/empty).
    4. For 'booking_create':
       - 'date', 'time', and 'start_point' are REQUIRED. If missing, CALL THE TOOL ANYWAY.
       - Infer dates: "明天" -> YYYY-MM-DD.
       - **Via Point**: Look for '經', '經過', '經由'. Extract the location but EXCLUDE the trigger word (e.g., "經文南路" -> "文南路").
       - **Category**: Default to '東洋' if not specified.
       - **Passenger Name**: Extract from '乘客', '送', '載' (e.g., "乘客多多良" -> "多多良").
       - **Meter Fare**: Extract integer from '金額', '車資', '費用' (e.g., "金額680" -> 680).
    5. For 'trip_update' / 'trip_delete':
       - You MUST provide 'trip_id'. Infer it from Context Info if user says "that one" or "modify the booking".
       - If trip_id is unknown/ambiguous, ASK the user to clarify instead of guessing.
    6. Always answer in Traditional Chinese (Taiwan).

    Few-Shot Examples:
    - User: "預約明天下午兩點從高鐵站經文南路到東洋後門，乘客多多良，金額680"
      Call: booking_create(date="明天", time="14:00", start_point="高鐵站", end_point="東洋後門", via_point="文南路", passenger_name="多多良", meter_fare=680, category="東洋")
    
    - User: "把剛剛那筆改成後天"
      Call: trip_update(trip_id=..., date="後天")
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
        
        # Classification
        if fname == 'customer_lookup':
            # Execute immediately
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

            # --- SUMMARY GENERATION ---
            summary = ""
            if fname == 'customer_create':
                summary = f"【新增客戶】\n名稱: {fargs.get('name')}\n簡稱: {fargs.get('short_name')}\n..."
            elif fname == 'customer_update':
                summary = f"【修改客戶】\n目標: {fargs.get('short_name') or fargs.get('name')}\n變更: {json.dumps(fargs, ensure_ascii=False)}"
            elif fname == 'customer_delete':
                summary = f"【刪除客戶】\n目標: {fargs.get('short_name') or fargs.get('name')}"
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
        clean_args = {k[4:] if k.startswith('new_') else k: v for k, v in func_args.items()}
        return _tool_customer_update(clean_args)
    elif func_name == 'customer_delete':
        return _tool_customer_delete(func_args)
    elif func_name == 'booking_create':
        return _tool_booking_create(func_args)
    elif func_name == 'trip_update':
        return _tool_trip_update(func_args)
    elif func_name == 'trip_delete':
        return _tool_trip_delete(func_args)
    else:
        return json.dumps({"status": "error", "message": "Unknown function"})

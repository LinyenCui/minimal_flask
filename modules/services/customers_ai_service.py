import logging
import json
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

    tools = Tool(
        function_declarations=[
            customer_lookup_func,
            customer_create_func,
            customer_update_func,
            customer_delete_func
        ]
    )
    return tools


def process_sandbox_message(user_id, text_input):
    """
    Process message for Customers Sandbox.
    Returns:
        dict: {
            "type": "response" | "proposal",
            "content": str (for response) | dict (for proposal: {func_name, func_args, summary})
        }
    """
    init_vertexai()
    model = GenerativeModel(
        MODEL_ID, # Use the project-configured Gemini 2.5 model
        tools=[get_gemini_tools()]
    )
    
    # We also need a chat session potentially, but for now single turn + context?
    # Actually, tool use often requires history.
    # We start a chat.
    chat = model.start_chat()
    
    # System instruction? "You are a database assistant..."
    # Gemini API supports system_instruction in GenerativeModel init (newer SDKs).
    # I'll add a preamble to the user message or try system_config if available.
    
    prompt = f"""
    You are a database administrator assistant for the 'customers' table.
    
    User Query: "{text_input}"
    
    Instructions:
    1. Analyze the user's intent (Query, Create, Update, Delete).
    2. PROACTIVELY call the corresponding tool function.
    3. For 'customer_create', 'short_name' and 'category' are REQUIRED. If missing, ASK the user for them.
    4. For 'lookup', partial name is enough.
    5. For 'create', infer the name and address from the text.
       - Example: "新增客戶 肯德基基隆路店" -> name="肯德基基隆路店"
    6. Always answer in Traditional Chinese (Taiwan).
    """
    
    response = chat.send_message(prompt)
    
    # Check for function calls
    # Iterate through parts to find function call
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
            
            # Feed back to Gemini
            response2 = chat.send_message(
                Part.from_function_response(
                    name=fname,
                    response={
                        "content": result_json
                    }
                )
            )
            return {
                "type": "text_response", # Standard text response
                "content": response2.text
            }
            
        else:
            # Unsafe operations -> PROPOSAL
            # Pre-validate target for update/delete to avoid "Customer not found" later
            # And improve UX by finding fuzzy matches
            
            target_name = fargs.get('name')
            target_short = fargs.get('short_name')
            found_target = None
            
            if fname in ['customer_update', 'customer_delete']:
                # 1. Try exact match
                if target_short:
                    found_target = CustomerSandbox.query.filter_by(short_name=target_short).first()
                elif target_name:
                    found_target = CustomerSandbox.query.filter_by(name=target_name).first() # Check exact name first
                    
                if not found_target and target_name:
                    # 2. Try fuzzy match on name AND short_name if exact failed
                    # Logic: User might say "久保田家" (short_name) but Gemini puts it in 'name' arg.
                    
                    filters = []
                    filters.append(CustomerSandbox.name.ilike(f"%{target_name}%"))
                    filters.append(CustomerSandbox.short_name.ilike(f"%{target_name}%"))
                    
                    # Use OR to find in either column
                    candidates = CustomerSandbox.query.filter(db.or_(*filters)).limit(5).all()
                    
                    if len(candidates) == 1:
                        found_target = candidates[0]
                        # Auto-correct the args to use the real name found
                        logger.info(f"Auto-correcting target: '{target_name}' -> Name: '{found_target.name}', Short: '{found_target.short_name}'")
                        fargs['name'] = found_target.name
                        if found_target.short_name:
                            fargs['short_name'] = found_target.short_name
                            
                    elif len(candidates) > 1:
                        # Ambiguous
                        names = [f"{c.name} ({c.short_name})" if c.short_name else c.name for c in candidates]
                        return {
                            "type": "text_response",
                            "content": f"找到多筆類似客戶，請問是指哪一個？\n{', '.join(names)}"
                        }
            
            # If still not found for update/delete, abort proposal
            if fname in ['customer_update', 'customer_delete'] and not found_target:
                 return {
                    "type": "text_response",
                    "content": f"找不到名稱為「{target_short or target_name}」的客戶。請確認名稱是否正確，或先查詢確認。"
                }

            summary = f"欲執行操作：{fname}\n參數：{json.dumps(fargs, ensure_ascii=False)}"
            # Map standard Create/Update/Delete to nice Chinese summary
            # Map standard Create/Update/Delete to nice Chinese summary
            if fname == 'customer_create':
                summary = (
                    f"【新增客戶】\n"
                    f"名稱: {fargs.get('name')}\n"
                    f"簡稱: {fargs.get('short_name') or '無'}\n"
                    f"地址: {fargs.get('address') or '無'}\n"
                    f"電話: {fargs.get('contact_phone') or '無'}\n"
                    f"類別: {fargs.get('category') or '無'}"
                )
            elif fname == 'customer_update':
                summary = f"【修改客戶】\n目標: {fargs.get('short_name') or fargs.get('name')}\n變更內容: {json.dumps(fargs, ensure_ascii=False)}"
            elif fname == 'customer_delete':
                summary = f"【刪除客戶】\n目標: {fargs.get('short_name') or fargs.get('name')}"
                
            return {
                "type": "proposal",
                "content": {
                    "func_name": fname,
                    "func_args": fargs,
                    "summary_text": summary
                }
            }
            
    else:
        # Just text response (clarification or answer)
        return {
            "type": "text_response",
            "content": response.text
        }

def execute_proposal(func_name, func_args):
    """Executes a previously proposed function."""
    if func_name == 'customer_create':
        return _tool_customer_create(func_args)
    elif func_name == 'customer_update':
        # Map nice args to actual args if needed?
        # My tool definition for update had "new_address" etc.
        # My _tool_customer_update expects keys like address directly?
        # Let's fix _tool_customer_update to handle "new_" prefix or fix Tool def.
        # It's easier to fix kwargs here.
        clean_args = {}
        for k, v in func_args.items():
            if k.startswith('new_'):
                clean_args[k[4:]] = v
            else:
                clean_args[k] = v
        return _tool_customer_update(clean_args)
        
    elif func_name == 'customer_delete':
        return _tool_customer_delete(func_args)
    else:
        return json.dumps({"status": "error", "message": "Unknown function"})

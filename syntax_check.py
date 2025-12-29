
try:
    print("Checking customers_ai_service...")
    from modules.services import customers_ai_service
    print("customers_ai_service imported successfully.")
    
    print("Checking customers_ai_handler...")
    from modules.handlers import customers_ai_handler
    print("customers_ai_handler imported successfully.")
    
    print("Checking booking_service...")
    from modules.services.booking import booking_service
    print("booking_service imported successfully.")
    
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()

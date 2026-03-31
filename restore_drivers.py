import re
from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def restore_drivers():
    with app.app_context():
        try:
            content = open('CLEANUP_BACKUP/auto_backup_20250719_233146.sql', 'r', encoding='utf-8', errors='ignore').read()
            
            # Find the COPY public.drivers block
            start_marker = "COPY public.drivers (id, name, plate_number, car_brand, car_model) FROM stdin;"
            end_marker = "\\."
            
            start_idx = content.find(start_marker)
            if start_idx == -1:
                print("Could not find COPY public.drivers in backup.")
                return
                
            start_idx += len(start_marker)
            end_idx = content.find(end_marker, start_idx)
            
            copy_data = content[start_idx:end_idx].strip()
            if not copy_data:
                print("No driver data found in COPY block.")
                return
                
            # Clear existing dummy drivers to avoid conflicts
            db.session.execute(text("TRUNCATE TABLE drivers CASCADE;"))
            
            # Format data for INSERT
            lines = copy_data.split('\n')
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 5:
                    did, name, plate, brand, model = parts[:5]
                    # Handle \N which is PostgreSQL NULL
                    plate = None if plate == '\\N' else plate
                    brand = None if brand == '\\N' else brand
                    model = None if model == '\\N' else model
                    
                    db.session.execute(
                        text("INSERT INTO drivers (id, name, plate_number, car_brand, car_model) VALUES (:id, :name, :plate, :brand, :model)"),
                        {"id": int(did), "name": name, "plate": plate, "brand": brand, "model": model}
                    )
            
            # Also fix sequence just in case
            db.session.execute(text("SELECT setval('drivers_id_seq', (SELECT MAX(id) FROM drivers) + 1)"))
            
            db.session.commit()
            print(f"Successfully restored {len(lines)} drivers from backup.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error restoring drivers: {e}")

if __name__ == '__main__':
    restore_drivers()

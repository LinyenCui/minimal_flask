import os

def check_backup(file_path):
    try:
        if os.path.exists(file_path):
            content = open(file_path, 'r', encoding='utf-8', errors='ignore').read()
            start = content.find('CREATE TABLE public.drivers')
            if start != -1:
                print(f"--- DRIVERS SCHEMA in {os.path.basename(file_path)} ---")
                print(content[start:start+400])
            else:
                print(f"No CREATE TABLE public.drivers found in {os.path.basename(file_path)}")
        else:
            print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

if __name__ == '__main__':
    check_backup('CLEANUP_BACKUP/auto_backup_20250719_233146.sql')
    check_backup('scripts/local_backup_20250718_142907.sql')

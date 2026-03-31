import os

def check_backup(file_path):
    try:
        content = open(file_path, 'r', encoding='utf-8', errors='ignore').read()
        start = content.find('CREATE TABLE public.completed_trips (')
        if start != -1:
            end = content.find(');', start)
            print("--- COMPLETED TRIPS SCHEMA ---")
            print(content[start:end+2])
        else:
            print("Could not find COMPLETED TRIPS schema in backup")
    except Exception as e:
        print(f"Error reading backup: {e}")

if __name__ == '__main__':
    check_backup('CLEANUP_BACKUP/auto_backup_20250719_233146.sql')

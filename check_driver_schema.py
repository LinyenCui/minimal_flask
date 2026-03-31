import os

def check_backup():
    try:
        content = open('db_backups/local_backup_20250629_154454.sql', 'r').read()
        start = content.find('CREATE TABLE public.drivers')
        if start != -1:
            print("--- DRIVERS SCHEMA IN BACKUP ---")
            print(content[start:start+400])
        else:
            print("Could not find drivers schema in backup")
    except Exception as e:
        print(f"Error reading backup: {e}")

if __name__ == '__main__':
    check_backup()

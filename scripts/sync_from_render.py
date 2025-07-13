#!/usr/bin/env python3
"""
Render 資料庫同步到本地的自動化腳本
"""
import os
import subprocess
import datetime
from dotenv import load_dotenv

load_dotenv()

# Render 資料庫連線資訊（需要設定在 .env）
RENDER_DB_HOST = os.getenv('RENDER_DB_HOST')
RENDER_DB_USER = os.getenv('RENDER_DB_USER') 
RENDER_DB_NAME = os.getenv('RENDER_DB_NAME')
RENDER_DB_PASSWORD = os.getenv('RENDER_DB_PASSWORD')

# 本地資料庫
LOCAL_DB_NAME = "dispatch_db"

def run_command(command, description=""):
    """執行系統命令並處理錯誤"""
    print(f"🔄 {description}")
    print(f"執行命令: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        if result.stdout:
            print(f"✅ {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 錯誤: {e}")
        if e.stderr:
            print(f"錯誤詳情: {e.stderr}")
        return False

def backup_local_db():
    """備份本地資料庫"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"local_backup_{timestamp}.sql"
    
    command = f"pg_dump -d {LOCAL_DB_NAME} > {backup_file}"
    if run_command(command, "備份本地資料庫"):
        print(f"✅ 本地備份檔案: {backup_file}")
        return backup_file
    return None

def download_from_render():
    """從 Render 下載資料"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    download_file = f"render_backup_{timestamp}.sql"
    
    # 設定 PGPASSWORD 避免密碼提示
    env = os.environ.copy()
    env['PGPASSWORD'] = RENDER_DB_PASSWORD
    
    command = f"pg_dump -h {RENDER_DB_HOST} -U {RENDER_DB_USER} -d {RENDER_DB_NAME} --clean --if-exists > {download_file}"
    
    try:
        result = subprocess.run(command, shell=True, check=True, env=env,
                              capture_output=True, text=True)
        print(f"✅ Render 資料下載完成: {download_file}")
        return download_file
    except subprocess.CalledProcessError as e:
        print(f"❌ 從 Render 下載失敗: {e}")
        return None

def import_to_local(sql_file):
    """匯入到本地資料庫"""
    command = f"psql -d {LOCAL_DB_NAME} -f {sql_file}"
    return run_command(command, f"匯入 {sql_file} 到本地資料庫")

def fix_sequences():
    """修復序列（如果需要）"""
    print("🔧 檢查並修復序列...")
    try:
        result = subprocess.run("python fix_sequence_after_import.py --quick", 
                              shell=True, input="y\n", text=True,
                              capture_output=True)
        if result.returncode == 0:
            print("✅ 序列修復完成")
        else:
            print("⚠️ 序列修復可能有問題，請手動檢查")
    except Exception as e:
        print(f"⚠️ 序列修復時出錯: {e}")

def main():
    """主函數"""
    print("🚀 開始 Render 資料庫同步流程")
    print("=" * 50)
    
    # 檢查必要的環境變數
    if not all([RENDER_DB_HOST, RENDER_DB_USER, RENDER_DB_NAME, RENDER_DB_PASSWORD]):
        print("❌ 請在 .env 文件中設定 Render 資料庫連線資訊：")
        print("   RENDER_DB_HOST=...")
        print("   RENDER_DB_USER=...")  
        print("   RENDER_DB_NAME=...")
        print("   RENDER_DB_PASSWORD=...")
        return False
    
    # 步驟1: 備份本地資料庫
    backup_file = backup_local_db()
    if not backup_file:
        print("❌ 本地備份失敗，中止同步")
        return False
    
    # 步驟2: 從 Render 下載
    render_file = download_from_render()
    if not render_file:
        print("❌ 從 Render 下載失敗，中止同步")
        return False
    
    # 步驟3: 匯入到本地
    if not import_to_local(render_file):
        print("❌ 匯入失敗，可以用以下命令恢復：")
        print(f"   psql -d {LOCAL_DB_NAME} -f {backup_file}")
        return False
    
    # 步驟4: 修復序列
    fix_sequences()
    
    print("🎉 同步完成！")
    print(f"📁 檔案保存:")
    print(f"   本地備份: {backup_file}")
    print(f"   Render 資料: {render_file}")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 
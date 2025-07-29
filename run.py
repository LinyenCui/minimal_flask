#!/usr/bin/env python3
import os
import sys
import subprocess

# 確保在正確的目錄
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 檢查虛擬環境
venv_python = os.path.join(script_dir, 'venv', 'bin', 'python3')
if not os.path.exists(venv_python):
    print("❌ 虛擬環境不存在，請先運行：python3 -m venv venv")
    sys.exit(1)

print("🚀 啟動派車管理系統...")
print(f"📁 工作目錄: {script_dir}")
print(f"🐍 Python: {venv_python}")

# 使用虛擬環境的 Python 執行
try:
    subprocess.run([venv_python, 'app.py'], check=True)
except KeyboardInterrupt:
    print("\n👋 程式已停止")
except Exception as e:
    print(f"❌ 啟動失敗: {e}")
    sys.exit(1)
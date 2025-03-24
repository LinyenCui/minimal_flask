import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# LINE Bot 配置
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# 数据库配置
DATABASE_URL = os.environ.get('DATABASE_URL')

# 应用配置
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 3000))

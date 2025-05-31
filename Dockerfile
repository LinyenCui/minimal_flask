# 使用官方 Python 運行時作為父映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 將依賴性文件複製到容器中
COPY requirements.txt .

# 安裝依賴包
# 我們添加 --no-cache-dir 以減小映像大小
# psycopg2-binary 可能需要 libpq-dev 等系統依賴，如果建置失敗可以考慮添加
# RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# 將當前目錄的內容複製到容器的 /app 目錄中
COPY . .

# 設定環境變數 (如果需要的話，例如 FLASK_APP)
# ENV FLASK_APP app.py
# ENV FLASK_RUN_HOST 0.0.0.0
# ENV FLASK_ENV production

# 容器監聽的端口 (Render 會通過 PORT 環境變數指定實際運行端口)
# 我們 EXPOSE 一個常用端口，但 Gunicorn 會綁定到 $PORT
EXPOSE 3000

# 運行應用的命令
# Gunicorn 會從環境變數 $PORT 獲取端口
# 使用 sh -c 來確保環境變數能被正確解析
CMD ["sh", "-c", "gunicorn app:app --bind \"0.0.0.0:${PORT:-3000}\""] 
import signal
import sys
import logging

def signal_handler(sig, frame):
    logger = logging.getLogger(__name__)
    logger.info("接收到終止信號，正在關閉應用程序...")
    # 如果調度器正在運行，嘗試關閉它
    from app import scheduler
    if hasattr(scheduler, 'running') and scheduler.running:
        try:
            scheduler.shutdown()
            logger.info("調度器已關閉")
        except Exception as e:
            logger.error(f"關閉調度器時出錯: {e}")
    sys.exit(0)

# 修改 init_scheduler 函數
def fix_scheduler_issue():
    # 註冊信號處理函數
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("信號處理已設置，可以使用 Ctrl+C 安全地停止應用程序")

if __name__ == "__main__":
    fix_scheduler_issue()
    print("請在主應用程序中導入並調用 fix_scheduler_issue 函數") 
import logging
import sys
from datetime import datetime

def setup_logger(name='infoHub'):
    """设置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 文件处理器
    log_filename = f'logs/app_{datetime.now().strftime("%Y%m%d")}.log'
    try:
        import os
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
    except Exception:
        file_handler = None

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    if file_handler:
        file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    if file_handler:
        logger.addHandler(file_handler)

    return logger

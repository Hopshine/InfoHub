"""
Ollama服务检查和启动工具
"""
import subprocess
import time
import requests
from utils.logger import setup_logger

logger = setup_logger('ollama_checker')


def check_ollama_service() -> bool:
    """检查Ollama服务是否运行"""
    try:
        # 方法1：检查API端点
        response = requests.get('http://localhost:11434/api/tags', timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            logger.info(f"Ollama服务运行中，可用模型数: {len(models)}")
            return True
    except:
        pass

    try:
        # 方法2：运行ollama list命令
        result = subprocess.run(['ollama', 'list'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            logger.info("Ollama服务已启动")
            return True
    except:
        pass

    return False


def ensure_ollama_running() -> bool:
    """确保Ollama服务运行"""
    if check_ollama_service():
        return True

    logger.info("Ollama服务未运行，尝试启动...")

    try:
        # 尝试运行ollama list来触发服务启动
        subprocess.run(['ollama', 'list'],
                      capture_output=True,
                      timeout=10)

        # 等待服务启动
        for i in range(10):
            time.sleep(1)
            if check_ollama_service():
                logger.info("Ollama服务启动成功")
                return True

        logger.warning("Ollama服务启动超时")
        return False
    except Exception as e:
        logger.error(f"启动Ollama服务失败: {e}")
        return False


def get_available_models() -> list:
    """获取可用的Ollama模型列表"""
    try:
        result = subprocess.run(['ollama', 'list'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                models = []
                for line in lines[1:]:  # 跳过标题行
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
                return models
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")

    return []


def recommend_model() -> str:
    """推荐合适的评估模型"""
    models = get_available_models()

    # 优先级：qwen系列 > gemma系列 > 其他
    for model in models:
        if 'qwen' in model.lower():
            if any(size in model for size in ['7b', '14b', '27b']):
                return model

    for model in models:
        if 'gemma' in model.lower():
            return model

    # 返回第一个可用模型
    return models[0] if models else 'qwen3.5:latest'


if __name__ == '__main__':
    print("检查Ollama服务...")
    if ensure_ollama_running():
        print("✓ Ollama服务运行正常")
        models = get_available_models()
        print(f"✓ 可用模型: {', '.join(models[:5])}")
        print(f"✓ 推荐模型: {recommend_model()}")
    else:
        print("✗ Ollama服务未运行")

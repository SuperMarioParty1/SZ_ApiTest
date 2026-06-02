"""
环境配置加载工具
统一从项目根目录的 .env 文件读取配置，不再依赖 config/*.env.yaml
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


def load_test_data(filename: str) -> dict:
    """
    加载 data 目录下的测试数据文件

    :param filename: 文件名，如 'users.yaml'
    :return: 数据字典
    """
    data_path = PROJECT_ROOT / "data" / filename
    if not data_path.exists():
        raise FileNotFoundError(f"测试数据文件不存在: {data_path}")

    with open(data_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _require(key: str) -> str:
    """读取必填环境变量，缺失时报错提示"""
    value = os.getenv(key)
    if value is None:
        raise EnvironmentError(f"缺少环境变量: {key}，请检查项目根目录的 .env 文件")
    return value


# 全局配置单例，直接从 .env 读取
ENV_CONFIG = {
    "base_url": _require("BASE_URL_DEV"),
    "super_token": _require("SUPER_TOKEN"),
}

logger.info(f"已加载环境配置，base_url={ENV_CONFIG['base_url']}")

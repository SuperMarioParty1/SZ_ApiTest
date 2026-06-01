"""
环境配置加载工具
根据 ENV 环境变量自动加载对应的 yaml 配置文件
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


def load_env_config(env: str = None) -> dict:
    """
    加载指定环境的配置文件

    :param env: 环境名称，默认读取 ENV 环境变量，fallback 为 dev
    :return: 配置字典
    """
    env = env or os.getenv("ENV", "dev")
    config_path = PROJECT_ROOT / "config" / f"{env}.env.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"环境配置文件不存在: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"已加载环境配置: {env} -> {config_path}")
    return config


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


# 全局配置单例
ENV_CONFIG = load_env_config()

"""
环境配置加载工具
统一从项目根目录的 .env 文件读取配置

.env 约定：
  BASE_URL_2102=http://test.kuso.xyz:2102
  BASE_URL_2106=http://test.kuso.xyz:2106
  ...
  SUPER_TOKEN=xxxxx

用例中按端口获取 base_url：
  from utils.env_loader import get_base_url, ENV_CONFIG
  base_url = get_base_url(2102)
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


def get_env(key: str) -> str:
    """读取环境变量，缺失时报错提示"""
    value = os.getenv(key)
    if value is None:
        raise EnvironmentError(f"缺少环境变量: {key}，请检查项目根目录的 .env 文件")
    return value


def get_base_url(port: int | str) -> str:
    """
    按端口获取 base_url

    用法：
        get_base_url(2102)  ->  读取 .env 中的 BASE_URL_2102
    """
    key = f"BASE_URL_{port}"
    url = get_env(key)
    logger.debug(f"base_url({port}) = {url}")
    return url


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


# 全局配置：只包含不依赖端口的公共配置
ENV_CONFIG = {
    "super_token": get_env("SUPER_TOKEN"),
}

logger.info("环境配置已加载")

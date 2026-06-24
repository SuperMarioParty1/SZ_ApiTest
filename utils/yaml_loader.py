from __future__ import annotations

"""
YAML 用例加载工具
负责读取 testcases 目录下的 yaml 用例文件，并转换为 httprunner 可执行格式
"""
import yaml
from pathlib import Path
from loguru import logger


def load_yaml_testcase(yaml_path: str | Path) -> dict:
    """
    加载单个 yaml 测试用例文件

    :param yaml_path: yaml 文件路径
    :return: 用例字典
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"用例文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        testcase = yaml.safe_load(f)

    logger.debug(f"已加载用例: {path.name}")
    return testcase


def load_yaml_testcases_from_dir(dir_path: str | Path) -> list[dict]:
    """
    批量加载目录下所有 yaml 测试用例

    :param dir_path: 目录路径
    :return: 用例列表
    """
    dir_path = Path(dir_path)
    testcases = []

    for yaml_file in sorted(dir_path.glob("**/*.yaml")):
        try:
            tc = load_yaml_testcase(yaml_file)
            testcases.append(tc)
        except Exception as e:
            logger.warning(f"加载用例失败 [{yaml_file}]: {e}")

    logger.info(f"共加载 {len(testcases)} 个用例，来源目录: {dir_path}")
    return testcases

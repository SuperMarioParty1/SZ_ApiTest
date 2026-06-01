"""
debugtalk.py - httprunner 钩子函数文件
放在项目根目录或 hooks 目录，用于定义自定义函数供 yaml 用例中引用

使用方式：在 yaml 用例中通过 ${function_name(args)} 调用
"""
import hashlib
import time
from loguru import logger


def get_timestamp() -> int:
    """获取当前时间戳（秒）"""
    return int(time.time())


def get_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


def md5_encrypt(text: str) -> str:
    """MD5 加密"""
    return hashlib.md5(text.encode()).hexdigest()


def concat_str(*args) -> str:
    """字符串拼接"""
    return "".join(str(a) for a in args)


def sleep(seconds: float):
    """等待指定秒数"""
    logger.info(f"等待 {seconds} 秒...")
    time.sleep(seconds)


def assert_equal(check_value, expect_value, msg: str = ""):
    """自定义断言：相等"""
    assert check_value == expect_value, (
        f"断言失败 {msg}: 期望 [{expect_value}]，实际 [{check_value}]"
    )


def assert_contains(check_value: str, expect_str: str):
    """自定义断言：包含"""
    assert expect_str in check_value, (
        f"断言失败: [{check_value}] 中不包含 [{expect_str}]"
    )

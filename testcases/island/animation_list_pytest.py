# 纯 pytest + requests 写法，接入自定义报告
# 运行命令：python run.py --path testcases/island/test_animation_list_pytest.py
import time
import pytest
import requests

from utils.env_loader import ENV_CONFIG

BASE_URL = ENV_CONFIG["base_url"]

PARAMS = {
    "tk": ENV_CONFIG["super_token"],
    "lang": "zh_CN",
    "isDynamic": 1,
    "ui_test": 1,
    "page": 1,
    "sysversion": "1.0.2",
    "app": "hzm",
    "device": "huawei",
    "vip": 0,
    "version": "3.2.1",
    "platform": "ios",
    "currency": "HKD",
    "cache_key_on": 0,
}

# 你接口返回的 24 条 name 完全匹配
EXPECTED_NAMES = [
    "狗狗",
    "猫",
    "爱心碰撞",
    "地下城堡4",
    "梦幻蝴蝶",
    "柯基骑滑板车",
    "马阿呆-马到成功",
    "马上有钱",
    "黑猫探月",
    "【DIY】亚克力吊坠",
    "赛车跑马灯",
    "懵懵兔秋千",
    "【DIY】水晶小卡",
    "柯基爬杆",
    "升降篮",
    "【DIY】黑胶唱片",
    "屁屁薯春天",
    "two兔",
    "荔枝猫猫虫",
    "写轮眼",
    "柴犬健身",
    "堆堆爱心",
    "熊猫树枝",
    "非主流猫b"
]


@pytest.fixture(scope="module")
def animation_list_response():
    """发送请求，整个模块复用同一个响应"""
    params = {**PARAMS, "timestamp": int(time.time())}
    resp = requests.get(f"{BASE_URL}/island/animation-list", params=params)
    return resp


class TestAnimationList:
    """动画岛列表接口测试"""

    def _base_record(self, record_request, response, check_item, assert_method, expect_value, actual_value):
        """统一上报请求数据到报告"""
        record_request({
            "url": f"{BASE_URL}/island/animation-list",
            "method": "GET",
            "params": {**PARAMS, "timestamp": "动态生成"},
            "request_headers": dict(response.request.headers),
            "status_code": response.status_code,
            "response_body": response.text,
            "asserts": [{
                "check_item": check_item,
                "assert_method": assert_method,
                "expect_value": expect_value,
                "actual_value": actual_value,
            }],
        })

    def test_status_code(self, animation_list_response, record_request):
        """HTTP 状态码应为 200"""
        actual = animation_list_response.status_code
        self._base_record(record_request, animation_list_response,
                          "status_code", "==", 200, actual)
        assert actual == 200

    def test_business_code(self, animation_list_response, record_request):
        """业务 code 应为 0"""
        body = animation_list_response.json()
        actual = body["code"]
        self._base_record(record_request, animation_list_response,
                          "content.code", "==", 0, actual)
        assert actual == 0, f"业务码异常: {body.get('msg')}"

    def test_msg_success(self, animation_list_response, record_request):
        """msg 应为 成功"""
        body = animation_list_response.json()
        actual = body["msg"]
        self._base_record(record_request, animation_list_response,
                          "content.msg", "==", "成功", actual)
        assert actual == "成功"

    def test_list_length(self, animation_list_response, record_request):
        """data.list 长度应为 24"""
        body = animation_list_response.json()
        data_list = body["data"]["list"]
        actual = len(data_list)
        self._base_record(record_request, animation_list_response,
                          "content.data.list", "len ==", 24, actual)
        assert actual == 24, f"列表长度期望 24，实际 {actual}"

    @pytest.mark.parametrize("index, expected_name", enumerate(EXPECTED_NAMES))
    def test_list_item_name(self, animation_list_response, record_request, index, expected_name):
        """逐项校验 list 中每个 name"""
        body = animation_list_response.json()
        data_list = body["data"]["list"]
        actual_name = data_list[index]["name"]
        self._base_record(record_request, animation_list_response,
                          f"content.data.list[{index}].name", "==", expected_name, actual_name)
        assert actual_name == expected_name, (
            f"list[{index}].name 期望: {expected_name}，实际: {actual_name}"
        )
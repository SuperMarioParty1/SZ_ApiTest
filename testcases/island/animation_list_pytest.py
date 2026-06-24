# 纯 pytest + requests 写法，接入自定义报告
# 运行命令：python run.py --path testcases/island/test_animation_list_pytest.py
import time
import pytest

from utils.env_loader import ENV_CONFIG, get_base_url
from utils.http_client import get_with_retry

BASE_URL = get_base_url(2102)

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
    resp = get_with_retry(f"{BASE_URL}/island/animation-list", params=params)
    return resp


# ──────────────────────────────────────────────
# 多语言测试：切换 lang 参数，验证接口基础可用性
# ──────────────────────────────────────────────

LANGUAGES = [
    ("zh_CN",       "简体中文"),
    ("zh-Hant_CN",  "繁体中文"),
    ("en_CN",       "英语"),
    ("ja_CN",       "日语"),
    ("es_CN",       "西班牙语"),
]


@pytest.fixture(params=LANGUAGES, ids=[lang for lang, _ in LANGUAGES], scope="module")
def lang_response(request):
    """每种语言单独发一次请求，fixture 自动参数化"""
    lang_code, lang_name = request.param
    params = {**PARAMS, "lang": lang_code, "timestamp": int(time.time())}
    resp = get_with_retry(f"{BASE_URL}/island/animation-list", params=params)
    # 把语言信息挂在响应上，方便测试函数取用
    resp._lang_code = lang_code
    resp._lang_name = lang_name
    return resp


class TestAnimationListMultiLang:
    """动画岛列表接口 - 多语言切换测试"""

    def _record(self, record_request, resp, check_item, assert_method, expect, actual):
        record_request({
            "url": resp.url,
            "method": "GET",
            "params": {**PARAMS, "lang": resp._lang_code, "timestamp": "动态生成"},
            "request_headers": dict(resp.request.headers),
            "status_code": resp.status_code,
            "response_body": resp.text,
            "asserts": [{
                "check_item": check_item,
                "assert_method": assert_method,
                "expect_value": expect,
                "actual_value": actual,
            }],
        })

    def test_status_code(self, lang_response, record_request):
        """各语言 HTTP 状态码应为 200"""
        actual = lang_response.status_code
        self._record(record_request, lang_response, "status_code", "==", 200, actual)
        assert actual == 200, f"[{lang_response._lang_name}] 状态码异常: {actual}"

    def test_business_code(self, lang_response, record_request):
        """各语言业务 code 应为 0"""
        body = lang_response.json()
        actual = body["code"]
        self._record(record_request, lang_response, "content.code", "==", 0, actual)
        assert actual == 0, f"[{lang_response._lang_name}] 业务码异常: {body.get('msg')}"

    def test_list_not_empty(self, lang_response, record_request):
        """各语言 data.list 不为空"""
        body = lang_response.json()
        actual = len(body["data"]["list"])
        self._record(record_request, lang_response, "content.data.list", "len > 0", actual, actual)
        assert actual > 0, f"[{lang_response._lang_name}] 列表为空"

    def test_list_length(self, lang_response, record_request):
        """各语言 data.list 长度应为 24"""
        body = lang_response.json()
        actual = len(body["data"]["list"])
        self._record(record_request, lang_response, "content.data.list", "len ==", 24, actual)
        assert actual == 24, f"[{lang_response._lang_name}] 列表长度期望 24，实际 {actual}"

    @pytest.mark.parametrize("index, expected_name", enumerate(EXPECTED_NAMES))
    def test_list_item_name(self, lang_response, record_request, index, expected_name):
        """各语言逐项校验 list 中每个 name"""
        body = lang_response.json()
        actual_name = body["data"]["list"][index]["name"]
        self._record(record_request, lang_response,
                     f"content.data.list[{index}].name", "==", expected_name, actual_name)
        assert actual_name == expected_name, (
            f"[{lang_response._lang_name}] list[{index}].name 期望: {expected_name}，实际: {actual_name}"
        )

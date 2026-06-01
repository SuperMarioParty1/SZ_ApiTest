# 纯 pytest + requests 写法，接入自定义报告
# 运行命令：python run.py --path testcases/theme/test_vote_list_pytest.py
import time
import pytest
import requests

BASE_URL = "http://test.kuso.xyz:2102"

PARAMS = {
    "app": "hzm",
    "channel": "AppStore",
    "device": "iPhone12,5",
    "lang": "en_CN",
    "page": 1,
    "platform": "ios",
    "sysversion": "15.1",
    "uuid": "sssssfhhh",
    "version": "1.0.0",
    "vip": 1,
    "tk": "x8eec9c967b71c6cb98b295179ec14c2cx",
    "cat": 0,
    "currency": "HKD",
    "cache_key_on": 0,
}

EXPECTED_DATA = ["ACGN", "Game", "Hip Hop", "Mad", "Motivation", "Car", "Cyberpunk", "Heal"]


@pytest.fixture(scope="module")
def vote_list_response():
    """发送请求，整个模块复用同一个响应"""
    params = {**PARAMS, "timestamp": int(time.time())}
    resp = requests.get(f"{BASE_URL}/theme/vote-list", params=params)
    return resp


class TestVoteList:
    """主题投票列表接口测试"""

    def _base_record(self, record_request, vote_list_response, check_item, assert_method, expect_value, actual_value):
        """统一上报请求数据到报告"""
        record_request({
            "url": f"{BASE_URL}/theme/vote-list",
            "method": "GET",
            "params": {**PARAMS, "timestamp": "动态生成"},
            "request_headers": dict(vote_list_response.request.headers),
            "status_code": vote_list_response.status_code,
            "response_body": vote_list_response.text,
            "asserts": [{
                "check_item": check_item,
                "assert_method": assert_method,
                "expect_value": expect_value,
                "actual_value": actual_value,
            }],
        })

    def test_status_code(self, vote_list_response, record_request):
        """HTTP 状态码应为 200"""
        actual = vote_list_response.status_code
        self._base_record(record_request, vote_list_response,
                          "status_code", "==", 200, actual)
        assert actual == 200

    def test_business_status(self, vote_list_response, record_request):
        """业务状态码 status 应为 0"""
        body = vote_list_response.json()
        actual = body["status"]
        self._base_record(record_request, vote_list_response,
                          "content.status", "==", 0, actual)
        assert actual == 0, f"业务状态码异常: {body.get('msg')}"

    def test_data_is_list(self, vote_list_response, record_request):
        """data 字段应为数组类型"""
        body = vote_list_response.json()
        actual = type(body["data"]).__name__
        self._base_record(record_request, vote_list_response,
                          "content.data", "type ==", "list", actual)
        assert isinstance(body["data"], list)

    def test_data_length(self, vote_list_response, record_request):
        """data 数组长度应为 8"""
        body = vote_list_response.json()
        actual = len(body["data"])
        self._base_record(record_request, vote_list_response,
                          "content.data", "len ==", 8, actual)
        assert actual == 8, f"data 长度期望 8，实际 {actual}"

    @pytest.mark.parametrize("index, expected_name", enumerate(EXPECTED_DATA))
    def test_data_item_name(self, vote_list_response, record_request, index, expected_name):
        """逐项校验 data 中每个元素的 name 字段"""
        body = vote_list_response.json()
        actual_name = body["data"][index]["name"]
        self._base_record(record_request, vote_list_response,
                          f"content.data.{index}.name", "==", expected_name, actual_name)
        assert actual_name == expected_name, (
            f"data[{index}].name 期望 '{expected_name}'，实际 '{actual_name}'"
        )

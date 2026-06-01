# httprunner 原生 Python 写法
# 运行命令：pytest testcases/theme/test_vote_list_hrun.py -v
from httprunner import HttpRunner, Config, Step, RunRequest


class TestVoteList(HttpRunner):

    config = (
        Config("主题投票列表接口")
        .base_url("http://test.kuso.xyz:2102")
        .variables(
            **{
                "UUID1": "sssssfhhh",
                "version": "1.0.0",
                "super_token": "x8eec9c967b71c6cb98b295179ec14c2cx",
            }
        )
    )

    teststeps = [
        Step(
            RunRequest("获取主题投票列表")
            .get("/theme/vote-list")
            .with_params(
                **{
                    "app": "hzm",
                    "channel": "AppStore",
                    "device": "iPhone12,5",
                    "lang": "en_CN",
                    "page": 1,
                    "platform": "ios",
                    "sysversion": "15.1",
                    "timestamp": "${get_timestamp()}",
                    "uuid": "$UUID1",
                    "version": "$version",
                    "vip": 1,
                    "tk": "$super_token",
                    "cat": 0,
                    "currency": "HKD",
                    "cache_key_on": 0,
                }
            )
            .validate()
            .assert_equal("status_code", 200)
            .assert_equal("content.status", 0)
            .assert_type_match("content.data", list)
            .assert_length_equal("content.data", 8)
            .assert_equal("content.data.0.name", "ACGN")
            .assert_equal("content.data.1.name", "Game")
            .assert_equal("content.data.2.name", "Hip Hop")
            .assert_equal("content.data.3.name", "Mad")
            .assert_equal("content.data.4.name", "Motivation")
            .assert_equal("content.data.5.name", "Car")
            .assert_equal("content.data.6.name", "Cyberpunk")
            .assert_equal("content.data.7.name", "Heal")
        ),
    ]


if __name__ == "__main__":
    TestVoteList().test_start()

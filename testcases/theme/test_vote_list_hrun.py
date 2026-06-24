# httprunner 原生 Python 写法
# 运行命令：pytest testcases/theme/test_vote_list_hrun.py -v
from httprunner import HttpRunner, Config, Step, RunRequest
from utils.env_loader import ENV_CONFIG, get_base_url


BASE_URL = get_base_url(2102)
SUPER_TOKEN = ENV_CONFIG["super_token"]


class TestVoteList(HttpRunner):

    config = (
        Config("主题投票列表接口")
        .base_url(BASE_URL)
        .variables(
            **{
                "UUID1": "sssssfhhh",
                "version": "1.0.0",
                "super_token": SUPER_TOKEN,
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
            .assert_equal("body.status", 0)
            .assert_type_match("body.data", list)
            .assert_length_equal("body.data", 8)
            .assert_equal("body.data[0].name", "ACGN")
            .assert_equal("body.data[1].name", "Game")
            .assert_equal("body.data[2].name", "Hip Hop")
            .assert_equal("body.data[3].name", "Mad")
            .assert_equal("body.data[4].name", "Motivation")
            .assert_equal("body.data[5].name", "Car")
            .assert_equal("body.data[6].name", "Cyberpunk")
            .assert_equal("body.data[7].name", "Heal")
        ),
    ]


if __name__ == "__main__":
    TestVoteList().test_start()

"""
pytest conftest.py
全局 fixture 配置 + 自定义 HTML 报告 hook
"""
import pytest
from datetime import datetime
from pathlib import Path
from loguru import logger
from utils.env_loader import ENV_CONFIG

PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

# 用于在 item 上存储请求数据的 key
STEP_DATA_KEY = pytest.StashKey()


# ──────────────────────────────────────────────
# record_request fixture
# ──────────────────────────────────────────────

@pytest.fixture
def record_request(request):
    """
    在测试函数中调用，将请求/响应/断言数据写入当前 item，
    供报告插件读取。

    用法：
        def test_xxx(self, record_request):
            record_request({
                "url": "...", "method": "GET",
                "params": {...}, "status_code": 200,
                "response_body": "...",
                "asserts": [{"check_item": "...", "assert_method": "==",
                             "expect_value": ..., "actual_value": ...}],
            })
    """
    def _record(data: dict):
        # 直接写到 item.stash，pytest 保证同一 item 全程可访问
        request.node.stash[STEP_DATA_KEY] = data

    return _record


# ──────────────────────────────────────────────
# Hook：把 stash 数据透传给 report 对象
# ──────────────────────────────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        report._step_data = item.stash.get(STEP_DATA_KEY, {})


# ──────────────────────────────────────────────
# 自定义报告插件
# ──────────────────────────────────────────────

def pytest_configure(config):
    config.pluginmanager.register(_CustomReportPlugin(), "custom_report_plugin")


class _CustomReportPlugin:
    def __init__(self):
        self.cases = {}   # class_name -> CaseResult

    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return

        from utils.report_generator import CaseResult, StepResult, AssertResult

        step_data = getattr(report, "_step_data", {})
        nodeid = report.nodeid  # e.g. testcases/theme/test_xxx.py::TestClass::test_func[param]

        # 解析 class 名和函数名
        parts = nodeid.split("::")
        class_name = parts[-2] if len(parts) >= 3 else parts[0]
        func_name = parts[-1] if parts else nodeid

        # 构建断言列表
        asserts = []
        for a in step_data.get("asserts", []):
            asserts.append(AssertResult(
                check_item=str(a.get("check_item", "")),
                assert_method=str(a.get("assert_method", "==")),
                expect_value=str(a.get("expect_value", "")),
                actual_value=str(a.get("actual_value", "")),
                passed=report.passed,
            ))

        # 失败时补充错误信息到断言
        if not report.passed and not asserts:
            longrepr = str(report.longrepr)[:400] if report.longrepr else "未知错误"
            asserts.append(AssertResult(
                check_item="assert",
                assert_method="",
                expect_value="",
                actual_value=longrepr,
                passed=False,
            ))

        step = StepResult(
            name=func_name,
            passed=report.passed,
            url=step_data.get("url", ""),
            method=step_data.get("method", ""),
            params=step_data.get("params", {}),
            request_headers=step_data.get("request_headers", {}),
            status_code=step_data.get("status_code", 0),
            response_body=step_data.get("response_body", ""),
            asserts=asserts,
            duration_ms=round(report.duration * 1000, 2),
        )

        if class_name not in self.cases:
            self.cases[class_name] = CaseResult(
                name=class_name,
                log_file="",
                start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        self.cases[class_name].steps.append(step)

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.cases:
            return

        from utils.report_generator import HtmlReportRenderer

        REPORTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"report_{timestamp}.html"

        HtmlReportRenderer().render(list(self.cases.values()), report_path)

        import subprocess
        subprocess.run(["open", str(report_path)])


# ──────────────────────────────────────────────
# 原有 fixture
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    return ENV_CONFIG["base_url"]


@pytest.fixture(scope="session")
def admin_token(base_url) -> str:
    import httpx
    from utils.env_loader import load_test_data
    users = load_test_data("users.yaml")
    admin = users["admin"]
    resp = httpx.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": admin["username"], "password": admin["password"]},
    )
    assert resp.status_code == 200, f"管理员登录失败: {resp.text}"
    logger.info("管理员 token 获取成功")
    return resp.json()["data"]["token"]


@pytest.fixture(scope="function")
def user_token(base_url) -> str:
    import httpx
    from utils.env_loader import load_test_data
    users = load_test_data("users.yaml")
    user = users["normal_user"]
    resp = httpx.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    assert resp.status_code == 200, f"普通用户登录失败: {resp.text}"
    return resp.json()["data"]["token"]

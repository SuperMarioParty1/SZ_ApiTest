from __future__ import annotations

"""
pytest conftest.py
全局 fixture 配置 + 自定义 HTML 报告 hook
"""
import os
import pytest
from datetime import datetime
from pathlib import Path
from loguru import logger
from utils.env_loader import ENV_CONFIG

PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
NO_OPEN_ENV_KEY = "NO_OPEN_REPORT"

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
        self.cases = {}   # case_key -> CaseResult
        self.processed_logs = set(LOGS_DIR.glob("*.run.log"))

    def _is_httprunner_case(self, file_name: str) -> bool:
        return file_name.endswith("_test") or file_name.endswith("_hrun")

    def _find_yaml_for_py_case(self, file_path: Path) -> Path | None:
        for suffix in ("_test", "_hrun"):
            if file_path.stem.endswith(suffix):
                yaml_path = file_path.with_name(f"{file_path.stem[:-len(suffix)]}.yaml")
                if yaml_path.exists():
                    return yaml_path
        return None

    def _get_new_run_log(self) -> Path | None:
        log_files = sorted(LOGS_DIR.glob("*.run.log"), key=lambda path: path.stat().st_mtime)
        for log_file in log_files:
            if log_file not in self.processed_logs:
                self.processed_logs.add(log_file)
                return log_file
        return None

    def _build_case_from_run_log(self, file_path: Path, case_name: str):
        from utils.report_generator import CaseResult, LogParser

        log_file = self._get_new_run_log()
        if not log_file:
            return None

        yaml_path = self._find_yaml_for_py_case(file_path)
        parsed_case = LogParser().parse(log_file, yaml_path=yaml_path)
        parsed_case.name = case_name
        parsed_case.log_file = log_file.name
        return parsed_case

    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return

        from utils.report_generator import CaseResult, StepResult, AssertResult

        step_data = getattr(report, "_step_data", {})
        nodeid = report.nodeid  # e.g. testcases/theme/test_xxx.py::TestClass::test_func[param]

        # 解析 class 名和函数名
        parts = nodeid.split("::")
        file_path = Path(parts[0]) if parts else Path(nodeid)
        file_name = file_path.stem
        class_name = parts[-2] if len(parts) >= 3 else parts[0]
        func_name = parts[-1] if parts else nodeid
        case_name = f"{file_name}::{class_name}"
        # pytest 对非 ASCII 参数做了 unicode 转义，还原成可读中文
        try:
            func_name = func_name.encode('raw_unicode_escape').decode('unicode_escape')
        except Exception:
            pass

        # 如果函数名带有 [param] 且 class 是参数化的 fixture，把参数提取出来作为分组 key
        # 例如：test_list_item_name[zh_CN-0-狗狗] -> class_name = "TestAnimationListMultiLang[zh_CN]"
        #        test_status_code[zh-Hant_CN]      -> class_name = "TestAnimationListMultiLang[zh-Hant_CN]"
        import re
        fixture_param_match = re.search(r'^[^[]+\[([^\]]+)\]', func_name)
        if fixture_param_match and 'MultiLang' in class_name:
            param_str = fixture_param_match.group(1)
            # 从已知的 lang code 列表里精确匹配前缀，避免 zh-Hant_CN 被误切
            known_langs = ["zh-Hant_CN", "zh_CN", "en_CN", "ja_CN", "es_CN"]
            matched_lang = next((lang for lang in known_langs if param_str == lang or param_str.startswith(lang + "-")), None)
            if matched_lang:
                case_name = f"{file_name}::{class_name}[{matched_lang}]"
                # 去掉 func_name 里的 fixture 参数部分，保留后面的 parametrize 参数
                func_name = re.sub(
                    r'^([^[]+)\[' + re.escape(matched_lang) + r'-?([^\]]*)\](.*)$',
                    lambda m: m.group(1) + (f"[{m.group(2)}]" if m.group(2) else "") + m.group(3),
                    func_name
                )

        if not step_data and self._is_httprunner_case(file_name):
            parsed_case = self._build_case_from_run_log(file_path, case_name)
            if parsed_case:
                if case_name not in self.cases:
                    self.cases[case_name] = parsed_case
                else:
                    self.cases[case_name].steps.extend(parsed_case.steps)
                    if parsed_case.yaml_file:
                        self.cases[case_name].yaml_file = parsed_case.yaml_file
                    if parsed_case.log_file:
                        self.cases[case_name].log_file = parsed_case.log_file
                return

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

        if case_name not in self.cases:
            self.cases[case_name] = CaseResult(
                name=case_name,
                log_file="",
                start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        self.cases[case_name].steps.append(step)

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.cases:
            return

        from utils.report_generator import HtmlReportRenderer, dump_case_results, PYTEST_CASES_JSON_NAME

        REPORTS_DIR.mkdir(exist_ok=True)
        dump_case_results(list(self.cases.values()), REPORTS_DIR / PYTEST_CASES_JSON_NAME)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"report_{timestamp}.html"

        HtmlReportRenderer().render(list(self.cases.values()), report_path)

        if os.getenv(NO_OPEN_ENV_KEY) != "1":
            import subprocess
            subprocess.run(["open", str(report_path)])


# ──────────────────────────────────────────────
# 原有 fixture
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    # 默认读 2102，需要其他端口时在具体用例里覆盖或直接调用 get_base_url(port)
    from utils.env_loader import get_base_url
    return get_base_url(2102)


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

"""
一键运行脚本，自动识别用例类型：
  - yaml 文件  → hrun 执行 → 自定义 HTML 报告（含断言详情）
  - py / 目录  → pytest 执行 → pytest-html 报告

用法：
    python run.py                                               # 运行全部用例
    python run.py --path testcases/theme/test_vote_list.yaml   # 运行 yaml 用例
    python run.py --path testcases/theme/test_vote_list_pytest.py  # 运行 py 用例
    python run.py --path testcases/theme                        # 运行整个目录
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
NO_OPEN_ENV_KEY = "NO_OPEN_REPORT"


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def get_existing_logs() -> set:
    return set(LOGS_DIR.glob("*.run.log"))


def get_new_logs(before: set) -> list:
    after = set(LOGS_DIR.glob("*.run.log"))
    return sorted(after - before, key=lambda f: f.stat().st_mtime)


def open_report(path: Path):
    """macOS 自动打开报告"""
    subprocess.run(["open", str(path)])


def should_open_report(no_open: bool) -> bool:
    return not no_open and os.getenv(NO_OPEN_ENV_KEY) != "1"


# ──────────────────────────────────────────────
# yaml 用例：hrun + 自定义报告
# ──────────────────────────────────────────────

def clean_generated_files(test_path: Path):
    """运行前删除 httprunner 自动生成的 _test.py，确保每次从 yaml 重新生成"""
    test_path = test_path.resolve()
    if test_path.is_file():
        targets = [test_path.parent / (test_path.stem + "_test.py")]
    else:
        targets = list(test_path.rglob("*_test.py"))

    for f in targets:
        if f.exists():
            f.unlink()
            print(f"🗑  已删除旧缓存: {f.relative_to(PROJECT_ROOT.resolve())}")


def get_generated_files(test_path: Path) -> list[Path]:
    test_path = test_path.resolve()
    if test_path.is_file():
        return [test_path.parent / (test_path.stem + "_test.py")]
    return list(test_path.rglob("*_test.py"))


def run_yaml(test_path: str, no_open: bool = False):
    from utils.report_generator import generate_report

    REPORTS_DIR.mkdir(exist_ok=True)
    yaml_path = Path(test_path)
    generated_files = get_generated_files(yaml_path)

    # 每次运行前清理旧的生成文件，避免缓存干扰
    clean_generated_files(yaml_path)

    logs_before = get_existing_logs()

    print(f"\n▶ [yaml 模式] hrun {test_path}\n")
    try:
        result = subprocess.run(["hrun", test_path], cwd=PROJECT_ROOT)
    finally:
        for generated_file in generated_files:
            if generated_file.exists():
                generated_file.unlink()
                print(f"🧹  已清理临时用例: {generated_file.relative_to(PROJECT_ROOT.resolve())}")

    new_logs = get_new_logs(logs_before)
    if not new_logs:
        print("\n⚠️  未检测到新日志文件，报告生成跳过")
        return result.returncode or 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"report_{timestamp}.html"

    print(f"\n▶ 生成自定义报告（含断言详情）...")
    generate_report(
        log_files=new_logs,
        output_path=report_path,
        yaml_path=yaml_path if yaml_path.is_file() else None,
    )
    if should_open_report(no_open):
        open_report(report_path)
    return result.returncode


def run_yaml_and_collect_logs(test_path: str) -> tuple[int, list]:
    yaml_path = Path(test_path)
    generated_files = get_generated_files(yaml_path)
    clean_generated_files(yaml_path)
    logs_before = get_existing_logs()
    print(f"\n▶ [yaml 模式] hrun {test_path}\n")
    try:
        result = subprocess.run(["hrun", test_path], cwd=PROJECT_ROOT)
    finally:
        for generated_file in generated_files:
            if generated_file.exists():
                generated_file.unlink()
                print(f"🧹  已清理临时用例: {generated_file.relative_to(PROJECT_ROOT.resolve())}")
    return result.returncode, get_new_logs(logs_before)


# ──────────────────────────────────────────────
# py / 目录：pytest + pytest-html 报告
# ──────────────────────────────────────────────

def run_pytest(test_path: str, no_open: bool = False):
    """pytest 模式：运行后由 conftest 的 hook 自动生成自定义报告"""
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short",
        # 关闭 pytest-html，由 conftest 插件接管报告生成
        "--no-header",
    ]
    print(f"\n▶ [pytest 模式] {' '.join(cmd)}\n")
    env = os.environ.copy()
    if no_open:
        env[NO_OPEN_ENV_KEY] = "1"
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return result.returncode


def run_directory(test_path: str, no_open: bool = False):
    from utils.report_generator import (
        HtmlReportRenderer,
        LogParser,
        load_case_results,
        PYTEST_CASES_JSON_NAME,
    )

    test_dir = Path(test_path)
    yaml_files = sorted(test_dir.rglob("*.yaml"))
    yaml_case_map = {}
    overall_code = 0

    for yaml_file in yaml_files:
        return_code, new_logs = run_yaml_and_collect_logs(str(yaml_file))
        if return_code != 0:
            overall_code = return_code
        parser = LogParser()
        for log_file in new_logs:
            parsed_case = parser.parse(log_file, yaml_path=yaml_file)
            if parsed_case.name not in yaml_case_map:
                yaml_case_map[parsed_case.name] = parsed_case
            else:
                yaml_case_map[parsed_case.name].steps.extend(parsed_case.steps)

    pytest_code = run_pytest(test_path, no_open=True)
    if pytest_code != 0 and overall_code == 0:
        overall_code = pytest_code

    pytest_cases = load_case_results(REPORTS_DIR / PYTEST_CASES_JSON_NAME)
    yaml_cases = list(yaml_case_map.values())
    merged_cases = yaml_cases + pytest_cases
    if merged_cases:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"report_{timestamp}.html"
        HtmlReportRenderer().render(merged_cases, report_path)
        if should_open_report(no_open):
            open_report(report_path)

    return overall_code


# ──────────────────────────────────────────────
# 入口：自动识别类型
# ──────────────────────────────────────────────

def run(test_path: str, no_open: bool = False):
    path = Path(test_path)

    # 明确是 yaml 文件 → hrun
    if path.suffix in (".yaml", ".yml"):
        return run_yaml(test_path, no_open=no_open)

    if path.is_dir():
        return run_directory(test_path, no_open=no_open)

    # py 文件或目录 → pytest
    return run_pytest(test_path, no_open=no_open)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="接口自动化测试运行脚本")
    parser.add_argument(
        "--path",
        default="testcases",
        help="测试路径：yaml 文件用 hrun，py 文件或目录用 pytest（默认 testcases/）",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="不自动打开测试报告，适用于 Jenkins/CI 环境",
    )
    args = parser.parse_args()
    sys.exit(run(args.path, no_open=args.no_open))

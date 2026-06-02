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
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"


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


def run_yaml(test_path: str):
    from utils.report_generator import generate_report

    REPORTS_DIR.mkdir(exist_ok=True)
    yaml_path = Path(test_path)

    # 每次运行前清理旧的生成文件，避免缓存干扰
    clean_generated_files(yaml_path)

    logs_before = get_existing_logs()

    print(f"\n▶ [yaml 模式] hrun {test_path}\n")
    subprocess.run(["hrun", test_path], cwd=PROJECT_ROOT)

    new_logs = get_new_logs(logs_before)
    if not new_logs:
        print("\n⚠️  未检测到新日志文件，报告生成跳过")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"report_{timestamp}.html"

    print(f"\n▶ 生成自定义报告（含断言详情）...")
    generate_report(
        log_files=new_logs,
        output_path=report_path,
        yaml_path=yaml_path if yaml_path.is_file() else None,
    )
    open_report(report_path)
    return 0


# ──────────────────────────────────────────────
# py / 目录：pytest + pytest-html 报告
# ──────────────────────────────────────────────

def run_pytest(test_path: str):
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
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


# ──────────────────────────────────────────────
# 入口：自动识别类型
# ──────────────────────────────────────────────

def run(test_path: str):
    path = Path(test_path)

    # 明确是 yaml 文件 → hrun
    if path.suffix in (".yaml", ".yml"):
        return run_yaml(test_path)

    # py 文件或目录 → pytest
    return run_pytest(test_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="接口自动化测试运行脚本")
    parser.add_argument(
        "--path",
        default="testcases",
        help="测试路径：yaml 文件用 hrun，py 文件或目录用 pytest（默认 testcases/）",
    )
    args = parser.parse_args()
    sys.exit(run(args.path))

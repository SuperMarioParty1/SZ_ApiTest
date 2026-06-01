"""
自定义 HTML 报告生成器
解析 httprunner 运行日志 + yaml 用例文件，生成包含断言实际值/期望值对比的 HTML 报告

断言数据来源说明：
  - httprunner 只在断言失败时才输出 check_value/expect_value
  - 通过时日志里没有断言详情，因此：
    1. 从日志解析响应体（response body）
    2. 从 yaml 读取断言配置（validate 字段）
    3. 从响应体中提取实际值，与期望值对比展示
"""
import json
import re
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import jmespath
    HAS_JMESPATH = True
except ImportError:
    HAS_JMESPATH = False

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
TESTCASES_DIR = PROJECT_ROOT / "testcases"


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class AssertResult:
    check_item: str       # 检查路径，如 status_code / body.status
    assert_method: str    # 断言方式，如 == / contains
    expect_value: str     # 期望值（来自 yaml）
    actual_value: str     # 实际值（从响应体提取）
    passed: bool


@dataclass
class StepResult:
    name: str
    passed: bool = True
    url: str = ""
    full_url: str = ""
    method: str = ""
    params: dict = field(default_factory=dict)
    request_headers: dict = field(default_factory=dict)
    status_code: int = 0
    response_headers: dict = field(default_factory=dict)
    response_body: str = ""
    asserts: list = field(default_factory=list)
    error_msg: str = ""
    duration_ms: float = 0


@dataclass
class CaseResult:
    name: str
    log_file: str
    start_time: str
    yaml_file: str = ""
    steps: list = field(default_factory=list)

    @property
    def passed(self):
        return all(s.passed for s in self.steps)

    @property
    def total_steps(self):
        return len(self.steps)

    @property
    def passed_steps(self):
        return sum(1 for s in self.steps if s.passed)


# ──────────────────────────────────────────────
# YAML 断言配置读取
# ──────────────────────────────────────────────

class YamlAssertLoader:
    METHOD_DISPLAY = {
        "eq": "==", "equals": "==", "equal": "==",
        "ne": "!=", "not_equal": "!=",
        "gt": ">", "greater_than": ">",
        "lt": "<", "less_than": "<",
        "gte": ">=", "ge": ">=",
        "lte": "<=", "le": "<=",
        "contains": "contains",
        "startswith": "startswith",
        "endswith": "endswith",
        "len_eq": "len ==", "length_equals": "len ==",
        "len_gt": "len >", "length_greater_than": "len >",
        "len_lt": "len <",
        "type": "type ==",
        "type_match": "type ==",
        "regex_match": "regex",
    }

    def load(self, yaml_path: Path) -> list:
        if not yaml_path or not yaml_path.exists():
            return []
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return []
        results = []
        for step in data.get("teststeps", []):
            # validate 可能在 step 顶层，也可能嵌套在 request 里
            validate_list = step.get("validate") or step.get("request", {}).get("validate", [])
            for v in (validate_list or []):
                parsed = self._parse(v)
                if parsed:
                    results.append(parsed)
        return results

    def _parse(self, item):
        if not isinstance(item, dict):
            return None
        # 格式：{eq: [check, expect]}
        for method, value in item.items():
            if isinstance(value, list) and len(value) == 2:
                return {"check": str(value[0]), "method": method, "expect": value[1]}
        # 格式：{check: ..., comparator: ..., expect: ...}
        if "check" in item:
            return {
                "check": str(item.get("check", "")),
                "method": str(item.get("comparator", "eq")),
                "expect": item.get("expect", ""),
            }
        return None

    def display(self, method: str) -> str:
        return self.METHOD_DISPLAY.get(method.lower(), method)


# ──────────────────────────────────────────────
# 响应体实际值提取
# ──────────────────────────────────────────────

class ResponseExtractor:
    def extract(self, check_path: str, status_code: int, response_body: str) -> str:
        check_path = check_path.strip()
        if check_path == "status_code":
            return str(status_code)
        # 兼容 body.xxx 和 content.xxx 两种前缀
        if check_path.startswith("body."):
            return self._from_body(check_path[5:], response_body)
        if check_path.startswith("content."):
            return self._from_body(check_path[8:], response_body)
        if check_path in ("body", "content"):
            return response_body[:200] if response_body else ""
        # 无前缀，直接从 body 取
        return self._from_body(check_path, response_body)

    def _from_body(self, path: str, body_str: str) -> str:
        if not body_str or body_str in ("None", ""):
            return "（无响应体）"
        try:
            body = json.loads(body_str)
        except Exception:
            return "（响应体非 JSON）"
        if not path:
            return json.dumps(body, ensure_ascii=False)
        # jmespath 优先（需要把 data.0.name 转成 data[0].name）
        if HAS_JMESPATH:
            try:
                jmes_path = re.sub(r'\.(\d+)', r'[\1]', path)
                val = jmespath.search(jmes_path, body)
                if val is not None:
                    return json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
            except Exception:
                pass
        # fallback：点分隔逐层取值，数字当索引
        try:
            current = body
            for part in path.split("."):
                if part.isdigit():
                    current = current[int(part)]
                elif isinstance(current, list):
                    current = current[int(part)]
                else:
                    current = current[part]
            return json.dumps(current, ensure_ascii=False) if isinstance(current, (dict, list)) else str(current)
        except Exception:
            return "（路径不存在）"


# ──────────────────────────────────────────────
# 断言执行器
# ──────────────────────────────────────────────

class AssertEvaluator:
    def evaluate(self, method: str, actual: str, expect) -> bool:
        expect_str = str(expect)
        try:
            m = method.lower()
            if m in ("eq", "equals", "equal"):
                try:
                    return float(actual) == float(expect_str)
                except Exception:
                    return actual == expect_str
            elif m in ("ne", "not_equal"):
                return actual != expect_str
            elif m in ("gt", "greater_than"):
                return float(actual) > float(expect_str)
            elif m in ("lt", "less_than"):
                return float(actual) < float(expect_str)
            elif m in ("gte", "ge"):
                return float(actual) >= float(expect_str)
            elif m in ("lte", "le"):
                return float(actual) <= float(expect_str)
            elif m == "contains":
                return expect_str in actual
            elif m == "startswith":
                return actual.startswith(expect_str)
            elif m == "endswith":
                return actual.endswith(expect_str)
            elif m in ("len_eq", "length_equals"):
                return len(json.loads(actual)) == int(expect_str)
            elif m in ("len_gt", "length_greater_than"):
                return len(json.loads(actual)) > int(expect_str)
            elif m in ("len_lt",):
                return len(json.loads(actual)) < int(expect_str)
            elif m in ("type", "type_match"):
                type_map = {"array": list, "list": list, "object": dict, "dict": dict,
                            "string": str, "str": str, "int": int, "integer": int,
                            "float": float, "bool": bool, "boolean": bool, "none": type(None)}
                expected_type = type_map.get(expect_str.lower())
                try:
                    parsed = json.loads(actual)
                    return isinstance(parsed, expected_type) if expected_type else False
                except Exception:
                    return False
        except Exception:
            pass
        return False


# ──────────────────────────────────────────────
# 日志解析器
# ──────────────────────────────────────────────

class LogParser:
    def __init__(self):
        self._loader = YamlAssertLoader()
        self._extractor = ResponseExtractor()
        self._evaluator = AssertEvaluator()

    def parse(self, log_path: Path, yaml_path: Path = None) -> CaseResult:
        content = log_path.read_text(encoding="utf-8")
        start_time = ""
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", content)
        if m:
            start_time = m.group(1)

        yaml_asserts = self._loader.load(yaml_path) if yaml_path else []

        case = CaseResult(
            name=log_path.stem,
            log_file=log_path.name,
            start_time=start_time,
            yaml_file=yaml_path.name if yaml_path else "",
        )
        for block in self._split_steps(content):
            case.steps.append(self._parse_step(block, yaml_asserts))
        return case

    def _split_steps(self, content: str) -> list:
        parts = re.split(r"(?=.*run step begin:.*>>>>>>)", content, flags=re.MULTILINE)
        return [p.strip() for p in parts if "run step begin" in p]

    def _parse_step(self, block: str, yaml_asserts: list) -> StepResult:
        step = StepResult(name="")

        # 步骤名
        m = re.search(r"run step begin:\s*(.+?)\s*>>>>>>", block)
        if m:
            step.name = m.group(1).strip()

        # 第一段 request details（httprunner 内部，含 params）
        sec1 = self._get_section(block, r"={6,} request details ={6,}")
        if sec1:
            m = re.search(r"^url:\s*(.+)$", sec1, re.MULTILINE)
            if m:
                step.url = m.group(1).strip()
            m = re.search(r"^method:\s*(.+)$", sec1, re.MULTILINE)
            if m:
                step.method = m.group(1).strip()
            pj = self._get_json_value(sec1, "params")
            if pj:
                try:
                    step.params = json.loads(pj)
                except Exception:
                    pass

        # 第二段 request details（requests 实际发送，含完整 URL 和请求头）
        sec2 = self._get_section(block, r"={18} request details ={18}")
        if sec2:
            m = re.search(r"^url\s+:\s*(.+)$", sec2, re.MULTILINE)
            if m:
                step.full_url = m.group(1).strip()
            hj = self._get_json_value(sec2, "headers")
            if hj:
                try:
                    step.request_headers = json.loads(hj)
                except Exception:
                    pass

        # response details
        resp = self._get_section(block, r"={18} response details ={18}")
        if resp:
            m = re.search(r"status_code\s*:\s*(\d+)", resp)
            if m:
                step.status_code = int(m.group(1))
            rh = self._get_json_value(resp, "headers")
            if rh:
                try:
                    step.response_headers = json.loads(rh)
                except Exception:
                    pass
            bm = re.search(r"^body\s+:\s*(\{[\s\S]+)", resp, re.MULTILINE)
            if bm:
                step.response_body = bm.group(1).strip()

        # 耗时
        m = re.search(r"response_time\(ms\):\s*([\d.]+)", block)
        if m:
            step.duration_ms = float(m.group(1))

        # 断言
        step.asserts = self._build_asserts(block, yaml_asserts, step.status_code, step.response_body)

        # 错误
        errors = [l for l in block.splitlines() if "| ERROR |" in l]
        if errors:
            step.error_msg = "\n".join(re.sub(r"^\d{4}.*?\| ERROR \|\s*", "", l) for l in errors)
            step.passed = False
        else:
            step.passed = all(a.passed for a in step.asserts) if step.asserts else True

        return step

    def _build_asserts(self, block: str, yaml_asserts: list, status_code: int, response_body: str) -> list:
        results = []
        if yaml_asserts:
            for cfg in yaml_asserts:
                check = cfg["check"]
                method = cfg["method"]
                expect = cfg["expect"]
                actual = self._extractor.extract(check, status_code, response_body)
                passed = self._evaluator.evaluate(method, actual, expect)
                results.append(AssertResult(
                    check_item=check,
                    assert_method=self._loader.display(method),
                    expect_value=str(expect),
                    actual_value=actual,
                    passed=passed,
                ))
            return results
        # fallback：日志中的失败断言
        pat = re.compile(
            r"check_item:\s*(.+)\ncheck_value:\s*(.+)\nassert_method:\s*(.+)\nexpect_value:\s*(.+)",
            re.MULTILINE,
        )
        for m in pat.finditer(block):
            results.append(AssertResult(
                check_item=m.group(1).strip(),
                assert_method=m.group(3).strip(),
                expect_value=m.group(4).strip(),
                actual_value=m.group(2).strip(),
                passed=False,
            ))
        return results

    def _get_section(self, text: str, pattern: str) -> str:
        m = re.search(pattern, text)
        if not m:
            return ""
        start = m.end()
        end_m = re.search(r"\n\d{4}-\d{2}-\d{2}", text[start:])
        end = start + end_m.start() if end_m else len(text)
        return text[start:end].strip()

    def _get_json_value(self, text: str, key: str) -> str:
        # 多行 JSON 对象
        pat = rf"^{key}\s*:\s*(\{{[\s\S]*?\n\}})"
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return m.group(1)
        # 单行
        pat2 = rf"^{key}\s*:\s*(\{{.*?\}})"
        m2 = re.search(pat2, text, re.MULTILINE)
        if m2:
            return m2.group(1)
        return ""


# ──────────────────────────────────────────────
# HTML 渲染器
# ──────────────────────────────────────────────

class HtmlReportRenderer:
    def render(self, cases: list, output_path: Path):
        total = len(cases)
        passed = sum(1 for c in cases if c.passed)
        failed = total - passed
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>神桌接口自动化</title>
<style>{self._css()}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🧪 接口自动化测试报告</h1>
    <p class="meta">生成时间：{generated_at}</p>
  </div>
  <div class="summary">
    <div class="stat-card total"><div class="num">{total}</div><div class="label">总用例数</div></div>
    <div class="stat-card pass"><div class="num">{passed}</div><div class="label">通过</div></div>
    <div class="stat-card fail"><div class="num">{failed}</div><div class="label">失败</div></div>
    <div class="stat-card rate"><div class="num">{int(passed/total*100) if total else 0}%</div><div class="label">通过率</div></div>
  </div>
  {"".join(self._render_case(c, i) for i, c in enumerate(cases))}
</div>
<script>{self._js()}</script>
</body>
</html>"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"✅ 报告已生成: {output_path}")

    def _render_case(self, case: CaseResult, idx: int) -> str:
        cls = "pass" if case.passed else "fail"
        icon = "✅ 通过" if case.passed else "❌ 失败"
        steps_html = "".join(self._render_step(s, i) for i, s in enumerate(case.steps))
        yaml_tag = f'<span class="yaml-tag">{case.yaml_file}</span>' if case.yaml_file else ""
        return f"""
  <div class="case-card {cls}">
    <div class="case-header" onclick="toggle('case-{idx}','arrow-{idx}')">
      <span class="badge {cls}">{icon}</span>
      <span class="case-name">{case.name}</span>
      {yaml_tag}
      <span class="case-meta">{case.passed_steps}/{case.total_steps} 步骤通过 · {case.start_time}</span>
      <span class="arrow" id="arrow-{idx}">▼</span>
    </div>
    <div class="case-body" id="case-{idx}">{steps_html}</div>
  </div>"""

    def _render_step(self, step: StepResult, idx: int) -> str:
        cls = "pass" if step.passed else "fail"
        icon = "✅" if step.passed else "❌"
        duration = f"{step.duration_ms:.1f} ms" if step.duration_ms else ""

        # 断言：始终显示
        asserts_html = self._render_asserts(step.asserts) if step.asserts else ""
        error_html = f'<div class="error-block">⚠️ {step.error_msg}</div>' if step.error_msg else ""

        # 请求参数、请求头、响应体：折叠到「详情」里
        detail_parts = []
        if step.params:
            detail_parts.append(self._kv_table(step.params, "请求参数"))
        if step.request_headers:
            detail_parts.append(self._kv_table(step.request_headers, "请求头"))
        if step.response_body and step.response_body not in ("None", ""):
            try:
                formatted = json.dumps(json.loads(step.response_body), ensure_ascii=False, indent=2)
            except Exception:
                formatted = step.response_body
            detail_parts.append(
                f'<div class="section-title">响应体</div>'
                f'<pre class="code-block">{formatted}</pre>'
            )

        # 失败时详情默认展开，通过时收起
        detail_open = "open" if not step.passed else ""
        detail_html = ""
        if detail_parts:
            detail_id = f"detail-{id(step)}"
            detail_html = f"""
          <div class="detail-toggle" onclick="toggleDetail('{detail_id}')">
            <span class="detail-label">{'▶ 查看详情' if step.passed else '▼ 请求详情'}</span>
          </div>
          <div class="detail-body {detail_open}" id="{detail_id}">
            {"".join(detail_parts)}
          </div>"""

        sc_cls = f"sc-{str(step.status_code)[0]}" if step.status_code else "sc-0"
        method_cls = step.method.lower() if step.method else ""

        return f"""
      <div class="step {cls}">
        <div class="step-header">
          <span>{icon} 步骤 {idx+1}：{step.name}</span>
          <span class="method-badge {method_cls}">{step.method}</span>
          <span class="duration">{duration}</span>
        </div>
        <div class="step-body">
          <div class="url-bar">
            <span class="url-label">URL</span>
            <span class="url-value">{step.url}</span>
            <span class="status-code {sc_cls}">{step.status_code or '-'}</span>
          </div>
          {asserts_html}
          {error_html}
          {detail_html}
        </div>
      </div>"""

    def _render_asserts(self, asserts: list) -> str:
        rows = ""
        for a in asserts:
            icon = "✅" if a.passed else "❌"
            cls = "pass" if a.passed else "fail"
            # 失败时高亮实际值
            actual_cls = "" if a.passed else " actual-fail"
            rows += f"""<tr class="{cls}">
              <td class="assert-icon">{icon}</td>
              <td class="assert-check"><code>{a.check_item}</code></td>
              <td class="assert-method"><span class="method-pill">{a.assert_method}</span></td>
              <td class="assert-expect">{a.expect_value}</td>
              <td class="assert-actual{actual_cls}">{a.actual_value}</td>
            </tr>"""
        return f"""
          <div class="section-title">断言结果</div>
          <table class="assert-table">
            <thead>
              <tr>
                <th style="width:36px"></th>
                <th>检查项</th>
                <th style="width:100px">断言方式</th>
                <th>期望值</th>
                <th>实际值</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>"""

    def _kv_table(self, data: dict, title: str) -> str:
        if not data:
            return ""
        rows = "".join(
            f"<tr><td class='key'>{k}</td><td class='val'>{v}</td></tr>"
            for k, v in data.items()
        )
        return f'<div class="section-title">{title}</div><table class="kv-table"><tbody>{rows}</tbody></table>'

    def _css(self) -> str:
        return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f0f2f5; color: #333; font-size: 14px; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e);
          color: white; padding: 28px 32px; border-radius: 12px; margin-bottom: 20px; }
.header h1 { font-size: 22px; font-weight: 600; }
.meta { margin-top: 6px; opacity: 0.6; font-size: 13px; }
.summary { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { flex: 1; background: white; border-radius: 10px; padding: 20px;
             text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.stat-card .num { font-size: 32px; font-weight: 700; }
.stat-card .label { font-size: 13px; color: #888; margin-top: 4px; }
.stat-card.pass .num { color: #22c55e; }
.stat-card.fail .num { color: #ef4444; }
.stat-card.total .num { color: #3b82f6; }
.stat-card.rate .num { color: #f59e0b; }
.case-card { background: white; border-radius: 10px; margin-bottom: 16px;
             box-shadow: 0 2px 8px rgba(0,0,0,.06); overflow: hidden; }
.case-card.fail { border-left: 4px solid #ef4444; }
.case-card.pass { border-left: 4px solid #22c55e; }
.case-header { display: flex; align-items: center; gap: 12px; padding: 16px 20px;
               cursor: pointer; user-select: none; }
.case-header:hover { background: #fafafa; }
.case-name { font-weight: 600; flex: 1; }
.case-meta { font-size: 12px; color: #999; }
.yaml-tag { font-size: 11px; background: #e0f2fe; color: #0369a1;
            padding: 2px 8px; border-radius: 10px; }
.arrow { color: #aaa; transition: transform .2s; font-size: 12px; }
.arrow.open { transform: rotate(180deg); }
.case-body { padding: 0 20px 16px; display: none; }
.case-body.open { display: block; }
.badge { padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge.pass { background: #dcfce7; color: #166534; }
.badge.fail { background: #fee2e2; color: #991b1b; }
.step { border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
.step.fail { border-color: #fca5a5; }
.step-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px;
               background: #f9fafb; font-weight: 500; }
.step.fail .step-header { background: #fff5f5; }
.duration { margin-left: auto; font-size: 12px; color: #94a3b8; font-weight: 400; }
.step-body { padding: 14px; }
.url-bar { display: flex; align-items: center; gap: 10px; background: #f1f5f9;
           border-radius: 6px; padding: 8px 12px; margin-bottom: 12px;
           font-family: monospace; font-size: 13px; }
.url-label { background: #334155; color: white; padding: 2px 8px;
             border-radius: 4px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.url-value { flex: 1; word-break: break-all; color: #1e40af; }
.status-code { padding: 2px 10px; border-radius: 4px; font-weight: 700;
               font-size: 13px; flex-shrink: 0; }
.sc-2 { background: #dcfce7; color: #166534; }
.sc-4 { background: #fef9c3; color: #854d0e; }
.sc-5 { background: #fee2e2; color: #991b1b; }
.sc-0 { background: #f3f4f6; color: #6b7280; }
.method-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px;
                font-weight: 700; color: white; flex-shrink: 0; }
.method-badge.get    { background: #3b82f6; }
.method-badge.post   { background: #22c55e; }
.method-badge.put    { background: #f59e0b; }
.method-badge.delete { background: #ef4444; }
.section-title { font-size: 11px; font-weight: 700; color: #94a3b8;
                 text-transform: uppercase; letter-spacing: .8px; margin: 14px 0 6px; }
.kv-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.kv-table td { padding: 6px 10px; border-bottom: 1px solid #f3f4f6; }
.kv-table td.key { width: 220px; color: #64748b; font-family: monospace; }
.kv-table td.val { font-family: monospace; word-break: break-all; }
/* 断言表格 */
.assert-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.assert-table th { padding: 8px 12px; background: #f8fafc; text-align: left;
                   font-weight: 600; color: #64748b; border-bottom: 2px solid #e2e8f0;
                   font-size: 12px; }
.assert-table td { padding: 9px 12px; border-bottom: 1px solid #f1f5f9;
                   vertical-align: middle; }
.assert-table tr.pass td { background: #f0fdf4; }
.assert-table tr.fail td { background: #fff5f5; }
.assert-icon { text-align: center; font-size: 15px; }
.assert-check code { background: #e2e8f0; padding: 2px 7px; border-radius: 4px;
                     font-size: 12px; color: #1e293b; }
.method-pill { background: #dbeafe; color: #1d4ed8; padding: 2px 8px;
               border-radius: 10px; font-size: 12px; font-weight: 600; }
.assert-expect { color: #166534; font-family: monospace; font-weight: 600; }
.assert-actual { font-family: monospace; color: #1e293b; }
.assert-actual.actual-fail { color: #dc2626; font-weight: 600;
                              background: #fee2e2; padding: 2px 6px; border-radius: 4px; }
.error-block { background: #fff5f5; border: 1px solid #fca5a5; border-radius: 6px;
               padding: 10px 14px; color: #b91c1c; font-size: 13px;
               font-family: monospace; white-space: pre-wrap; margin-top: 12px; }
.code-block { background: #1e293b; color: #e2e8f0; padding: 14px; border-radius: 6px;
              font-size: 12px; overflow-x: auto; white-space: pre-wrap;
              word-break: break-all; margin-top: 4px; line-height: 1.6; }
/* 详情折叠 */
.detail-toggle { margin-top: 12px; cursor: pointer; display: inline-flex;
                 align-items: center; gap: 4px; }
.detail-label { font-size: 12px; color: #64748b; padding: 3px 10px;
                border: 1px solid #e2e8f0; border-radius: 20px;
                background: #f8fafc; transition: background .15s; }
.detail-toggle:hover .detail-label { background: #e2e8f0; color: #334155; }
.detail-body { display: none; margin-top: 8px; }
.detail-body.open { display: block; }
"""

    def _js(self) -> str:
        return """
function toggle(bodyId, arrowId) {
  document.getElementById(bodyId).classList.toggle('open');
  document.getElementById(arrowId).classList.toggle('open');
}
function toggleDetail(id) {
  const el = document.getElementById(id);
  const toggle = el.previousElementSibling.querySelector('.detail-label');
  el.classList.toggle('open');
  toggle.textContent = el.classList.contains('open') ? '▼ 请求详情' : '▶ 查看详情';
}
// 失败用例默认展开
document.querySelectorAll('.case-card.fail').forEach(card => {
  const body = card.querySelector('.case-body');
  const arrow = card.querySelector('.arrow');
  if (body) body.classList.add('open');
  if (arrow) arrow.classList.add('open');
});
"""


# ──────────────────────────────────────────────
# 对外接口
# ──────────────────────────────────────────────

def find_yaml_for_log(log_path: Path) -> Path | None:
    """
    尝试在 testcases 目录下找到与本次运行对应的 yaml 文件。
    httprunner 日志文件名是 UUID，无法直接对应，
    取最近修改的 yaml 文件作为关联（单用例场景适用）。
    多用例场景建议通过 run.py 显式传入 yaml_path。
    """
    yaml_files = sorted(
        TESTCASES_DIR.glob("**/*.yaml"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return yaml_files[0] if yaml_files else None


def generate_report(
    log_files: list = None,
    log_dir: Path = None,
    output_path: Path = None,
    yaml_path: Path = None,
) -> Path:
    """
    生成 HTML 报告

    :param log_files:   本次运行新产生的日志文件列表（优先）
    :param log_dir:     扫描整个目录（log_files 为空时使用）
    :param output_path: 报告输出路径，默认 reports/report_<timestamp>.html
    :param yaml_path:   对应的 yaml 用例文件，用于读取断言配置
    :return: 报告文件路径
    """
    if log_files:
        files = sorted(log_files, key=lambda f: f.stat().st_mtime)
    else:
        log_dir = log_dir or LOGS_DIR
        files = sorted(log_dir.glob("*.run.log"), key=lambda f: f.stat().st_mtime)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_path or REPORTS_DIR / f"report_{timestamp}.html"

    if not files:
        print("⚠️  未找到日志文件")
        return output_path

    # 自动关联 yaml
    if yaml_path is None:
        yaml_path = find_yaml_for_log(files[0])

    parser = LogParser()
    cases = [parser.parse(f, yaml_path) for f in files]

    HtmlReportRenderer().render(cases, output_path)
    return output_path


if __name__ == "__main__":
    import subprocess
    report_path = generate_report()
    subprocess.run(["open", str(report_path)])

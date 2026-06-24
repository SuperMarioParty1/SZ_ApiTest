# SZ_ApiTest 接口自动化测试框架

基于 **Python + HttpRunner v4 + pytest** 构建的接口自动化测试框架，支持三种用例编写模式，统一通过 `run.py` 一键运行并生成自定义 HTML 报告。

---

## 项目结构

```
SZ_ApiTest/
├── testcases/                        # 测试用例（按业务模块分层）
│   ├── conftest.py                   # pytest 全局 fixture 及报告插件
│   ├── theme/                        # 主题模块
│   │   ├── test_vote_list.yaml           # yaml 用例
│   │   ├── test_vote_list_pytest.py      # pytest + requests 用例
│   │   └── test_vote_list_hrun.py        # httprunner 原生 Python 用例
│   └── island/                       # 动画岛模块
│       ├── animation_list.yaml           # yaml 用例（支持参数化多语言）
│       └── animation_list_pytest.py      # pytest + requests 用例
├── hooks/
│   └── debugtalk.py                  # yaml 用例中可调用的自定义函数
├── utils/
│   ├── env_loader.py                 # 环境变量加载工具
│   ├── yaml_loader.py                # yaml 用例加载工具
│   └── report_generator.py          # 自定义 HTML 报告生成器
├── data/
│   └── users.yaml                    # 测试账号数据
├── logs/                             # httprunner 运行日志（自动生成）
├── reports/                          # HTML 测试报告输出目录
├── .env                              # 环境变量配置（不提交 git）
├── pytest.ini                        # pytest 配置
├── run.py                            # 一键运行入口
└── requirements.txt                  # 依赖清单
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

项目根目录创建 `.env` 文件（已在 `.gitignore` 中忽略，不会提交）：

```env
# 各测试环境按端口区分
BASE_URL_2102=http://test.kuso.xyz:2102
BASE_URL_2103=http://test.kuso.xyz:2103
BASE_URL_2105=http://test.kuso.xyz:2105
BASE_URL_2106=http://test.kuso.xyz:2106
BASE_URL_2108=http://test.kuso.xyz:2108

# 公共账号 token
SUPER_TOKEN=your_token_here
```

### 3. 运行用例

```bash
# 运行单个 yaml 用例
python3 run.py --path testcases/theme/test_vote_list.yaml

# 运行单个 pytest 用例
python3 run.py --path testcases/island/animation_list_pytest.py

# 运行整个模块目录
python3 run.py --path testcases/theme

# 运行全部用例
python3 run.py

# CI/Jenkins 环境运行（不自动打开报告）
python3 run.py --path testcases --no-open
```

运行完成后自动生成 HTML 报告并打开浏览器。

---

## 用例编写模式

框架支持三种模式，可按需选择：

### 模式一：yaml 用例（推荐，简洁）

适合标准 CRUD 接口，支持变量、参数化、断言。

```yaml
config:
  name: 主题投票列表接口
  base_url: ${ENV(BASE_URL_2102)}      # 从 .env 读取对应端口的地址
  variables:
    super_token: ${ENV(SUPER_TOKEN)}   # 从 .env 读取 token

teststeps:
  - name: 获取投票列表
    request:
      method: GET
      url: /theme/vote-list
      params:
        tk: $super_token
        lang: zh_CN
    validate:
      - eq: [status_code, 200]
      - eq: [content.status, 0]
      - len_eq: [content.data, 8]
      - eq: ["content.data[0].name", "ACGN"]   # 数组取下标必须加引号
```

**yaml 注意事项：**
- 读取 `.env` 变量用 `${ENV(KEY_NAME)}`
- 引用 `variables` 里的变量用 `$变量名`
- 数组路径取下标必须用 `["content.data[0].name"]` 加引号，否则 yaml 解析报错
- 多语言/多参数场景用 `parameters` 实现参数化，一个 case 跑多轮：

```yaml
config:
  variables:
    lang: zh_CN
  parameters:
    lang: ["zh_CN", "zh-Hant_CN", "en_CN", "ja_CN", "es_CN"]

teststeps:
  - name: 获取列表 - $lang    # step name 可引用参数变量
    request:
      params:
        lang: $lang
```

### 模式二：pytest + requests（灵活，适合复杂逻辑）

适合需要复杂断言、参数化、多步骤依赖的场景。

```python
from utils.env_loader import ENV_CONFIG, get_base_url

BASE_URL = get_base_url(2102)      # 按端口获取 base_url
PARAMS = {
    "tk": ENV_CONFIG["super_token"],
    "lang": "zh_CN",
    ...
}

class TestVoteList:
    def test_status_code(self, vote_list_response, record_request):
        actual = vote_list_response.status_code
        record_request({...})      # 上报数据到自定义报告
        assert actual == 200
```

多语言参数化示例：

```python
LANGUAGES = [("zh_CN", "简体"), ("en_CN", "英语"), ...]

@pytest.fixture(params=LANGUAGES, ids=[lang for lang, _ in LANGUAGES], scope="module")
def lang_response(request):
    lang_code, _ = request.param
    resp = requests.get(f"{BASE_URL}/island/animation-list", params={**PARAMS, "lang": lang_code})
    resp._lang_code = lang_code
    return resp

class TestMultiLang:
    def test_status_code(self, lang_response, record_request):
        assert lang_response.status_code == 200
```

报告中每种语言会独立显示为一个 case（通过 `conftest.py` 自动按 fixture 参数分组）。

### 模式三：httprunner 原生 Python

适合从 yaml 生成后微调，或需要使用 httprunner 内置能力的场景。

```python
from httprunner import HttpRunner, Config, Step, RunRequest

class TestVoteList(HttpRunner):
    config = Config("主题投票列表").base_url("http://...").variables(...)
    teststeps = [Step(RunRequest("获取列表").get("/theme/vote-list")...)]
```

---

## 环境变量与多环境

`.env` 按端口维护多套环境地址，用例中按需指定：

| 端口 | 用途 |
|------|------|
| 2102 | 主环境 |
| 2103 | 环境2 |
| 2105 | 环境3 |
| 2106 | 动画岛环境 |
| 2108 | 环境5 |

**yaml 用例**：在 `config.base_url` 里指定 `${ENV(BASE_URL_2106)}`

**pytest 用例**：在文件顶部用 `get_base_url(2106)` 获取

---

## 自定义函数（debugtalk.py）

`hooks/debugtalk.py` 中定义的函数可在 yaml 用例中通过 `${func()}` 调用：

| 函数 | 说明 |
|------|------|
| `get_timestamp()` | 返回当前秒级时间戳 |
| `get_timestamp_ms()` | 返回毫秒级时间戳 |
| `md5_encrypt(text)` | MD5 加密 |
| `concat_str(*args)` | 字符串拼接 |
| `sleep(seconds)` | 等待指定秒数 |

```yaml
params:
  timestamp: ${get_timestamp()}
```

---

## 报告说明

- **yaml 用例**：运行后解析 httprunner 日志，生成包含断言详情（检查项/期望值/实际值对比）的自定义 HTML 报告
- **pytest 用例**：通过 `conftest.py` 的插件钩子实时收集，运行结束后自动生成相同风格的 HTML 报告
- 报告保存在 `reports/` 目录，文件名格式为 `report_YYYYMMDD_HHMMSS.html`
- 运行完成后自动在浏览器打开最新报告

---

## 新增用例流程

1. 在 `testcases/` 下对应模块目录新建用例文件
2. yaml 用例：参考现有 yaml 编写，`base_url` 指定对应端口的 ENV key
3. pytest 用例：顶部用 `get_base_url(端口号)` 和 `ENV_CONFIG["super_token"]` 读取配置
4. 如需新增自定义函数，在 `hooks/debugtalk.py` 中添加
5. 用 `python3 run.py --path <用例路径>` 验证运行

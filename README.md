# SZ_Project 接口自动化测试框架

基于 **Python + HttpRunner + pytest** 构建，支持 YAML 格式编写接口用例。

编写模式支持
1.支持yaml编写
2.pytest + requests
3.httprunner 原生

## 项目结构

```
SZ_Project/
├── data/                       # 测试数据（yaml 格式）
│   └── users.yaml
├── hooks/                      # httprunner 钩子函数
│   └── debugtalk.py            # 自定义函数，yaml 中通过 ${func()} 调用
├── testcases/                  # 测试用例（按模块分层）
│   ├── conftest.py             # pytest 全局 fixture
│   └── user/
│       ├── login/
│       │   ├── test_login.py           # pytest 驱动层
│       │   ├── test_login_success.yaml # yaml 用例
│       │   └── test_login_fail.yaml
│       └── profile/
│           ├── test_get_profile.yaml
│           └── test_update_profile.yaml
├── utils/                      # 工具函数
│   ├── env_loader.py           # 环境配置加载
│   └── yaml_loader.py          # yaml 用例加载
├── reports/                    # 测试报告输出目录
├── logs/                       # 日志输出目录
├── .env                        # 环境变量配置
├── pytest.ini                  # pytest 配置
└── requirements.txt            # 依赖清单
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写真实的 BASE_URL 等信息
```

### 3. 运行测试

```bash
# 运行全部用例
pytest

# 运行指定模块
pytest testcases/user/login/

# 指定环境运行
ENV=test pytest

# 生成 HTML 报告
pytest --html=reports/report.html --self-contained-html

# 生成 Allure 报告
pytest --alluredir=allure-results
allure serve allure-results
```

---

## YAML 用例规范

```yaml
config:
  name: 用例集名称
  base_url: ${ENV(BASE_URL_DEV)}   # 从环境变量读取
  variables:
    key: value                      # 用例级变量

teststeps:
  - name: 步骤名称
    request:
      method: POST
      url: /api/path
      headers:
        Content-Type: application/json
      json:
        field: $variable            # 引用变量
    extract:
      token: body.data.token        # 提取响应字段到变量
    validate:
      - eq: [status_code, 200]      # 断言状态码
      - eq: [body.code, 0]          # 断言响应体字段
```

### 常用断言类型

| 断言方法 | 说明 |
|---------|------|
| `eq` | 相等 |
| `ne` | 不相等 |
| `gt` | 大于 |
| `lt` | 小于 |
| `contains` | 包含 |
| `len_eq` | 长度等于 |
| `len_gt` | 长度大于 |

### 调用自定义函数（debugtalk.py）

```yaml
# 在 yaml 中调用 hooks/debugtalk.py 中定义的函数
json:
  nickname: 用户_${get_timestamp()}
  sign: ${md5_encrypt($password)}
```

---

## 新增模块流程

1. 在 `testcases/` 下创建对应模块目录，添加 `__init__.py`
2. 编写 `.yaml` 用例文件
3. 创建对应的 `test_xxx.py` 驱动文件，加载并执行 yaml 用例
4. 如需新增自定义函数，在 `hooks/debugtalk.py` 中添加


## 运行命令
# 运行单个用例
python run.py --path testcases/theme/test_vote_list.yaml

# 运行整个目录
python run.py --path testcases/theme


## 编写模式支持
1.支持yaml编写
2.pytest + requests
3.httprunner 原生

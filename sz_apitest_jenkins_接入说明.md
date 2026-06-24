# sz_apitest Jenkins 接入说明

## 1. 文档目的

本文档用于沉淀 `sz_apitest` 接入 Jenkins 的完整方案，包括：

- Jenkins 任务创建方式
- 凭据与环境变量配置
- Pipeline 脚本说明
- 项目执行规则
- 报告产出与查看方式
- 已踩坑与规避建议

适用对象：

- 需要在 Jenkins 上手动触发接口回归的同学
- 需要配置定时任务做自动巡检的同学
- 后续维护该接口自动化框架的同学

---

## 2. 接入目标

当前 Jenkins 接入的目标分为两类：

1. 测试环境回归
   - 定时执行存量接口 case
   - 快速发现接口变更、兼容性问题、联动影响

2. 线上环境巡检
   - 定时执行关键接口 case
   - 提前暴露线上接口不稳定、异常返回、超时等问题

接入后的直接收益：

- 回归任务标准化
- 手动执行与定时执行统一入口
- 报告统一归档和查看
- 降低因人工遗漏导致的问题漏检

---

## 3. Jenkins 任务类型

本项目 Jenkins 任务使用：

- **流水线（Pipeline）**

原因：

- 便于写 Checkout / 安装依赖 / 执行用例 / 归档报告 的完整流程
- 便于参数化执行
- 便于后续扩展定时任务、失败通知、环境切换

---

## 4. 前置条件

Jenkins 节点需要满足以下条件：

### 4.1 基础环境

- 已安装 `git`
- 已安装 `python3`
- 节点具备访问代码仓库权限
- 节点具备访问目标接口环境权限

### 4.2 Jenkins 插件建议

建议安装：

- Git Plugin
- Pipeline
- Credentials Binding Plugin
- HTML Publisher Plugin

其中：

- `Credentials Binding Plugin` 用于安全注入 token / base_url
- `HTML Publisher Plugin` 用于在 Jenkins 页面直接查看 HTML 报告

---

## 5. 代码仓库信息

当前仓库地址：

```text
http://xmyzd.kuso.xyz:911/ykj/sz_apitest.git
```

当前 Pipeline 默认拉取：

- 分支：`master`

---

## 6. Jenkins 凭据配置

### 6.1 Git 凭据

需要新增 Git 仓库访问凭据：

- `sz-apitest-git`

类型：

- `Username with password`

用途：

- Jenkins 拉取代码仓库

### 6.2 公共业务凭据

需要新增：

- `sz-apitest-super-token`

类型：

- `Secret text`

用途：

- 作为接口请求中的业务 token

### 6.3 测试环境 base_url 凭据

需要新增以下凭据：

- `sz-apitest-test-base-url-2102`
- `sz-apitest-test-base-url-2103`
- `sz-apitest-test-base-url-2105`
- `sz-apitest-test-base-url-2106`
- `sz-apitest-test-base-url-2108`

类型：

- `Secret text`

### 6.4 生产环境 base_url 凭据

需要新增以下凭据：

- `sz-apitest-prod-base-url-2102`
- `sz-apitest-prod-base-url-2103`
- `sz-apitest-prod-base-url-2105`
- `sz-apitest-prod-base-url-2106`
- `sz-apitest-prod-base-url-2108`

类型：

- `Secret text`

### 6.5 配置原则

Jenkins 中不直接把 token 和 base_url 写死到脚本里，统一放在 Credentials 中管理。

优点：

- 安全
- 便于环境切换
- 便于统一维护

---

## 7. 当前项目执行规则

项目当前支持三类执行入口：

### 7.1 YAML 用例

例如：

- `testcases/island/animation_list.yaml`
- `testcases/theme/test_vote_list.yaml`

执行方式：

- 通过 `hrun` 执行
- 自动生成 `.run.log`
- 再通过自定义报告生成器生成 HTML 报告

### 7.2 pytest 用例

例如：

- `testcases/island/animation_list_pytest.py`
- `testcases/theme/test_vote_list_pytest.py`

执行方式：

- 通过 `pytest` 执行
- 由 `testcases/conftest.py` 中的插件统一生成 HTML 报告

### 7.3 hrun 原生 Python 用例

例如：

- `testcases/theme/test_vote_list_hrun.py`

执行方式：

- 通过 `pytest` 执行
- 通过 `.run.log` 兜底解析请求、响应和断言信息
- 报告中可展示 URL、响应体、断言结果

---

## 8. 当前测试路径规则

项目统一通过 `run.py` 执行：

### 8.1 单个 YAML

```bash
python3 run.py --path testcases/theme/test_vote_list.yaml --no-open
```

### 8.2 单个 pytest

```bash
python3 run.py --path testcases/theme/test_vote_list_pytest.py --no-open
```

### 8.3 单个 hrun Python 用例

```bash
python3 run.py --path testcases/theme/test_vote_list_hrun.py --no-open
```

### 8.4 执行整个目录

```bash
python3 run.py --path testcases/theme --no-open
```

### 8.5 执行全量

```bash
python3 run.py --path testcases --no-open
```

### 8.6 `--no-open` 的作用

Jenkins 上必须使用 `--no-open`，否则执行结束后脚本会尝试调用本地 `open` 打开报告页面，CI 环境下会报错或行为异常。

---

## 9. 当前目录模式执行逻辑

当 `run.py --path` 指向目录时，执行逻辑如下：

1. 先扫描目录下所有 `.yaml`
2. 逐个执行 YAML 用例
3. 解析每次 YAML 产生的 `.run.log`
4. 再执行该目录下的 `*_pytest.py` 和 `*_hrun.py`
5. 最终合并 YAML 与 pytest/hrun 的结果，生成一份总报告

这样可以保证：

- YAML case 不丢
- pytest case 不丢
- hrun 原生 Python case 也能在报告里展示详情

---

## 10. pytest 收集规则

当前 `pytest.ini` 中的收集规则为：

```ini
python_files = *_pytest.py *_hrun.py
```

说明：

- Jenkins 不直接依赖 `*_test.py` 这类 YAML 临时生成文件做常规收集
- 目录模式下的 YAML 用例由 `run.py` 主动触发执行

这样做的好处：

- 避免 `*_test.py` 临时缓存文件引起重复执行
- 避免 Jenkins 因缓存文件残留导致执行结果混乱

---

## 11. 自动生成文件处理策略

YAML 用例执行时，HttpRunner 会自动生成 `*_test.py` 文件，例如：

- `test_vote_list.yaml` -> `test_vote_list_test.py`

当前处理策略：

1. 执行前先删除旧缓存
2. 执行过程中允许临时生成
3. 执行结束后自动清理临时生成文件

这样可以避免：

- 仓库目录被临时文件污染
- Jenkins workspace 中残留历史缓存
- pytest 下次误收集这些临时文件

---

## 12. 报告生成规则

### 12.1 报告目录

统一输出到：

```text
reports/
```

### 12.2 主要文件

- `report_YYYYMMDD_HHMMSS.html`：本次生成的时间戳报告
- `report_latest.html`：最新报告
- `report.css`：报告样式文件

### 12.3 报告内容来源

#### YAML 用例

- 通过 `.run.log` 解析请求、响应、断言结果

#### pytest 用例

- 通过 `record_request` fixture 和 `conftest.py` 自定义插件记录请求信息

#### hrun Python 用例

- 如果 pytest 插件拿不到步骤详情，则回退解析 `.run.log`

---

## 13. Jenkins 中报告查看方式

当前 Jenkins 配置支持两种查看方式：

1. 构建描述中的“查看测试报告”链接
2. HTML Publisher 发布的页面

Pipeline 中已包含：

- `archiveArtifacts`
- `publishHTML`

这样可以在 Jenkins 页面直接打开报告，而不需要手动去服务器目录找文件。

---

## 14. 敏感信息处理

报告中对以下敏感字段已做脱敏：

- `tk`
- `token`
- `super_token`
- `authorization`
- `access_token`
- `refresh_token`

这样可以避免 Jenkins HTML 报告中泄露业务凭据。

---

## 15. 当前 Jenkins Pipeline 参数说明

### 15.1 RUN_ENV

可选值：

- `test`
- `prod`

作用：

- 切换使用测试环境或生产环境的 base_url 凭据

### 15.2 RUN_TYPE

可选值：

- `all`
- `module`
- `file`

当前脚本行为：

- `all`：执行 `testcases`
- `module` / `file`：都通过 `CASE_PATH` 指定路径执行

### 15.3 CASE_PATH

示例：

- `testcases`
- `testcases/theme`
- `testcases/island/animation_list.yaml`
- `testcases/theme/test_vote_list_pytest.py`
- `testcases/theme/test_vote_list_hrun.py`

注意：

- 不建议手工填写 `*_test.py`
- `*_test.py` 属于 YAML 执行时的临时生成文件，不应作为 Jenkins 手工执行入口

---

## 16. 当前 Jenkinsfile 设计说明

### 16.1 Checkout

- 从 Git 仓库拉取 `master`
- 使用 `sz-apitest-git` 凭据

### 16.2 Install Dependencies

使用策略：

- 首次构建创建 `.venv`
- 使用清华镜像源安装依赖
- 对 `requirements.txt` 做 SHA1 校验
- 如果依赖未变化，则跳过安装

优点：

- 提升构建速度
- 避免每次全量重装依赖

### 16.3 Run API Cases

通过 `withCredentials` 注入：

- `SUPER_TOKEN`
- 当前环境对应的各组 `BASE_URL_210x`

然后执行：

```bash
python3 run.py --path xxx --no-open
```

### 16.4 Post Actions

- 归档 `reports/**/*`
- 归档 `logs/**/*`
- 发布 HTML 报告
- 失败时输出统一提示

---

## 17. 当前 Jenkinsfile（基线版本）

> 以下为当前基线 Pipeline，可直接作为后续维护参考。

```groovy
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
    }

    parameters {
        choice(name: 'RUN_ENV', choices: ['test', 'prod'], description: '运行环境，当前默认先使用 test')
        choice(name: 'RUN_TYPE', choices: ['all', 'module', 'file'], description: '执行方式')
        string(
            name: 'CASE_PATH',
            defaultValue: 'testcases',
            description: '模块目录或文件路径，例如 testcases/theme 或 testcases/island/animation_list_pytest.py'
        )
    }

    environment {
        PYTHONUNBUFFERED = '1'
        GIT_URL = 'http://xmyzd.kuso.xyz:911/ykj/sz_apitest.git'
        GIT_BRANCH = 'master'
        PIP_INDEX_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: "${GIT_BRANCH}",
                    credentialsId: 'sz-apitest-git',
                    url: "${GIT_URL}"
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    if [ ! -d ".venv" ]; then
                        python3 -m venv .venv
                        . .venv/bin/activate
                        python3 -m pip install --upgrade pip \
                          -i "${PIP_INDEX_URL}" \
                          --timeout 120 --retries 5
                    else
                        . .venv/bin/activate
                    fi

                    CURRENT_SHA=$(shasum requirements.txt | awk '{print $1}')

                    if [ ! -f ".venv/.requirements.sha1" ]; then
                        pip install -r requirements.txt \
                          -i "${PIP_INDEX_URL}" \
                          --timeout 120 --retries 5
                        echo "$CURRENT_SHA" > .venv/.requirements.sha1
                    else
                        INSTALLED_SHA=$(cat .venv/.requirements.sha1)

                        if [ "$CURRENT_SHA" != "$INSTALLED_SHA" ]; then
                            pip install -r requirements.txt \
                              -i "${PIP_INDEX_URL}" \
                              --timeout 120 --retries 5
                            echo "$CURRENT_SHA" > .venv/.requirements.sha1
                        else
                            echo "requirements.txt 未变化，跳过依赖安装"
                        fi
                    fi
                '''
            }
        }

        stage('Run API Cases') {
            steps {
                script {
                    def commonCreds = [
                        string(credentialsId: 'sz-apitest-super-token', variable: 'SUPER_TOKEN')
                    ]

                    def envCreds
                    if (params.RUN_ENV == 'prod') {
                        envCreds = [
                            string(credentialsId: 'sz-apitest-prod-base-url-2102', variable: 'BASE_URL_2102'),
                            string(credentialsId: 'sz-apitest-prod-base-url-2103', variable: 'BASE_URL_2103'),
                            string(credentialsId: 'sz-apitest-prod-base-url-2105', variable: 'BASE_URL_2105'),
                            string(credentialsId: 'sz-apitest-prod-base-url-2106', variable: 'BASE_URL_2106'),
                            string(credentialsId: 'sz-apitest-prod-base-url-2108', variable: 'BASE_URL_2108')
                        ]
                    } else {
                        envCreds = [
                            string(credentialsId: 'sz-apitest-test-base-url-2102', variable: 'BASE_URL_2102'),
                            string(credentialsId: 'sz-apitest-test-base-url-2103', variable: 'BASE_URL_2103'),
                            string(credentialsId: 'sz-apitest-test-base-url-2105', variable: 'BASE_URL_2105'),
                            string(credentialsId: 'sz-apitest-test-base-url-2106', variable: 'BASE_URL_2106'),
                            string(credentialsId: 'sz-apitest-test-base-url-2108', variable: 'BASE_URL_2108')
                        ]
                    }

                    withCredentials(commonCreds + envCreds) {
                        sh '''
                            . .venv/bin/activate

                            if [ "$RUN_TYPE" = "all" ]; then
                                python3 run.py --path testcases --no-open
                            else
                                python3 run.py --path "$CASE_PATH" --no-open
                            fi
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**/*, logs/**/*', allowEmptyArchive: true

            script {
                if (fileExists('reports/report_latest.html')) {
                    currentBuild.description = "<a href='${env.BUILD_URL}artifact/reports/report_latest.html' target='_blank'>查看测试报告</a>"

                    try {
                        publishHTML(target: [
                            allowMissing: true,
                            alwaysLinkToLastBuild: true,
                            includes: 'report.css',
                            keepAll: true,
                            reportDir: 'reports',
                            reportFiles: 'report_latest.html',
                            reportName: '接口自动化测试报告'
                        ])
                    } catch (Exception err) {
                        echo "HTML Publisher 插件不可用，已保留归档报告链接。"
                    }
                }
            }
        }

        failure {
            echo '接口自动化任务执行失败，请检查控制台日志和测试报告。'
        }
    }
}
```

---

## 18. 已踩坑记录

### 18.1 Git 仓库拉取失败

现象：

- Jenkins 报 `repository not found`
- 或 `CredentialId could not be found`

原因：

- Git 仓库地址错误
- Git 凭据 ID 错误
- Jenkins 任务使用的凭据域不正确

处理方式：

- 确认仓库地址为：
  `http://xmyzd.kuso.xyz:911/ykj/sz_apitest.git`
- 确认 Jenkins 中存在 `sz-apitest-git`

### 18.2 Python 3.9 类型标注兼容问题

现象：

- `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`

原因：

- Jenkins 节点 Python 版本为 3.9
- 使用了 `Path | None` 这类 3.10 风格类型标注
- 但文件顶部没有 `from __future__ import annotations`

处理方式：

- 相关文件统一补上 `from __future__ import annotations`

### 18.3 Jenkins 中打开报告报错

现象：

- 运行结束尝试自动打开本地报告
- Jenkins 环境下失败

处理方式：

- 所有 Jenkins 执行统一带 `--no-open`

### 18.4 报告样式在 Jenkins 中异常

现象：

- 本地 HTML 正常
- Jenkins 打开样式错乱

处理方式：

- 报告样式独立成 `report.css`
- Pipeline 中通过 `publishHTML` 一起发布

### 18.5 `*_test.py` 导致重复执行或结果混乱

现象：

- Jenkins 收集到 YAML 临时生成文件
- 执行结果重复、混乱

处理方式：

- pytest 常规收集不依赖 `*_test.py`
- YAML 由 `run.py` 目录模式主动执行
- 临时生成文件执行后清理

### 18.6 requests 用例偶发网络抖动

现象：

- `RemoteDisconnected`
- `ConnectionError`
- `ConnectTimeout`

处理方式：

- 已在 `utils/http_client.py` 中加入统一重试和超时

---

## 19. 手工执行建议

### 19.1 执行全量回归

- `RUN_ENV = test`
- `RUN_TYPE = all`
- `CASE_PATH = testcases`

### 19.2 执行某个模块

例如：

- `RUN_ENV = test`
- `RUN_TYPE = module`
- `CASE_PATH = testcases/theme`

### 19.3 执行单个文件

推荐填写以下真实源文件：

- `testcases/theme/test_vote_list.yaml`
- `testcases/theme/test_vote_list_pytest.py`
- `testcases/theme/test_vote_list_hrun.py`
- `testcases/island/animation_list.yaml`
- `testcases/island/animation_list_pytest.py`

不建议填写：

- `testcases/**/**_test.py`

原因：

- 这些文件属于 YAML 执行期缓存，不是稳定入口

---

## 20. 定时任务建议

建议拆分为两类任务：

### 20.1 测试环境回归任务

- 每日定时执行
- `RUN_ENV = test`
- `RUN_TYPE = all`

### 20.2 生产环境巡检任务

- 每日定时执行关键接口
- `RUN_ENV = prod`
- `RUN_TYPE = module` 或 `file`

示例 cron：

```text
H 8 * * *
```

说明：

- 由 Jenkins 自动分散分钟数
- 避免多个任务同一时刻启动

---

## 21. 后续优化建议

1. 对 Jenkins 参数做目录/文件下拉联动
   - 提升手工选择 case 的体验

2. 增加失败通知
   - 如企业微信 / 飞书 / 邮件

3. 增加 Allure 或趋势统计
   - 补充历史趋势视角

4. 对生产环境与测试环境拆分独立任务
   - 降低误操作风险

5. 对关键接口增加 smoke 专用任务
   - 提升日常巡检效率

---

## 22. 结论

当前 `sz_apitest` 已具备较完整的 Jenkins 接入能力：

- 支持手动触发
- 支持定时执行
- 支持环境切换
- 支持 YAML / pytest / hrun 三类用例统一纳管
- 支持 HTML 报告归档与在线查看
- 兼顾了依赖增量安装、敏感信息脱敏、Python 3.9 兼容性、临时文件清理等落地问题

后续在此基础上继续扩展通知、趋势和参数交互即可。

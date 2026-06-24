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

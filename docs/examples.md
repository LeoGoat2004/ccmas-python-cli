# 使用示例

本文档提供 CCMAS 的实际使用示例，涵盖从基础到高级的各种场景。

## 目录

1. [基础示例](#基础示例)
2. [文件操作](#文件操作)
3. [代码开发](#代码开发)
4. [项目管理](#项目管理)
5. [多 Agent 协作](#多-agent-协作)
6. [高级用法](#高级用法)

## 基础示例

### 启动交互模式

```bash
# 进入交互式对话
ccmas

# 使用特定模型
ccmas --model gpt-3.5-turbo

# 使用 Ollama 本地模型
ccmas --ollama --model llama2
```

### 执行单任务

```bash
# 简单问答
ccmas "解释什么是递归函数"

# 保存输出
ccmas "列出 Python 的 10 个最佳实践" -o best_practices.txt

# 使用不同温度设置
ccmas "写一个创意故事开头" --temperature 1.0
```

### 代码解释

```bash
# 解释代码文件
ccmas "解释 src/main.py 中的核心逻辑"

# 解释特定函数
ccmas "解释 quicksort 函数的工作原理" < algorithms.py
```

## 文件操作

### 读取和分析文件

```bash
# 分析配置文件
ccmas "分析 config.yaml 的结构和用途" < config.yaml

# 检查日志文件
ccmas "总结这些错误日志的主要问题" < error.log

# 比较文件
ccmas "比较这两个文件的差异" < <(diff file1.txt file2.txt)
```

### 生成文件

```bash
# 生成 Python 脚本
ccmas "创建一个计算斐波那契数列的 Python 脚本" -o fibonacci.py

# 生成配置文件
ccmas "为 Flask 应用生成生产环境配置" -o config.py

# 生成文档
ccmas "为这个项目生成 README 文档" -o README.md
```

### 批量处理

```bash
# 批量分析代码文件
for file in src/*.py; do
    echo "=== Analyzing $file ==="
    ccmas "分析这段代码的质量" < "$file" >> code_analysis.txt
done

# 批量生成文档
for file in src/*.py; do
    base=$(basename "$file" .py)
    ccmas "为 $file 生成文档字符串" < "$file" > "docs/${base}.md"
done
```

## 代码开发

### 代码生成

```bash
# 生成函数实现
ccmas "实现一个 LRU 缓存类，包含 get 和 put 方法" -o lru_cache.py

# 生成单元测试
ccmas "为 utils.py 中的所有函数生成单元测试" -o test_utils.py

# 生成 API 端点
ccmas "创建一个 REST API 端点处理用户注册" -o user_api.py
```

### 代码审查

```bash
# 审查代码文件
ccmas --agent code-reviewer "审查 src/auth.py"

# 检查安全问题
ccmas "检查这段代码的安全漏洞" < auth.py

# 性能分析
ccmas "分析这段代码的性能瓶颈" < data_processing.py
```

### 代码重构

```bash
# 重构建议
ccmas "为这段代码提供重构建议" < legacy_code.py

# 自动重构（使用 acceptEdits 模式）
ccmas --permission-mode acceptEdits "重构这个类使用依赖注入" < service.py

# 现代化代码
ccmas "将这个 Python 2 代码转换为 Python 3" < old_script.py -o modern_script.py
```

### 调试辅助

```bash
# 分析错误
ccmas "解释这个错误并提供解决方案" < error_traceback.txt

# 修复 bug
ccmas "找出并修复这段代码中的 bug" < buggy_code.py

# 优化算法
ccmas "优化这个函数的时间复杂度" < slow_function.py
```

## 项目管理

### 项目初始化

```bash
# 创建项目结构
ccmas "为 Python Web 应用生成项目结构" -o setup_project.sh

# 生成依赖文件
ccmas "根据这些导入语句生成 requirements.txt" < imports.txt -o requirements.txt

# 创建 Makefile
ccmas "为这个项目生成 Makefile" -o Makefile
```

### 版本控制

```bash
# 生成提交信息
git diff --cached | ccmas "根据这些更改生成提交信息"

# 代码审查（PR 描述）
git diff main...feature | ccmas "生成 Pull Request 描述"

# 发布说明
git log --oneline v1.0.0..v1.1.0 | ccmas "生成 v1.1.0 的发布说明" -o RELEASE_NOTES.md
```

### 文档生成

```bash
# 生成 API 文档
ccmas "为 src/api.py 生成 API 文档" -o API.md

# 生成使用指南
ccmas "根据代码生成用户使用指南" < main.py -o USER_GUIDE.md

# 更新 CHANGELOG
ccmas "根据最近的提交更新 CHANGELOG" < commits.txt >> CHANGELOG.md
```

## 多 Agent 协作

### 使用专业 Agent

```bash
# 使用探索 Agent 了解项目
ccmas --agent explorer "了解这个项目的架构"

# 使用代码审查 Agent
ccmas --agent code-reviewer "审查最近的更改"

# 使用测试 Agent
ccmas --agent test-runner "运行测试并修复失败的测试"
```

### Agent 链式调用

```bash
# 第一步：探索项目
ccmas --agent explorer "列出项目的主要模块" > modules.txt

# 第二步：分析每个模块
for module in $(cat modules.txt); do
    ccmas --agent code-reviewer "审查 $module 模块" >> review_report.txt
done

# 第三步：生成总结
ccmas "根据这些审查报告生成总结" < review_report.txt
```

### Fork 子 Agent

```python
# 在 Python 代码中使用 Fork 子 Agent
from ccmas.agent.run_agent import run_agent
from ccmas.agent.definition import GENERAL_PURPOSE_AGENT
from ccmas.llm.client import OpenAIClient

client = OpenAIClient(model="gpt-4")

# 创建子 Agent 处理特定任务
result = await run_agent(
    agent=GENERAL_PURPOSE_AGENT,
    messages=[UserMessage(content="分析这个日志文件")],
    llm_client=client,
)
```

## 高级用法

### 管道和重定向

```bash
# 组合多个命令
cat data.json | ccmas "将这些数据转换为 CSV 格式" | tee output.csv

# 使用进程替换
ccmas "比较这两个文件" <(cat file1.txt) <(cat file2.txt)

# 过滤和转换
grep "ERROR" app.log | ccmas "分类这些错误" | sort | uniq -c
```

### 自动化脚本

```bash
#!/bin/bash
# daily_report.sh - 生成每日报告

# 获取昨天的提交
git log --since="yesterday" --pretty=format:"%h %s" > /tmp/commits.txt

# 生成报告
ccmas --permission-mode bypassPermissions "根据这些提交生成日报" < /tmp/commits.txt > daily_report.md

# 发送报告（假设有邮件工具）
mail -s "Daily Report" team@example.com < daily_report.md
```

### 交互式工作流

```bash
# 创建交互式菜单脚本
#!/bin/bash
# ccmas_helper.sh

echo "CCMAS 助手"
echo "1. 解释代码"
echo "2. 生成测试"
echo "3. 优化代码"
echo "4. 退出"

read -p "选择操作: " choice

case $choice in
    1)
        read -p "输入文件路径: " filepath
        ccmas "解释 $filepath 的代码" < "$filepath"
        ;;
    2)
        read -p "输入文件路径: " filepath
        ccmas "为 $filepath 生成单元测试" < "$filepath" > "test_$(basename $filepath)"
        ;;
    3)
        read -p "输入文件路径: " filepath
        ccmas --permission-mode acceptEdits "优化 $filepath 的代码" < "$filepath" > "$filepath.optimized"
        ;;
    4)
        exit 0
        ;;
esac
```

### CI/CD 集成

```yaml
# .github/workflows/ccmas-review.yml
name: AI Code Review

on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run CCMAS Review
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          pip install ccmas
          git diff origin/main | ccmas --permission-mode bypassPermissions "审查这些更改" > review_comment.md
          # 发布评论（需要额外脚本）
```

### 数据处理

```bash
# JSON 处理
cat data.json | ccmas "提取所有用户的邮箱地址" | jq '.'

# CSV 处理
cat data.csv | ccmas "分析这些销售数据并生成摘要" > sales_summary.txt

# 日志分析
cat access.log | ccmas "找出最频繁的访问 IP 和页面" > access_analysis.txt
```

### 学习辅助

```bash
# 解释概念
ccmas "用简单的语言解释区块链技术"

# 学习路径
ccmas "制定一个 3 个月的 Python 学习计划"

# 代码对比学习
ccmas "比较 Python 和 JavaScript 的异步编程模型"

# 面试准备
ccmas "生成 10 个 Python 高级面试问题及答案" > interview_prep.md
```

## 实际项目示例

### Web 应用开发

```bash
# 1. 创建项目结构
ccmas "创建一个 FastAPI 项目结构，包含认证、数据库和 API 模块" -o create_project.sh
bash create_project.sh

# 2. 生成模型
cd myproject
ccmas "为用户、文章和评论生成 SQLAlchemy 模型" -o models.py

# 3. 生成 API 端点
ccmas "为 User 模型生成 CRUD API 端点" -o user_routes.py

# 4. 生成测试
ccmas "为 user_routes.py 生成 pytest 测试" -o test_users.py

# 5. 生成文档
ccmas "根据代码生成 API 文档" -o API_DOCUMENTATION.md
```

### 数据分析项目

```bash
# 1. 数据清洗脚本
ccmas "创建一个清洗 CSV 数据的 Python 脚本" -o clean_data.py

# 2. 分析脚本
ccmas "创建一个分析销售趋势的脚本，包含可视化" -o analyze_sales.py

# 3. 报告生成
ccmas "创建一个从分析结果生成 HTML 报告的脚本" -o generate_report.py

# 4. 自动化工作流
cat > run_analysis.sh << 'EOF'
#!/bin/bash
python clean_data.py
python analyze_sales.py
python generate_report.py
echo "分析完成！"
EOF
chmod +x run_analysis.sh
```

## 最佳实践总结

1. **明确任务描述**：提供具体、清晰的指令
2. **使用合适的模型**：根据任务复杂度选择模型
3. **合理设置参数**：温度、最大 token 等
4. **保存常用配置**：使用配置文件提高效率
5. **版本控制输出**：重要的生成内容应纳入版本控制
6. **审查生成内容**：AI 生成的代码需要人工审查
7. **组合工具使用**：将 CCMAS 与其他 CLI 工具结合

## 故障排除示例

### 处理大文件

```bash
# 文件太大，分段处理
head -n 100 large_file.py | ccmas "分析前 100 行"
tail -n 100 large_file.py | ccmas "分析后 100 行"
```

### 处理超时

```bash
# 增加超时时间
ccmas "分析整个代码库" --timeout 600

# 分批处理
find src -name "*.py" -exec ccmas "分析 {}" {} \;
```

### 处理复杂任务

```bash
# 分解复杂任务
ccmas "第一步：分析需求" < requirements.txt > step1.md
ccmas "第二步：设计架构" < step1.md > step2.md
ccmas "第三步：实现核心功能" < step2.md > step3.md
```

# 使用指南

本指南介绍 CCMAS 的基本用法和 CLI 命令。

## 命令行界面

CCMAS 提供直观的命令行界面，支持交互模式和单任务模式。

### 基本语法

```bash
ccmas [OPTIONS] [TASK]
```

- `TASK`: 可选的任务描述。如果提供，CCMAS 将执行该任务并退出；如果不提供，将进入交互模式。

### 常用选项

| 选项 | 简写 | 说明 | 示例 |
|------|------|------|------|
| `--model` | `-m` | 指定模型 | `--model gpt-4` |
| `--api-base` | `-b` | 自定义 API 基础 URL | `--api-base http://localhost:8000/v1` |
| `--ollama` | - | 使用 Ollama 后端 | `--ollama` |
| `--vllm` | - | 使用 vLLM 后端 | `--vllm` |
| `--temperature` | `-t` | 设置采样温度 (0-2) | `--temperature 0.5` |
| `--max-tokens` | - | 最大生成 token 数 | `--max-tokens 2048` |
| `--permission-mode` | `-p` | 权限模式 | `--permission-mode auto` |
| `--config` | `-c` | 指定配置文件 | `--config ./my-config.json` |
| `--save-config` | - | 保存当前配置 | `--save-config` |
| `--no-color` | - | 禁用彩色输出 | `--no-color` |
| `--verbose` | `-v` | 启用详细输出 | `--verbose` |
| `--version` | - | 显示版本信息 | `--version` |
| `--output` | `-o` | 输出文件路径 | `--output result.txt` |

## 使用模式

### 交互模式

启动交互式对话：

```bash
ccmas
```

交互模式特性：
- 多轮对话支持
- 历史记录保存
- 实时流式输出
- 工具调用可视化
- Token 使用统计

常用交互命令：
```
/help      - 显示帮助信息
/clear     - 清除对话历史
/config    - 显示当前配置
/exit      - 退出程序
```

### 单任务模式

执行单个任务并退出：

```bash
# 基本用法
ccmas "解释量子计算的基本原理"

# 保存输出到文件
ccmas "生成一个 Python 快速排序实现" -o quicksort.py

# 使用特定模型
ccmas "分析这段代码" --model gpt-4 -o analysis.txt
```

## 后端选择

### OpenAI（默认）

```bash
# 使用默认模型 (gpt-4)
ccmas "任务描述"

# 指定模型
ccmas "任务描述" --model gpt-3.5-turbo

# 自定义 API 基础 URL（用于代理或兼容服务）
ccmas "任务描述" --api-base https://api.example.com/v1
```

### Ollama

```bash
# 使用 Ollama 后端
ccmas "任务描述" --ollama

# 指定 Ollama 模型
ccmas "任务描述" --ollama --model llama2

# 自定义 Ollama 服务器地址
ccmas "任务描述" --ollama --api-base http://localhost:11434
```

### vLLM

```bash
# 使用 vLLM 后端
ccmas "任务描述" --vllm

# 指定模型
ccmas "任务描述" --vllm --model meta-llama/Llama-2-7b-chat-hf

# 自定义 vLLM 服务器地址
ccmas "任务描述" --vllm --api-base http://localhost:8000/v1
```

## 权限模式

CCMAS 支持多种权限模式来控制 Agent 的行为：

| 模式 | 说明 | 使用场景 |
|------|------|----------|
| `default` | 默认模式，每次操作前询问 | 安全敏感环境 |
| `acceptEdits` | 自动接受编辑操作 | 开发环境 |
| `bypassPermissions` | 绕过所有权限检查 | 自动化脚本 |
| `plan` | 计划模式，先制定计划再执行 | 复杂任务 |
| `auto` | 自动模式，智能判断 | 日常使用 |
| `bubble` | 向上级 Agent 请求权限 | 多 Agent 环境 |

使用示例：
```bash
# 自动接受编辑
ccmas "修改配置文件" --permission-mode acceptEdits

# 计划模式
ccmas "重构整个项目" --permission-mode plan

# 自动化脚本
ccmas "批量处理文件" --permission-mode bypassPermissions
```

## 配置管理

### 查看当前配置

```bash
ccmas --verbose --config
```

### 保存配置

```bash
# 保存当前设置到默认配置文件
ccmas --model gpt-4 --temperature 0.5 --save-config

# 保存到指定文件
ccmas --model gpt-4 --save-config --config ./my-config.json
```

### 使用自定义配置

```bash
ccmas --config ./project-config.json "任务描述"
```

## 高级用法

### 管道输入

```bash
# 从文件读取输入
cat code.py | ccmas "审查这段代码"

# 从其他命令获取输入
git diff | ccmas "总结这些更改"
```

### 批量处理

```bash
# 处理多个文件
for file in *.py; do
    ccmas "分析 $file" --output "analysis_$file.txt"
done
```

### 结合其他工具

```bash
# 与 grep 结合
grep -r "TODO" . | ccmas "整理这些待办事项"

# 与 git 结合
git log --oneline -10 | ccmas "生成发布说明"
```

## Agent 使用

### 使用内置 Agent

```bash
# 使用代码审查 Agent
ccmas --agent code-reviewer "审查 src/main.py"

# 使用探索 Agent
ccmas --agent explorer "了解项目结构"

# 使用测试运行 Agent
ccmas --agent test-runner "运行所有测试"
```

### 创建自定义 Agent

```bash
# 使用自定义 Agent 定义文件
ccmas --agent ./my-agent.json "执行任务"
```

## 输出控制

### 重定向输出

```bash
# 保存到文件
ccmas "生成报告" > report.txt

# 追加到文件
ccmas "添加内容" >> report.txt

# 使用 --output 选项（保留格式化）
ccmas "生成代码" --output code.py
```

### 控制输出格式

```bash
# 禁用彩色输出（用于脚本）
ccmas "任务" --no-color

# 详细输出（调试）
ccmas "任务" --verbose

# 仅输出结果（无提示信息）
ccmas "任务" 2>/dev/null
```

## 故障排除

### 调试模式

```bash
# 启用详细日志
ccmas "任务" --verbose

# 查看 API 调用
CCMAS_DEBUG=1 ccmas "任务"
```

### 常见错误

**连接超时**：
```bash
# 增加超时时间
ccmas "任务" --timeout 600
```

**Token 限制**：
```bash
# 增加最大 token 数
ccmas "任务" --max-tokens 4096
```

**速率限制**：
```bash
# 降低温度以减少生成长度
ccmas "任务" --temperature 0.3 --max-tokens 1024
```

## 最佳实践

1. **明确任务描述**：提供清晰、具体的任务描述
2. **使用合适的模型**：简单任务用轻量级模型，复杂任务用强模型
3. **合理设置温度**：创造性任务用高温度 (0.8-1.0)，精确任务用低温度 (0.0-0.3)
4. **保存常用配置**：将常用设置保存到配置文件
5. **使用权限模式**：根据环境选择合适的权限模式
6. **版本控制配置**：将项目级配置纳入版本控制

## 下一步

- 阅读 [配置说明](configuration.md) 了解详细配置选项
- 查看 [架构概览](architecture.md) 理解系统工作原理
- 参考 [示例代码](examples.md) 学习实际应用

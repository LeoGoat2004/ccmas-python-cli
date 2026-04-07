# 配置说明

本文档详细介绍 CCMAS 的配置系统，包括配置文件结构、环境变量和配置优先级。

## 配置系统概述

CCMAS 使用分层配置系统，配置来源按优先级从高到低排列：

1. **命令行参数** - 最高优先级
2. **环境变量**
3. **项目级配置文件** (`.ccmas/config.json`)
4. **用户级配置文件** (`~/.ccmas/config.json`)
5. **默认值** - 最低优先级

## 配置选项详解

### 模型设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | string | `"gpt-4"` | 默认使用的模型 |
| `temperature` | float | `0.7` | 采样温度 (0.0 - 2.0) |
| `max_tokens` | integer | `null` | 最大生成 token 数 |

```json
{
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**温度设置建议**：
- `0.0 - 0.3`: 代码生成、精确回答
- `0.4 - 0.7`: 一般对话、平衡输出
- `0.8 - 1.0`: 创意写作、头脑风暴
- `1.1 - 2.0`: 探索性任务、多样化输出

### API 设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_base` | string | `null` | 自定义 API 基础 URL |
| `api_key` | string | `null` | API 认证密钥 |

```json
{
  "api_base": "https://api.example.com/v1",
  "api_key": "sk-..."
}
```

**安全提示**：不要在配置文件中硬编码 API 密钥，建议使用环境变量。

### 后端设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `backend` | string | `"openai"` | 后端类型 |
| `ollama_base_url` | string | `"http://localhost:11434"` | Ollama 服务器地址 |
| `vllm_base_url` | string | `"http://localhost:8000"` | vLLM 服务器地址 |

```json
{
  "backend": "ollama",
  "ollama_base_url": "http://localhost:11434"
}
```

支持的后端：
- `openai`: OpenAI API 或兼容服务
- `ollama`: Ollama 本地部署
- `vllm`: vLLM 高性能推理服务

### 权限设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `permission_mode` | string | `"default"` | 权限模式 |

```json
{
  "permission_mode": "acceptEdits"
}
```

权限模式选项：
- `default`: 每次操作前询问确认
- `acceptEdits`: 自动接受文件编辑操作
- `bypassPermissions`: 绕过所有权限检查（谨慎使用）
- `plan`: 计划模式，先制定计划再执行
- `auto`: 自动模式，智能判断是否需要确认
- `bubble`: 向上级 Agent 请求权限（多 Agent 环境）

### UI 设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `show_token_usage` | boolean | `true` | 显示 token 使用统计 |
| `show_timing` | boolean | `true` | 显示执行时间 |
| `color_output` | boolean | `true` | 启用彩色输出 |

```json
{
  "show_token_usage": true,
  "show_timing": true,
  "color_output": true
}
```

### 历史记录设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `save_history` | boolean | `true` | 保存对话历史 |
| `history_file` | string | `null` | 历史记录文件路径 |
| `max_history_size` | integer | `1000` | 最大历史记录条目数 |

```json
{
  "save_history": true,
  "history_file": "~/.ccmas/history.json",
  "max_history_size": 1000
}
```

### 高级设置

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | integer | `300` | 请求超时时间（秒） |
| `retry_attempts` | integer | `3` | 失败重试次数 |
| `verbose` | boolean | `false` | 详细输出模式 |

```json
{
  "timeout": 300,
  "retry_attempts": 3,
  "verbose": false
}
```

## 配置文件示例

### 完整配置文件

```json
{
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 2048,
  "api_base": null,
  "api_key": null,
  "backend": "openai",
  "ollama_base_url": "http://localhost:11434",
  "vllm_base_url": "http://localhost:8000",
  "permission_mode": "default",
  "show_token_usage": true,
  "show_timing": true,
  "color_output": true,
  "save_history": true,
  "history_file": null,
  "max_history_size": 1000,
  "timeout": 300,
  "retry_attempts": 3,
  "verbose": false
}
```

### 开发环境配置

```json
{
  "model": "gpt-3.5-turbo",
  "temperature": 0.3,
  "permission_mode": "acceptEdits",
  "show_token_usage": true,
  "show_timing": true,
  "color_output": true,
  "verbose": true
}
```

### 生产环境配置

```json
{
  "model": "gpt-4",
  "temperature": 0.2,
  "max_tokens": 4096,
  "permission_mode": "default",
  "show_token_usage": false,
  "color_output": false,
  "save_history": false,
  "timeout": 600,
  "retry_attempts": 5
}
```

### Ollama 本地配置

```json
{
  "model": "llama2",
  "backend": "ollama",
  "ollama_base_url": "http://localhost:11434",
  "temperature": 0.7,
  "permission_mode": "auto"
}
```

## 配置文件位置

### 用户级配置

- **Windows**: `%USERPROFILE%\.ccmas\config.json`
- **macOS/Linux**: `~/.ccmas/config.json`

### 项目级配置

在项目根目录创建：
```
project/
├── .ccmas/
│   └── config.json
├── src/
└── README.md
```

项目级配置会覆盖用户级配置中的相同选项。

## 环境变量

### 核心环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `CCMAS_CONFIG_PATH` | 自定义配置文件路径 | `/path/to/config.json` |
| `CCMAS_HISTORY_PATH` | 历史记录文件路径 | `/path/to/history.json` |

### 使用环境变量

**Windows (PowerShell)**:
```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:CCMAS_CONFIG_PATH = "C:\Users\Name\.ccmas\config.json"
ccmas "任务"
```

**Windows (CMD)**:
```cmd
set OPENAI_API_KEY=sk-...
set CCMAS_CONFIG_PATH=C:\Users\Name\.ccmas\config.json
ccmas "任务"
```

**macOS/Linux**:
```bash
export OPENAI_API_KEY="sk-..."
export CCMAS_CONFIG_PATH="$HOME/.ccmas/config.json"
ccmas "任务"
```

### 持久化环境变量

**Windows**:
```powershell
# 用户级
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")

# 系统级
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "Machine")
```

**macOS/Linux**:
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
source ~/.bashrc
```

## 配置验证

### 验证配置文件

```bash
# 使用 verbose 模式查看加载的配置
ccmas --verbose --config /path/to/config.json

# 测试配置
ccmas --version
```

### 配置错误处理

如果配置文件有错误，CCMAS 会：
1. 显示错误信息
2. 使用默认配置继续运行
3. 记录错误到日志（如果启用）

常见配置错误：
- JSON 语法错误
- 无效的配置值
- 配置文件权限问题

## 配置管理最佳实践

### 1. 分层配置策略

```
全局默认 -> 用户配置 -> 项目配置 -> 环境变量 -> 命令行参数
   (1)         (2)          (3)           (4)            (5)
```

优先级：(5) > (4) > (3) > (2) > (1)

### 2. 敏感信息处理

**不要**：
```json
{
  "api_key": "sk-actual-key-here"
}
```

**推荐**：
```json
{
  "api_key": null
}
```
```bash
export OPENAI_API_KEY="sk-actual-key-here"
```

### 3. 项目配置模板

创建 `.ccmas/config.example.json`：
```json
{
  "model": "gpt-4",
  "temperature": 0.5,
  "permission_mode": "acceptEdits"
}
```

添加到 `.gitignore`：
```
.ccmas/config.json
```

### 4. 团队协作配置

使用环境特定的配置文件：
```
.ccmas/
├── config.development.json
├── config.staging.json
└── config.production.json
```

通过环境变量切换：
```bash
export CCMAS_CONFIG_PATH=".ccmas/config.development.json"
```

## 配置参考表

| 配置项 | CLI 参数 | 环境变量 | 配置键 | 类型 | 范围/选项 |
|--------|----------|----------|--------|------|-----------|
| 模型 | `--model` | - | `model` | string | 任意有效模型名 |
| 温度 | `--temperature` | - | `temperature` | float | 0.0 - 2.0 |
| 最大 Token | `--max-tokens` | - | `max_tokens` | int | > 0 |
| API 密钥 | - | `OPENAI_API_KEY` | `api_key` | string | - |
| API 基础 URL | `--api-base` | - | `api_base` | string | URL |
| 后端 | `--ollama`, `--vllm` | - | `backend` | string | openai, ollama, vllm |
| 权限模式 | `--permission-mode` | - | `permission_mode` | string | 见上文 |
| 配置文件 | `--config` | `CCMAS_CONFIG_PATH` | - | string | 文件路径 |
| 彩色输出 | `--no-color` | - | `color_output` | boolean | true, false |
| 详细输出 | `--verbose` | - | `verbose` | boolean | true, false |

## 故障排除

### 配置未生效

1. 检查配置文件路径是否正确
2. 验证 JSON 语法
3. 检查配置优先级（命令行参数会覆盖配置文件）
4. 使用 `--verbose` 查看实际加载的配置

### 配置文件权限错误

```bash
# 修复权限（macOS/Linux）
chmod 600 ~/.ccmas/config.json

# 修复权限（Windows）
icacls "%USERPROFILE%\.ccmas\config.json" /grant:r "%USERNAME%:(R)"
```

### 环境变量未识别

```bash
# 检查环境变量是否设置
echo $OPENAI_API_KEY  # macOS/Linux
echo %OPENAI_API_KEY%  # Windows

# 检查 CCMAS 是否能读取
ccmas --verbose "test" 2>&1 | grep -i "api\|key"
```

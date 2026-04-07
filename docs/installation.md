# 安装指南

本指南将帮助您在系统上安装和配置 CCMAS。

## 系统要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows、macOS 或 Linux
- **内存**: 建议至少 4GB RAM
- **网络**: 需要网络连接（如果使用云端 LLM）

## 安装方法

### 方法一：使用 pip 安装（推荐）

```bash
pip install ccmas
```

### 方法二：从源码安装

```bash
# 克隆仓库
git clone https://github.com/ccmas/ccmas-python-cli.git
cd ccmas-python-cli

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -e .

# 安装开发依赖（可选）
pip install -e ".[dev]"
```

### 方法三：使用 Poetry 安装

```bash
# 克隆仓库
git clone https://github.com/ccmas/ccmas-python-cli.git
cd ccmas-python-cli

# 安装 Poetry（如果尚未安装）
pip install poetry

# 安装依赖
poetry install

# 激活环境
poetry shell
```

## 验证安装

安装完成后，验证 CCMAS 是否正确安装：

```bash
# 检查版本
ccmas --version

# 查看帮助
ccmas --help
```

## 配置 LLM 后端

### OpenAI（默认）

设置环境变量：

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY="your-api-key-here"

# Windows (CMD)
set OPENAI_API_KEY=your-api-key-here

# macOS/Linux
export OPENAI_API_KEY=your-api-key-here
```

或者创建配置文件：

```bash
# 创建配置目录
mkdir -p ~/.ccmas

# 创建配置文件
echo '{"api_key": "your-api-key-here"}' > ~/.ccmas/config.json
```

### Ollama

1. 安装 Ollama：
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. 启动 Ollama 服务：
   ```bash
   ollama serve
   ```

3. 拉取模型：
   ```bash
   ollama pull llama2
   ```

4. 使用 CCMAS：
   ```bash
   ccmas --ollama --model llama2
   ```

### vLLM

1. 安装 vLLM：
   ```bash
   pip install vllm
   ```

2. 启动 vLLM 服务器：
   ```bash
   python -m vllm.entrypoints.openai.api_server \
       --model meta-llama/Llama-2-7b-chat-hf \
       --port 8000
   ```

3. 使用 CCMAS：
   ```bash
   ccmas --vllm --model meta-llama/Llama-2-7b-chat-hf
   ```

## 配置选项

### 全局配置

创建全局配置文件 `~/.ccmas/config.json`：

```json
{
  "model": "gpt-4",
  "temperature": 0.7,
  "backend": "openai",
  "api_base": null,
  "permission_mode": "default",
  "show_token_usage": true,
  "show_timing": true,
  "color_output": true,
  "save_history": true,
  "max_history_size": 1000,
  "timeout": 300,
  "retry_attempts": 3
}
```

### 项目级配置

在项目根目录创建 `.ccmas/config.json`：

```bash
mkdir -p .ccmas
cat > .ccmas/config.json << 'EOF'
{
  "model": "gpt-3.5-turbo",
  "temperature": 0.5,
  "permission_mode": "acceptEdits"
}
EOF
```

项目级配置会覆盖全局配置。

## 环境变量

以下环境变量可用于配置 CCMAS：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `CCMAS_CONFIG_PATH` | 自定义配置文件路径 | `~/.ccmas/config.json` |
| `CCMAS_HISTORY_PATH` | 历史记录文件路径 | `~/.ccmas/history.json` |

## 故障排除

### 问题：命令未找到

**解决方案**：
```bash
# 检查 pip 安装路径
pip show ccmas

# 确保 pip bin 目录在 PATH 中
# 或直接使用 Python 运行
python -m ccmas
```

### 问题：API 密钥错误

**解决方案**：
```bash
# 检查环境变量是否设置
echo $OPENAI_API_KEY  # macOS/Linux
echo %OPENAI_API_KEY%  # Windows

# 验证配置文件
ccmas --config ~/.ccmas/config.json --verbose
```

### 问题：Ollama 连接失败

**解决方案**：
```bash
# 检查 Ollama 服务是否运行
curl http://localhost:11434/api/tags

# 检查模型是否已下载
ollama list
```

### 问题：依赖冲突

**解决方案**：
```bash
# 创建干净的虚拟环境
python -m venv venv_clean
source venv_clean/bin/activate  # 或 venv_clean\Scripts\activate
pip install ccmas
```

## 更新 CCMAS

```bash
# 使用 pip
pip install --upgrade ccmas

# 从源码更新
cd ccmas-python-cli
git pull
pip install -e .
```

## 卸载 CCMAS

```bash
pip uninstall ccmas
```

## 下一步

安装完成后，请阅读：
- [使用指南](usage.md) - 学习基本用法
- [配置说明](configuration.md) - 了解详细配置选项
- [示例代码](examples.md) - 查看实际使用示例

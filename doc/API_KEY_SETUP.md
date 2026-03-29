# 配置 API Key 说明

## 演示程序运行成功！

演示程序已经成功创建了3篇示例文章并保存到数据库 `data/demo.db`。

由于未配置 ANTHROPIC_API_KEY，系统跳过了AI分析步骤。

## 如何配置 API Key

### 步骤1：获取 API Key

访问 Anthropic 控制台：https://console.anthropic.com/

1. 注册/登录账号
2. 进入 API Keys 页面
3. 创建新的 API Key
4. 复制 API Key（格式：sk-ant-api03-xxxxx）

### 步骤2：配置环境变量

在项目根目录创建 `.env` 文件：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

### 步骤3：编辑 .env 文件

用文本编辑器打开 `.env` 文件，填入你的 API Key：

```
# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-api03-你的实际密钥

# 数据库配置
DATABASE_PATH=data/articles.db

# 采集配置
SEARCH_KEYWORDS=大模型,Claude,GPT,AI,人工智能,LLM
MAX_ARTICLES_PER_SEARCH=20

# 分析配置
ANALYSIS_MODEL=claude-sonnet-4-6
```

### 步骤4：再次运行演示

配置完成后，再次运行演示程序：

```bash
python demo.py
```

这次将会调用 Claude API 对文章进行智能分析，包括：
- 生成文章摘要
- 提取关键词
- 文章分类
- 深度分析

## 测试 API 连接

你也可以运行测试脚本验证配置：

```bash
python test.py
# 选择选项 2：测试分析模块
```

## 费用说明

- Claude Sonnet 4.6: $3/MTok (输入), $15/MTok (输出)
- 单篇文章分析成本：约 $0.01-0.02
- 演示程序分析3篇文章：约 $0.03-0.06

## 无 API Key 的使用方式

如果暂时没有 API Key，你仍然可以：

1. **使用演示数据**：查看已创建的示例文章
2. **测试数据库功能**：运行 `python test.py` 选择选项1
3. **手动采集文章**：使用采集模块保存文章到数据库
4. **稍后分析**：配置 API Key 后再对已采集的文章进行分析

## 查看演示数据

使用 SQLite 工具查看演示数据库：

```bash
# 安装 sqlite3（如果没有）
# Windows: 下载 https://www.sqlite.org/download.html

# 查看数据
sqlite3 data/demo.db "SELECT title, account_name, publish_time FROM articles;"
```

或使用 Python：

```python
import sqlite3
conn = sqlite3.connect('data/demo.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM articles")
for row in cursor.fetchall():
    print(row)
conn.close()
```

## 下一步

配置好 API Key 后，你可以：

1. 运行完整的演示程序（包含AI分析）
2. 使用 `python main.py` 开始正式采集和分析
3. 根据需求自定义配置和功能

祝使用愉快！

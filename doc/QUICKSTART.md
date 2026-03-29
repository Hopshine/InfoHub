# 快速启动指南

## 第一步：安装依赖

```bash
pip install -r requirements.txt
```

## 第二步：配置API Key

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的Anthropic API Key：
```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

如果还没有API Key，请访问：https://console.anthropic.com/

## 第三步：运行演示程序（推荐）

```bash
python demo.py
```

演示程序会：
- 创建3篇示例文章
- 使用Claude API进行分析
- 展示分析结果

这是了解系统功能的最快方式！

## 第四步：运行主程序

```bash
python main.py
```

选择操作：
- **选项1**：采集文章（从微信公众号搜索并保存）
- **选项2**：分析文章（使用AI分析已采集的文章）
- **选项3**：生成报告（生成Markdown格式的分析报告）
- **选项4**：全流程执行（一键完成采集→分析→报告）

## 重要提示

### 关于文章采集

由于微信公众号的反爬机制，直接采集可能会遇到验证码或IP封禁。

**推荐方案：**

1. **使用第三方API**（最稳定）
   - 天行数据：https://www.tianapi.com/
   - 聚合数据：https://www.juhe.cn/

2. **手动收集URL**
   - 手动复制文章链接到 `urls.txt`
   - 系统自动抓取内容并分析

3. **先运行演示程序**
   - 使用模拟数据体验完整功能
   - 无需担心采集问题

### 配置说明

在 `.env` 文件中可以自定义：

```bash
# 搜索关键词（逗号分隔）
SEARCH_KEYWORDS=大模型,Claude,GPT,AI,人工智能,LLM

# 每个关键词最多采集文章数
MAX_ARTICLES_PER_SEARCH=20

# 使用的Claude模型
ANALYSIS_MODEL=claude-sonnet-4-6
```

## 测试系统

运行测试脚本验证各模块：

```bash
python test.py
```

## 查看结果

- **数据库**：`data/articles.db`（使用SQLite工具查看）
- **日志**：`logs/app_YYYYMMDD.log`
- **报告**：`reports/report_YYYYMMDD_HHMMSS.md`

## 需要帮助？

- 查看详细文档：`USAGE.md`
- 技术方案：`TECHNICAL_DESIGN.md`
- 项目说明：`README.md`

## 常见问题

**Q: 采集失败怎么办？**
A: 参考 `collector/alternative_collectors.py` 中的替代方案

**Q: API调用失败？**
A: 检查API Key是否正确，账户是否有余额

**Q: 如何定时执行？**
A: 使用cron（Linux/Mac）或任务计划程序（Windows）

---

祝使用愉快！🚀

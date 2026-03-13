# 使用指南

## 系统说明

这是一个微信公众号文章采集与分析系统，专注于收集大模型相关的文章并使用Claude API进行智能分析。

## 功能模块

### 1. 文章采集模块
- 通过搜狗微信搜索API搜索关键词相关文章
- 自动抓取文章标题、作者、发布时间、内容等信息
- 去重处理，避免重复采集

### 2. 内容分析模块
- 使用Claude API对文章进行深度分析
- 自动生成摘要、提取关键词
- 文章分类（技术解读、行业动态、产品评测等）
- 深度分析（观点、创新点、应用价值等）

### 3. 数据存储模块
- SQLite数据库持久化存储
- 支持文章查询、统计、导出

### 4. 报告生成模块
- 自动生成Markdown格式分析报告
- 统计概览、分类统计、最新文章列表

## 安装步骤

1. 确保已安装Python 3.8+

2. 安装依赖包：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的Anthropic API Key：
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

## 使用方法

运行主程序：
```bash
python main.py
```

选择操作：
- 选项1：采集文章（搜索并保存文章）
- 选项2：分析文章（使用Claude分析已采集的文章）
- 选项3：生成报告（生成分析报告）
- 选项4：全流程执行（依次执行采集、分析、生成报告）

## 配置说明

在 `.env` 文件中可以配置：

- `ANTHROPIC_API_KEY`: Claude API密钥（必填）
- `SEARCH_KEYWORDS`: 搜索关键词，逗号分隔（默认：大模型,Claude,GPT,AI）
- `MAX_ARTICLES_PER_SEARCH`: 每个关键词最多采集文章数（默认：20）
- `ANALYSIS_MODEL`: 使用的Claude模型（默认：claude-sonnet-4-6）

## 注意事项

### 关于微信文章采集

由于微信公众号的反爬机制，直接采集可能会遇到以下问题：

1. **验证码拦截**：搜狗微信搜索会要求验证码验证
2. **IP封禁**：频繁请求可能导致IP被封

**解决方案：**

1. **使用代理IP池**：轮换IP地址
2. **接入第三方API**：
   - 天行数据 (https://www.tianapi.com/)
   - 聚合数据 (https://www.juhe.cn/)
   - 微信公众号API服务商

3. **手动导入**：
   - 手动复制文章内容
   - 使用浏览器插件辅助采集

### 推荐方案

对于生产环境，建议：
1. 使用付费的第三方API服务
2. 或者手动收集文章URL，系统负责内容抓取和分析
3. 配置代理池和验证码识别服务

## 数据库结构

文章表 (articles)：
- id: 主键
- title: 标题
- author: 作者
- account_name: 公众号名称
- publish_time: 发布时间
- url: 文章链接
- content: 文章内容
- summary: 摘要（AI生成）
- keywords: 关键词（AI提取）
- category: 分类（AI判断）
- analysis: 深度分析（AI生成）
- created_at: 创建时间
- updated_at: 更新时间

## 扩展建议

1. **定时任务**：使用cron或Windows任务计划程序定时执行
2. **Web界面**：使用Flask/FastAPI开发Web管理界面
3. **数据可视化**：使用Plotly/ECharts展示统计图表
4. **导出功能**：支持导出Excel、PDF报告
5. **邮件通知**：分析完成后发送邮件通知

## 故障排查

### 采集失败
- 检查网络连接
- 确认搜狗微信搜索是否可访问
- 考虑使用代理或第三方API

### 分析失败
- 检查ANTHROPIC_API_KEY是否正确
- 确认API额度是否充足
- 查看日志文件了解详细错误

### 数据库错误
- 确认data目录存在且有写权限
- 检查SQLite是否正常安装

## 技术支持

如有问题，请查看：
- 日志文件：`logs/app_YYYYMMDD.log`
- 项目文档：README.md

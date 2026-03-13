# 微信公众号信息收集与分析系统

## 功能特性

- 自动采集大模型相关的微信公众号文章
- 使用Claude API进行内容分析和摘要
- 数据持久化存储
- 生成分析报告
- **🌐 Web可视化管理界面**（新增）

## 技术栈

- Python 3.8+
- SQLite
- Anthropic Claude API
- Flask Web框架
- HTML/CSS/JavaScript

## 快速开始

### 方式1: Web界面（推荐）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动Web服务器
python web_app.py

# 3. 浏览器访问
http://localhost:5000
```

### 方式2: 命令行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 文件，填入你的 ANTHROPIC_API_KEY

# 3. 运行演示
python demo.py

# 4. 运行主程序
python main.py
```

## 🌐 Web界面功能

- 📊 实时数据统计仪表盘
- 📝 文章列表展示和搜索
- 🔍 分类过滤和筛选
- 📖 文章详情查看
- 🤖 在线AI分析功能
- 📈 分类统计图表
- 📱 响应式设计，支持移动端

**访问地址**: http://localhost:5000

详细使用说明请查看 `WEB_GUIDE.md`

## 项目结构

```
infoHub/
├── main.py              # 命令行主程序
├── web_app.py           # Web服务器
├── demo.py              # 演示程序
├── test.py              # 测试脚本
├── view_db.py           # 数据库查看工具
├── config.py            # 配置管理
├── collector/           # 采集模块
│   └── wechat_collector.py
├── analyzer/            # 分析模块
│   └── content_analyzer.py
├── storage/             # 存储模块
│   └── database.py
├── utils/               # 工具函数
│   └── logger.py
├── templates/           # Web模板
│   └── index.html
├── static/              # 静态资源
│   ├── css/style.css
│   └── js/app.js
└── data/                # 数据目录
    └── articles.db
```

## 文档

- `QUICKSTART.md` - 快速启动指南
- `WEB_GUIDE.md` - Web界面使用指南
- `USAGE.md` - 详细使用说明
- `TECHNICAL_DESIGN.md` - 技术方案文档
- `API_KEY_SETUP.md` - API配置说明
- `FINAL_SUMMARY.md` - 项目完成总结

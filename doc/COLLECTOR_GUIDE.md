# 📥 微信文章采集功能完整指南

## ✅ 采集功能已完成

系统现在支持完整的微信公众号文章采集功能，包括：

1. **单个URL采集** - 输入单个文章URL进行采集
2. **批量URL采集** - 一次性导入多个URL批量采集
3. **搜索采集** - 通过关键词搜索并采集文章
4. **命令行工具** - 提供独立的命令行采集工具

## 🌐 Web界面采集（推荐）

### 访问采集功能

1. 打开浏览器访问: http://localhost:5000
2. 点击顶部的 **"📥 采集文章"** 按钮
3. 选择采集方式

### 方式1: 单个URL采集

**适用场景**: 采集少量文章，逐个添加

**操作步骤**:
1. 切换到"单个URL"标签页
2. 输入微信文章URL
   ```
   https://mp.weixin.qq.com/s/xxxxx
   ```
3. 点击"开始采集"
4. 等待采集完成

**优点**:
- ✅ 操作简单
- ✅ 即时反馈
- ✅ 适合测试

### 方式2: 批量URL采集

**适用场景**: 已收集多个URL，需要批量导入

**操作步骤**:
1. 切换到"批量URL"标签页
2. 在文本框中输入多个URL，每行一个:
   ```
   https://mp.weixin.qq.com/s/xxxxx
   https://mp.weixin.qq.com/s/yyyyy
   https://mp.weixin.qq.com/s/zzzzz
   ```
3. 点击"批量采集"
4. 确认采集数量
5. 等待批量采集完成

**优点**:
- ✅ 效率高
- ✅ 支持大量URL
- ✅ 显示详细结果

### 方式3: 搜索采集

**适用场景**: 通过关键词发现新文章

**操作步骤**:
1. 切换到"搜索采集"标签页
2. 输入搜索关键词（如：Claude、GPT、大模型）
3. 设置最多采集数量（建议5-10篇）
4. 点击"搜索并采集"
5. 等待搜索和采集完成

**注意事项**:
- ⚠️ 可能遇到验证码
- ⚠️ 建议配合代理使用
- ⚠️ 首选URL导入方式

## 💻 命令行采集工具

### 工具1: URL导入工具

```bash
python import_urls.py
```

**功能**:
1. 从文件导入URL (urls.txt)
2. 手动输入URL
3. 搜索并采集

**使用文件导入**:

1. 创建 `urls.txt` 文件:
   ```
   # 微信文章URL列表
   https://mp.weixin.qq.com/s/xxxxx
   https://mp.weixin.qq.com/s/yyyyy
   https://mp.weixin.qq.com/s/zzzzz
   ```

2. 运行导入工具:
   ```bash
   python import_urls.py
   ```

3. 选择"1. 从文件导入URL"

4. 确认并开始采集

### 工具2: 测试采集功能

```bash
python test_collector.py
```

**功能**:
- 测试单个URL采集
- 测试搜索功能
- 验证采集器是否正常工作

## 📝 如何获取微信文章URL

### 方法1: 手机微信

1. 打开微信文章
2. 点击右上角"..."
3. 选择"复制链接"
4. 粘贴到采集工具

### 方法2: 电脑浏览器

1. 在浏览器中打开微信文章
2. 复制地址栏的URL
3. 粘贴到采集工具

### 方法3: 搜狗微信搜索

1. 访问: https://weixin.sogou.com/
2. 搜索关键词
3. 复制文章链接
4. 或直接使用系统的搜索采集功能

## 🎯 采集流程

```
输入URL
  ↓
发送HTTP请求
  ↓
解析HTML页面
  ↓
提取文章信息
  ├─ 标题
  ├─ 公众号名称
  ├─ 作者
  ├─ 发布时间
  └─ 文章内容
  ↓
保存到数据库
  ↓
采集完成
```

## 🔧 采集器技术实现

### 核心功能

**文件**: `collector/wechat_collector_v2.py`

**主要方法**:
- `fetch_article_from_url()` - 从URL获取文章
- `collect_from_url_list()` - 批量采集
- `search_articles_sogou()` - 搜狗搜索
- `_extract_title()` - 提取标题
- `_extract_content()` - 提取内容

### 提取策略

系统使用多种策略提取文章信息，确保兼容性：

**标题提取**:
1. `<h1 id="activity-name">`
2. `<h1 class="rich_media_title">`
3. `<meta property="og:title">`

**内容提取**:
1. `<div id="js_content">`
2. `<div class="rich_media_content">`

**公众号提取**:
1. `<strong class="profile_nickname">`
2. `<a id="js_name">`
3. `<meta property="og:article:author">`

## ⚠️ 注意事项

### 反爬机制

微信公众号有反爬保护：
- 🔒 频率限制
- 🔒 验证码验证
- 🔒 IP封禁

**应对策略**:
1. 添加随机延迟（2-5秒）
2. 使用代理IP池
3. 优先使用URL导入方式
4. 避免短时间大量请求

### 法律合规

- ✅ 仅用于个人学习研究
- ✅ 尊重版权，不用于商业
- ✅ 遵守robots.txt协议
- ❌ 不进行大规模爬取
- ❌ 不用于非法用途

### 数据质量

采集可能失败的情况：
- 文章已删除
- URL已过期
- 网络连接问题
- 遇到验证码
- 页面结构变化

**建议**:
- 定期检查采集结果
- 验证数据完整性
- 保留原始URL

## 📊 采集统计

采集完成后，系统会显示：
- ✅ 成功数量
- ⏭️ 跳过数量（已存在）
- ❌ 失败数量
- 📝 详细结果列表

## 🚀 最佳实践

### 推荐工作流程

1. **收集URL**
   - 手动浏览微信公众号
   - 使用搜狗微信搜索
   - 保存到urls.txt文件

2. **批量导入**
   - 使用Web界面批量采集
   - 或使用命令行工具

3. **验证数据**
   - 检查采集结果
   - 查看文章详情
   - 确认内容完整

4. **AI分析**
   - 配置API Key
   - 批量分析文章
   - 生成报告

### 采集频率建议

- 单次采集: 10-20篇
- 采集间隔: 5-10分钟
- 每日上限: 100-200篇

### 错误处理

遇到问题时：
1. 检查URL是否有效
2. 验证网络连接
3. 查看日志文件 `logs/app_*.log`
4. 尝试单个URL测试
5. 使用测试工具诊断

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `collector/wechat_collector_v2.py` | 采集器核心代码 |
| `import_urls.py` | URL导入工具 |
| `test_collector.py` | 采集功能测试 |
| `urls.txt` | URL列表文件 |
| `web_app.py` | Web采集API |

## 🎯 快速开始

### 立即体验

1. **Web界面采集**:
   ```bash
   # 确保Web服务器运行中
   # 访问 http://localhost:5000
   # 点击"采集文章"按钮
   ```

2. **命令行采集**:
   ```bash
   # 创建urls.txt文件
   echo "https://mp.weixin.qq.com/s/xxxxx" > urls.txt

   # 运行导入工具
   python import_urls.py
   ```

3. **测试采集**:
   ```bash
   python test_collector.py
   ```

## 💡 示例

### 示例1: 采集单篇文章

```python
from collector.wechat_collector_v2 import WeChatCollectorV2

collector = WeChatCollectorV2()
url = "https://mp.weixin.qq.com/s/xxxxx"
article = collector.fetch_article_from_url(url)

if article:
    print(f"标题: {article['title']}")
    print(f"内容: {article['content'][:100]}...")
```

### 示例2: 批量采集

```python
urls = [
    "https://mp.weixin.qq.com/s/xxxxx",
    "https://mp.weixin.qq.com/s/yyyyy",
]

collector = WeChatCollectorV2()
articles = collector.collect_from_url_list(urls)

print(f"成功采集 {len(articles)} 篇文章")
```

## 🎉 总结

采集功能已完全实现并可用：

- ✅ Web界面采集（3种方式）
- ✅ 命令行工具
- ✅ 批量处理
- ✅ 错误处理
- ✅ 完整文档

**立即开始**: 访问 http://localhost:5000 点击"采集文章"！

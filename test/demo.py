#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速启动脚本 - 用于演示系统功能（使用模拟数据）
"""

import sys
import os
from datetime import datetime

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from analyzer.content_analyzer import ContentAnalyzer
from config import Config

def create_demo_data(db: Database):
    """创建演示数据"""
    print("正在创建演示数据...")

    demo_articles = [
        {
            'title': 'Claude 4.6发布：AI推理能力的重大突破',
            'author': 'AI科技评论',
            'account_name': 'AI前沿观察',
            'publish_time': '2024-03-10',
            'url': 'https://example.com/article1',
            'content': '''
            Anthropic公司今日正式发布Claude 4.6大语言模型，这是继Claude 3.5之后的又一重大升级。
            新模型在推理能力、代码生成和长文本理解方面都有显著提升。

            主要特性：
            1. 上下文窗口扩展至100万token，可处理超长文档
            2. 推理能力提升40%，在数学和逻辑问题上表现更优
            3. 代码生成准确率提高35%，支持更多编程语言
            4. 增强的安全性和可控性，减少有害输出

            技术创新：
            Claude 4.6采用了全新的Constitutional AI训练方法，通过多轮对话和反馈机制，
            使模型更好地理解人类价值观和安全边界。同时引入了动态注意力机制，
            显著提升了长文本处理效率。

            应用场景：
            - 代码开发助手
            - 文档分析和总结
            - 复杂问题求解
            - 创意写作辅助
            '''
        },
        {
            'title': 'GPT-5传闻：OpenAI的下一步棋',
            'author': '科技观察者',
            'account_name': '深度科技',
            'publish_time': '2024-03-12',
            'url': 'https://example.com/article2',
            'content': '''
            近日，关于OpenAI即将发布GPT-5的传闻甚嚣尘上。虽然官方尚未确认，
            但业内人士透露，新模型可能在今年下半年问世。

            预期改进：
            1. 多模态能力增强，更好地理解图像、视频和音频
            2. 推理链更长，可处理更复杂的多步骤问题
            3. 实时学习能力，可根据对话动态调整
            4. 更低的运行成本和更快的响应速度

            行业影响：
            GPT-5的发布将进一步推动AI在各行业的应用。教育、医疗、金融等领域
            都将受益于更强大的AI能力。同时，这也对AI安全和伦理提出了新的挑战。

            竞争格局：
            随着Claude、Gemini等竞品的快速发展，OpenAI面临着前所未有的竞争压力。
            GPT-5能否保持领先地位，将是业界关注的焦点。
            '''
        },
        {
            'title': '大模型应用落地：从概念到实践',
            'author': '产品经理',
            'account_name': 'AI产品思考',
            'publish_time': '2024-03-13',
            'url': 'https://example.com/article3',
            'content': '''
            大语言模型技术日趋成熟，但如何将其有效应用到实际业务中，
            仍是许多企业面临的挑战。本文分享一些实践经验。

            关键要素：
            1. 明确应用场景：不是所有问题都需要大模型
            2. 数据准备：高质量的训练数据是成功的基础
            3. 提示工程：精心设计的提示词能显著提升效果
            4. 评估体系：建立科学的评估指标

            常见应用：
            - 客服机器人：自动回答常见问题
            - 内容生成：文章、报告、营销文案
            - 代码助手：辅助开发人员编写代码
            - 数据分析：从海量数据中提取洞察

            注意事项：
            - 成本控制：API调用费用可能很高
            - 数据安全：避免泄露敏感信息
            - 准确性验证：AI输出需要人工审核
            - 用户体验：设计友好的交互界面
            '''
        }
    ]

    for article in demo_articles:
        article_id = db.insert_article(article)
        if article_id:
            print(f"[OK] 已添加: {article['title']}")

    print(f"\n演示数据创建完成，共 {len(demo_articles)} 篇文章\n")

def demo_analysis(db: Database):
    """演示分析功能"""
    print("=" * 60)
    print("开始分析演示文章")
    print("=" * 60)

    try:
        Config.validate()
    except ValueError as e:
        print(f"\n⚠ 警告: {e}")
        print("跳过AI分析步骤（需要配置ANTHROPIC_API_KEY）\n")
        return

    analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)
    unanalyzed = db.get_unanalyzed_articles(limit=3)

    if not unanalyzed:
        print("所有文章都已分析完成")
        return

    for i, article in enumerate(unanalyzed, 1):
        print(f"\n[{i}/{len(unanalyzed)}] 分析: {article['title']}")
        print("-" * 60)

        result = analyzer.analyze_article(article)

        db.update_analysis(
            article['id'],
            result['analysis'],
            result['summary'],
            result['keywords'],
            result['category']
        )

        print(f"分类: {result['category']}")
        print(f"关键词: {result['keywords']}")
        print(f"摘要: {result['summary'][:100]}...")

    print("\n[OK] 分析完成\n")

def show_results(db: Database):
    """展示结果"""
    print("=" * 60)
    print("分析结果汇总")
    print("=" * 60)

    articles = db.get_all_articles(limit=10)

    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   公众号: {article['account_name']}")
        print(f"   发布时间: {article['publish_time']}")

        if article['category']:
            print(f"   分类: {article['category']}")

        if article['keywords']:
            print(f"   关键词: {article['keywords']}")

        if article['summary']:
            print(f"   摘要: {article['summary'][:80]}...")

    print("\n" + "=" * 60)

def main():
    print("\n" + "=" * 60)
    print("InfoHub 演示程序")
    print("=" * 60)

    # 使用独立的演示数据库
    demo_db_path = 'data/demo.db'
    db = Database(demo_db_path)

    print("\n这是一个演示程序，将展示系统的核心功能：")
    print("1. 创建演示文章数据")
    print("2. 使用Claude API分析文章（需要API Key）")
    print("3. 展示分析结果\n")

    input("按回车键开始演示...")

    # 步骤1：创建演示数据
    create_demo_data(db)

    # 步骤2：分析文章
    demo_analysis(db)

    # 步骤3：展示结果
    show_results(db)

    print("\n演示完成！")
    print(f"演示数据库位置: {demo_db_path}")
    print("你可以运行 python main.py 开始正式使用系统\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n演示被中断")
    except Exception as e:
        print(f"\n错误: {e}")

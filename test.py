#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本 - 用于验证系统各模块功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from analyzer.content_analyzer import ContentAnalyzer
from config import Config

def test_database():
    """测试数据库模块"""
    print("=" * 50)
    print("测试数据库模块")
    print("=" * 50)

    db = Database('data/test.db')

    # 插入测试文章
    test_article = {
        'title': '测试文章：Claude 4.6发布',
        'author': '测试作者',
        'account_name': '测试公众号',
        'publish_time': '2024-03-14',
        'url': 'https://example.com/test',
        'content': 'Claude 4.6是Anthropic最新发布的大语言模型，具有更强的推理能力和更长的上下文窗口。'
    }

    article_id = db.insert_article(test_article)

    if article_id:
        print(f"✓ 文章插入成功，ID: {article_id}")
    else:
        print("✗ 文章插入失败（可能已存在）")

    # 查询文章
    articles = db.get_all_articles(limit=5)
    print(f"✓ 查询到 {len(articles)} 篇文章")

    # 查询未分析文章
    unanalyzed = db.get_unanalyzed_articles(limit=5)
    print(f"✓ 未分析文章: {len(unanalyzed)} 篇")

    print("\n数据库模块测试完成\n")

def test_analyzer():
    """测试分析模块"""
    print("=" * 50)
    print("测试分析模块")
    print("=" * 50)

    try:
        Config.validate()
    except ValueError as e:
        print(f"✗ 配置验证失败: {e}")
        print("请先在 .env 文件中配置 ANTHROPIC_API_KEY")
        return

    analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)

    test_article = {
        'title': 'Claude 4.6：AI推理能力的新突破',
        'content': '''
        Anthropic最新发布的Claude 4.6模型在多个基准测试中表现出色。
        该模型具有100万token的上下文窗口，支持更长的文档处理。
        在代码生成、数学推理和复杂问题解决方面都有显著提升。
        Claude 4.6采用了全新的训练方法，提高了模型的安全性和可控性。
        '''
    }

    print("正在调用Claude API进行分析...")
    result = analyzer.analyze_article(test_article)

    print("\n分析结果：")
    print(f"分类: {result['category']}")
    print(f"关键词: {result['keywords']}")
    print(f"摘要: {result['summary']}")
    print(f"\n深度分析:\n{result['analysis'][:200]}...")

    print("\n✓ 分析模块测试完成\n")

def test_full_workflow():
    """测试完整工作流"""
    print("=" * 50)
    print("测试完整工作流")
    print("=" * 50)

    try:
        Config.validate()
    except ValueError as e:
        print(f"✗ 配置验证失败: {e}")
        return

    db = Database('data/test.db')
    analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)

    # 获取未分析文章
    unanalyzed = db.get_unanalyzed_articles(limit=1)

    if not unanalyzed:
        print("没有待分析的文章")
        return

    article = unanalyzed[0]
    print(f"分析文章: {article['title']}")

    # 分析
    result = analyzer.analyze_article(article)

    # 更新数据库
    db.update_analysis(
        article['id'],
        result['analysis'],
        result['summary'],
        result['keywords'],
        result['category']
    )

    print("✓ 完整工作流测试完成")

def main():
    print("\nInfoHub 系统测试\n")

    print("请选择测试项：")
    print("1. 测试数据库模块")
    print("2. 测试分析模块（需要API Key）")
    print("3. 测试完整工作流（需要API Key）")
    print("0. 退出")

    choice = input("\n请输入选项 (0-3): ").strip()

    if choice == '1':
        test_database()
    elif choice == '2':
        test_analyzer()
    elif choice == '3':
        test_full_workflow()
    elif choice == '0':
        print("退出测试")
    else:
        print("无效选项")

if __name__ == '__main__':
    main()

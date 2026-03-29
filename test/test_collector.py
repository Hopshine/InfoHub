#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试采集功能
"""

import sys
import os

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector.wechat_collector_v2 import WeChatCollectorV2

def test_url_extraction():
    """测试URL提取功能"""
    print("=" * 60)
    print("测试URL提取功能")
    print("=" * 60)

    # 测试URL（这是一个示例，实际使用时需要真实的微信文章URL）
    test_url = input("\n请输入一个微信文章URL进行测试: ").strip()

    if not test_url:
        print("未输入URL")
        return

    collector = WeChatCollectorV2()

    print(f"\n正在采集: {test_url}")
    print("-" * 60)

    article = collector.fetch_article_from_url(test_url)

    if article:
        print("\n[成功] 采集成功!")
        print(f"\n标题: {article['title']}")
        print(f"公众号: {article['account_name']}")
        print(f"作者: {article['author']}")
        print(f"发布时间: {article['publish_time']}")
        print(f"内容长度: {len(article['content'])} 字符")
        print(f"\n内容预览:")
        print(article['content'][:300])
        print("...")
    else:
        print("\n[失败] 采集失败")
        print("可能原因:")
        print("1. URL无效或已过期")
        print("2. 网络连接问题")
        print("3. 文章已被删除")

def test_search():
    """测试搜索功能"""
    print("=" * 60)
    print("测试搜索功能")
    print("=" * 60)

    keyword = input("\n请输入搜索关键词: ").strip()

    if not keyword:
        print("未输入关键词")
        return

    collector = WeChatCollectorV2()

    print(f"\n正在搜索: {keyword}")
    print("-" * 60)

    articles = collector.search_articles_sogou(keyword, max_results=5)

    if articles:
        print(f"\n[成功] 搜索到 {len(articles)} 篇文章")
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   公众号: {article['account_name']}")
            print(f"   时间: {article['publish_time']}")
            print(f"   URL: {article['url'][:60]}...")
    else:
        print("\n[失败] 未搜索到文章")
        print("可能原因:")
        print("1. 遇到验证码")
        print("2. 关键词无结果")
        print("3. 网络问题")

def main():
    print("\n采集功能测试工具\n")

    print("请选择测试项:")
    print("1. 测试URL采集")
    print("2. 测试搜索功能")
    print("0. 退出")

    choice = input("\n请选择 (0-2): ").strip()

    if choice == '1':
        test_url_extraction()
    elif choice == '2':
        test_search()
    elif choice == '0':
        print("退出")
    else:
        print("无效选择")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

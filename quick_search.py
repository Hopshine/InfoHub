#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试搜索采集功能
"""

import sys
import os

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector.wechat_collector_v2 import WeChatCollectorV2
from storage.database import Database
from config import Config

def quick_search_test():
    """快速测试搜索功能"""
    print("=" * 60)
    print("搜索采集快速测试")
    print("=" * 60)

    # 测试关键词
    keywords = ["Claude", "AI日报", "GPT"]

    print("\n可用的测试关键词:")
    for i, kw in enumerate(keywords, 1):
        print(f"{i}. {kw}")

    choice = input("\n选择关键词 (1-3) 或输入自定义关键词: ").strip()

    if choice.isdigit() and 1 <= int(choice) <= 3:
        keyword = keywords[int(choice) - 1]
    else:
        keyword = choice if choice else "Claude"

    print(f"\n搜索关键词: {keyword}")
    print("最多采集: 3 篇（测试用）")
    print("\n注意: 可能遇到验证码")

    confirm = input("\n确认继续? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 初始化
    collector = WeChatCollectorV2()
    db = Database(Config.DATABASE_PATH)

    print("\n正在搜索...")
    print("-" * 60)

    # 搜索
    articles = collector.search_articles_sogou(keyword, max_results=3)

    if not articles:
        print("\n[失败] 未搜索到文章")
        print("\n可能原因:")
        print("1. 遇到验证码 - 建议使用URL导入方式")
        print("2. 关键词无结果")
        print("3. 网络问题")
        print("\n推荐方案:")
        print("- 手动访问 https://weixin.sogou.com/ 搜索")
        print("- 复制文章URL")
        print("- 使用Web界面的批量URL导入功能")
        return

    print(f"\n[成功] 搜索到 {len(articles)} 篇文章\n")

    # 显示搜索结果
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   公众号: {article['account_name']}")
        print(f"   时间: {article['publish_time']}")
        print(f"   URL: {article['url'][:60]}...")
        print()

    # 询问是否采集详细内容
    collect = input("是否采集这些文章的详细内容? (y/n): ").strip().lower()
    if collect != 'y':
        print("已取消采集")
        return

    print("\n开始采集详细内容...")
    print("-" * 60)

    success_count = 0
    for i, article in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {article['title'][:40]}...")

        # 检查是否已存在
        if db.article_exists(article['url']):
            print("  [跳过] 已存在")
            continue

        # 获取详细内容
        full_article = collector.fetch_article_from_url(article['url'])

        if full_article:
            article_id = db.insert_article(full_article)
            if article_id:
                print(f"  [成功] ID: {article_id}")
                success_count += 1
            else:
                print("  [失败] 保存失败")
        else:
            print("  [失败] 获取内容失败")

    print("\n" + "=" * 60)
    print(f"采集完成! 成功 {success_count}/{len(articles)} 篇")
    print("=" * 60)

    if success_count > 0:
        print("\n可以通过以下方式查看:")
        print("1. Web界面: http://localhost:5000")
        print("2. 命令行: python view_db.py")

if __name__ == '__main__':
    try:
        quick_search_test()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

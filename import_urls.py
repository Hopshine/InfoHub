#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL导入工具 - 用于批量导入微信文章URL并采集内容
"""

import sys
import os

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector.wechat_collector_v2 import WeChatCollectorV2
from storage.database import Database
from config import Config

def import_from_file():
    """从文件导入URL"""
    print("=" * 60)
    print("URL导入工具")
    print("=" * 60)

    # 检查urls.txt是否存在
    if not os.path.exists('urls.txt'):
        print("\n未找到 urls.txt 文件")
        print("请创建 urls.txt 文件，每行一个微信文章URL")
        print("\n示例格式:")
        print("https://mp.weixin.qq.com/s/xxxxx")
        print("https://mp.weixin.qq.com/s/yyyyy")

        # 创建示例文件
        with open('urls.txt', 'w', encoding='utf-8') as f:
            f.write("# 微信文章URL列表\n")
            f.write("# 每行一个URL，以 # 开头的行为注释\n")
            f.write("# 示例:\n")
            f.write("# https://mp.weixin.qq.com/s/xxxxx\n")

        print("\n已创建示例文件 urls.txt，请编辑后重新运行")
        return

    # 读取URL
    with open('urls.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    urls = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and line.startswith('http'):
            urls.append(line)

    if not urls:
        print("\nurls.txt 中没有有效的URL")
        print("请添加微信文章URL后重新运行")
        return

    print(f"\n找到 {len(urls)} 个URL")
    print("\n预览:")
    for i, url in enumerate(urls[:5], 1):
        print(f"{i}. {url[:60]}...")

    if len(urls) > 5:
        print(f"... 还有 {len(urls) - 5} 个URL")

    # 确认
    confirm = input("\n确认开始采集? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 初始化
    db = Database(Config.DATABASE_PATH)
    collector = WeChatCollectorV2()

    print("\n开始采集...")
    print("=" * 60)

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url[:60]}...")

        # 检查是否已存在
        if db.article_exists(url):
            print("  [跳过] 文章已存在")
            skip_count += 1
            continue

        # 采集文章
        article = collector.fetch_article_from_url(url)

        if article:
            # 保存到数据库
            article_id = db.insert_article(article)

            if article_id:
                print(f"  [成功] {article['title'][:40]}")
                success_count += 1
            else:
                print("  [失败] 保存到数据库失败")
                fail_count += 1
        else:
            print("  [失败] 采集失败")
            fail_count += 1

    # 统计
    print("\n" + "=" * 60)
    print("采集完成!")
    print(f"成功: {success_count} 篇")
    print(f"跳过: {skip_count} 篇")
    print(f"失败: {fail_count} 篇")
    print("=" * 60)

def import_from_input():
    """手动输入URL"""
    print("=" * 60)
    print("手动输入URL")
    print("=" * 60)
    print("\n请输入微信文章URL（输入空行结束）:\n")

    urls = []
    while True:
        url = input(f"URL {len(urls) + 1}: ").strip()
        if not url:
            break
        if url.startswith('http'):
            urls.append(url)
        else:
            print("  [警告] 无效的URL，已跳过")

    if not urls:
        print("\n未输入任何URL")
        return

    print(f"\n共输入 {len(urls)} 个URL")

    # 初始化
    db = Database(Config.DATABASE_PATH)
    collector = WeChatCollectorV2()

    print("\n开始采集...")

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] 采集中...")

        if db.article_exists(url):
            print("  [跳过] 文章已存在")
            continue

        article = collector.fetch_article_from_url(url)

        if article:
            article_id = db.insert_article(article)
            if article_id:
                print(f"  [成功] {article['title'][:40]}")
            else:
                print("  [失败] 保存失败")
        else:
            print("  [失败] 采集失败")

    print("\n采集完成!")

def search_and_collect():
    """搜索并采集"""
    print("=" * 60)
    print("搜索并采集")
    print("=" * 60)

    keyword = input("\n请输入搜索关键词: ").strip()
    if not keyword:
        print("未输入关键词")
        return

    max_results = input("最多采集多少篇? (默认10): ").strip()
    max_results = int(max_results) if max_results.isdigit() else 10

    print(f"\n搜索关键词: {keyword}")
    print(f"最多采集: {max_results} 篇")
    print("\n注意: 搜狗搜索可能遇到验证码，建议使用URL导入方式")

    confirm = input("\n确认继续? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return

    # 初始化
    db = Database(Config.DATABASE_PATH)
    collector = WeChatCollectorV2()

    print("\n正在搜索...")
    articles = collector.search_articles_sogou(keyword, max_results)

    if not articles:
        print("未搜索到文章或遇到验证码")
        return

    print(f"\n搜索到 {len(articles)} 篇文章")

    # 获取详细内容
    success_count = 0
    for i, article in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {article['title'][:40]}...")

        if db.article_exists(article['url']):
            print("  [跳过] 已存在")
            continue

        # 获取完整内容
        full_article = collector.fetch_article_from_url(article['url'])

        if full_article:
            article_id = db.insert_article(full_article)
            if article_id:
                print("  [成功]")
                success_count += 1
            else:
                print("  [失败] 保存失败")
        else:
            print("  [失败] 获取内容失败")

    print(f"\n采集完成! 成功 {success_count} 篇")

def main():
    print("\n微信文章采集工具\n")

    print("请选择采集方式:")
    print("1. 从文件导入URL (urls.txt)")
    print("2. 手动输入URL")
    print("3. 搜索并采集 (可能遇到验证码)")
    print("0. 退出")

    choice = input("\n请选择 (0-3): ").strip()

    if choice == '1':
        import_from_file()
    elif choice == '2':
        import_from_input()
    elif choice == '3':
        search_and_collect()
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查看数据库内容的工具脚本
"""

import sys
import os
import sqlite3

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def view_database(db_path):
    """查看数据库内容"""
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 统计信息
    cursor.execute("SELECT COUNT(*) as total FROM articles")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as analyzed FROM articles WHERE analysis IS NOT NULL")
    analyzed = cursor.fetchone()['analyzed']

    print("=" * 70)
    print(f"数据库: {db_path}")
    print("=" * 70)
    print(f"文章总数: {total}")
    print(f"已分析: {analyzed}")
    print(f"待分析: {total - analyzed}")
    print("=" * 70)

    # 文章列表
    cursor.execute("""
        SELECT id, title, account_name, publish_time,
               category, keywords,
               CASE WHEN analysis IS NOT NULL THEN 'Yes' ELSE 'No' END as has_analysis
        FROM articles
        ORDER BY publish_time DESC
    """)

    articles = cursor.fetchall()

    if articles:
        print("\n文章列表:\n")
        for article in articles:
            print(f"[{article['id']}] {article['title']}")
            print(f"    公众号: {article['account_name']}")
            print(f"    发布时间: {article['publish_time']}")

            if article['category']:
                print(f"    分类: {article['category']}")

            if article['keywords']:
                print(f"    关键词: {article['keywords']}")

            print(f"    已分析: {article['has_analysis']}")
            print()
    else:
        print("\n数据库为空")

    conn.close()

def view_article_detail(db_path, article_id):
    """查看文章详情"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    article = cursor.fetchone()

    if not article:
        print(f"未找到ID为 {article_id} 的文章")
        conn.close()
        return

    print("=" * 70)
    print(f"文章详情 [ID: {article['id']}]")
    print("=" * 70)
    print(f"\n标题: {article['title']}")
    print(f"作者: {article['author']}")
    print(f"公众号: {article['account_name']}")
    print(f"发布时间: {article['publish_time']}")
    print(f"URL: {article['url']}")

    if article['category']:
        print(f"\n分类: {article['category']}")

    if article['keywords']:
        print(f"关键词: {article['keywords']}")

    if article['summary']:
        print(f"\n摘要:\n{article['summary']}")

    if article['content']:
        print(f"\n内容预览:\n{article['content'][:500]}...")

    if article['analysis']:
        print(f"\n深度分析:\n{article['analysis']}")

    conn.close()

def main():
    print("\n数据库查看工具\n")

    # 检查可用的数据库
    databases = []
    if os.path.exists('data/demo.db'):
        databases.append(('data/demo.db', '演示数据库'))
    if os.path.exists('data/articles.db'):
        databases.append(('data/articles.db', '正式数据库'))

    if not databases:
        print("未找到数据库文件")
        print("请先运行 python demo.py 或 python main.py")
        return

    print("可用的数据库:")
    for i, (path, name) in enumerate(databases, 1):
        print(f"{i}. {name} ({path})")

    if len(databases) == 1:
        db_path = databases[0][0]
    else:
        choice = input(f"\n请选择数据库 (1-{len(databases)}): ").strip()
        try:
            db_path = databases[int(choice) - 1][0]
        except (ValueError, IndexError):
            print("无效选择")
            return

    print("\n操作选项:")
    print("1. 查看所有文章列表")
    print("2. 查看文章详情")
    print("0. 退出")

    choice = input("\n请选择操作 (0-2): ").strip()

    if choice == '1':
        view_database(db_path)
    elif choice == '2':
        view_database(db_path)
        article_id = input("\n请输入文章ID: ").strip()
        try:
            view_article_detail(db_path, int(article_id))
        except ValueError:
            print("无效的文章ID")
    elif choice == '0':
        print("退出")
    else:
        print("无效选项")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")

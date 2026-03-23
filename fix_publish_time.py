"""
修复数据库中缺失的发布时间
重新从URL获取文章并更新publish_time字段
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from collector.wechat_collector_v2 import WeChatCollectorV2
from config import Config
import time

def fix_publish_time():
    """修复缺失的发布时间"""
    db_path = 'data/demo.db' if os.path.exists('data/demo.db') else Config.DATABASE_PATH
    db = Database(db_path)
    collector = WeChatCollectorV2()

    # 获取所有发布时间为空的文章
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, title, url
        FROM articles
        WHERE publish_time IS NULL OR publish_time = ''
        LIMIT 50
    ''')

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    print(f"找到 {len(articles)} 篇缺失发布时间的文章")

    if not articles:
        print("所有文章都有发布时间，无需修复")
        return

    success_count = 0
    fail_count = 0

    for i, article in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] 处理: {article['title'][:50]}")
        print(f"URL: {article['url'][:80]}")

        try:
            # 重新获取文章
            fetched = collector.fetch_article_from_url(article['url'])

            if fetched and fetched.get('publish_time'):
                # 更新数据库
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE articles
                    SET publish_time = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (fetched['publish_time'], article['id']))
                conn.commit()
                conn.close()

                print(f"[OK] 成功更新发布时间: {fetched['publish_time']}")
                success_count += 1
            else:
                print("[FAIL] 未能获取发布时间")
                fail_count += 1

            # 延迟避免被封
            time.sleep(2)

        except Exception as e:
            print(f"[ERROR] 错误: {str(e)}")
            fail_count += 1
            continue

    print(f"\n修复完成！")
    print(f"成功: {success_count} 篇")
    print(f"失败: {fail_count} 篇")

if __name__ == '__main__':
    fix_publish_time()

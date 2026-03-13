#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import time
from config import Config
from utils.logger import setup_logger
from storage.database import Database
from collector.wechat_collector import WeChatCollector
from analyzer.content_analyzer import ContentAnalyzer

logger = setup_logger('main')

def collect_articles(db: Database, collector: WeChatCollector):
    """采集文章"""
    logger.info("=" * 50)
    logger.info("开始采集文章")
    logger.info("=" * 50)

    total_collected = 0

    for keyword in Config.SEARCH_KEYWORDS:
        logger.info(f"\n搜索关键词: {keyword}")

        articles = collector.search_articles(keyword, Config.MAX_ARTICLES_PER_SEARCH)

        for article in articles:
            url = article.get('url')

            # 检查是否已存在
            if db.article_exists(url):
                logger.info(f"文章已存在，跳过: {article.get('title')}")
                continue

            # 获取文章详细内容
            logger.info(f"正在获取文章内容: {article.get('title')}")
            content = collector.fetch_article_content(url)

            if content:
                article['content'] = content

                # 保存到数据库
                article_id = db.insert_article(article)

                if article_id:
                    logger.info(f"✓ 文章已保存 [ID: {article_id}]: {article.get('title')}")
                    total_collected += 1
                else:
                    logger.warning(f"✗ 保存失败: {article.get('title')}")

            time.sleep(2)  # 延迟避免被封

    logger.info(f"\n采集完成，共收集 {total_collected} 篇新文章")
    return total_collected

def analyze_articles(db: Database, analyzer: ContentAnalyzer):
    """分析文章"""
    logger.info("=" * 50)
    logger.info("开始分析文章")
    logger.info("=" * 50)

    unanalyzed = db.get_unanalyzed_articles(limit=50)

    if not unanalyzed:
        logger.info("没有待分析的文章")
        return 0

    logger.info(f"找到 {len(unanalyzed)} 篇待分析文章\n")

    analyzed_count = 0

    for article in unanalyzed:
        try:
            logger.info(f"分析文章 [ID: {article['id']}]: {article['title']}")

            result = analyzer.analyze_article(article)

            # 更新数据库
            db.update_analysis(
                article['id'],
                result['analysis'],
                result['summary'],
                result['keywords'],
                result['category']
            )

            logger.info(f"✓ 分析完成")
            logger.info(f"  分类: {result['category']}")
            logger.info(f"  关键词: {result['keywords']}")
            logger.info(f"  摘要: {result['summary'][:100]}...\n")

            analyzed_count += 1
            time.sleep(1)  # 避免API限流

        except Exception as e:
            logger.error(f"✗ 分析失败: {str(e)}\n")
            continue

    logger.info(f"分析完成，共分析 {analyzed_count} 篇文章")
    return analyzed_count

def generate_report(db: Database):
    """生成分析报告"""
    logger.info("=" * 50)
    logger.info("生成分析报告")
    logger.info("=" * 50)

    articles = db.get_all_articles(limit=100)

    if not articles:
        logger.info("暂无文章数据")
        return

    # 统计信息
    total = len(articles)
    analyzed = sum(1 for a in articles if a['analysis'])

    categories = {}
    for article in articles:
        if article['category']:
            categories[article['category']] = categories.get(article['category'], 0) + 1

    # 生成报告
    report = f"""
# 微信公众号文章分析报告

生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 统计概览

- 文章总数: {total}
- 已分析: {analyzed}
- 待分析: {total - analyzed}

## 分类统计

"""

    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        report += f"- {category}: {count}篇\n"

    report += "\n## 最新文章\n\n"

    for i, article in enumerate(articles[:10], 1):
        report += f"### {i}. {article['title']}\n\n"
        report += f"- 公众号: {article['account_name']}\n"
        report += f"- 发布时间: {article['publish_time']}\n"

        if article['category']:
            report += f"- 分类: {article['category']}\n"

        if article['keywords']:
            report += f"- 关键词: {article['keywords']}\n"

        if article['summary']:
            report += f"- 摘要: {article['summary']}\n"

        report += f"- 链接: {article['url']}\n\n"

    # 保存报告
    report_file = f"reports/report_{time.strftime('%Y%m%d_%H%M%S')}.md"
    import os
    os.makedirs('reports', exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"报告已生成: {report_file}")

def main():
    """主函数"""
    try:
        # 验证配置
        Config.validate()

        # 初始化组件
        db = Database(Config.DATABASE_PATH)
        collector = WeChatCollector()
        analyzer = ContentAnalyzer(Config.ANTHROPIC_API_KEY)

        logger.info("InfoHub 微信公众号信息收集系统")
        logger.info("=" * 50)

        # 显示菜单
        print("\n请选择操作：")
        print("1. 采集文章")
        print("2. 分析文章")
        print("3. 生成报告")
        print("4. 全流程执行（采集 -> 分析 -> 报告）")
        print("0. 退出")

        choice = input("\n请输入选项 (0-4): ").strip()

        if choice == '1':
            collect_articles(db, collector)
        elif choice == '2':
            analyze_articles(db, analyzer)
        elif choice == '3':
            generate_report(db)
        elif choice == '4':
            collect_articles(db, collector)
            analyze_articles(db, analyzer)
            generate_report(db)
        elif choice == '0':
            logger.info("退出程序")
            sys.exit(0)
        else:
            logger.warning("无效的选项")

    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()

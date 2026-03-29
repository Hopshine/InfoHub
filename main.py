#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse
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

def cmd_generate_news(db: Database, args):
    """CLI: 生成文章"""
    from scheduler.auto_scheduler import AutoScheduler
    scheduler = AutoScheduler(db)

    count = getattr(args, 'count', 5) or 5
    style = getattr(args, 'style', None) or Config.ARTICLE_STYLE

    # 先检查是否有未处理的热点，没有则先采集
    hotnews = db.get_unprocessed_hotnews(limit=1)
    if not hotnews:
        logger.info("没有未处理的热点新闻，先进行采集...")
        scheduler.collect_hotnews()

    articles = scheduler.generate_articles(count=count, style=style)
    if articles:
        print(f"\n生成了 {len(articles)} 篇文章：")
        for a in articles:
            print(f"  [ID:{a['id']}] {a['title']}")
    else:
        print("没有生成任何文章")


def cmd_publish_article(db: Database, args):
    """CLI: 发布文章"""
    from scheduler.auto_scheduler import AutoScheduler
    scheduler = AutoScheduler(db)

    article_id = getattr(args, 'article_id', None)
    publish_type = getattr(args, 'publish_type', 'draft') or 'draft'

    ids = [int(article_id)] if article_id else None
    results = scheduler.publish_drafts(
        article_ids=ids, publish_type=publish_type)

    if results:
        print(f"\n发布结果（{len(results)}篇）：")
        for r in results:
            print(f"  [ID:{r.get('article_id')}] {r['status']} - {r.get('result', '')}")
    else:
        print("没有可发布的文章")


def cmd_auto_run(db: Database, args):
    """CLI: 自动运行完整流程"""
    from scheduler.auto_scheduler import AutoScheduler
    scheduler = AutoScheduler(db)

    count = getattr(args, 'count', 5) or 5
    style = getattr(args, 'style', None) or Config.ARTICLE_STYLE
    auto_publish = getattr(args, 'auto_publish', False)

    result = scheduler.run_full_pipeline(
        generate_count=count, style=style, auto_publish=auto_publish)

    print(f"\n流程执行完毕：")
    print(f"  采集: {result['collect'].get('total', 0)}条热点")
    print(f"  生成: {len(result['generate'])}篇文章")
    if result['publish']:
        success = sum(1 for r in result['publish'] if r['status'] != 'failed')
        print(f"  发布: {success}/{len(result['publish'])}篇成功")


def cmd_list_drafts(db: Database, args):
    """CLI: 查看草稿"""
    drafts = db.get_draft_articles(limit=30)
    if not drafts:
        print("暂无草稿文章")
        return

    print(f"\n草稿文章（共{len(drafts)}篇）：")
    print("-" * 70)
    for d in drafts:
        keywords = d.get('keywords', '') or ''
        print(f"  [ID:{d['id']}] [{d.get('style', '')}] {d['title']}")
        print(f"         摘要: {(d.get('summary') or '')[:60]}...")
        if keywords:
            print(f"         关键词: {keywords}")
        print(f"         创建: {d.get('created_at', '')}")
        print()


def cmd_list_published(db: Database, args):
    """CLI: 查看发布记录"""
    records = db.get_publish_records(limit=30)
    if not records:
        print("暂无发布记录")
        return

    print(f"\n发布记录（共{len(records)}条）：")
    print("-" * 70)
    for r in records:
        title = r.get('article_title', '未知')
        print(f"  [ID:{r['id']}] [{r['status']}] {title}")
        print(f"         平台: {r.get('platform', '')} | 方式: {r.get('publish_type', '')}")
        if r.get('media_id'):
            print(f"         media_id: {r['media_id']}")
        print(f"         时间: {r.get('created_at', '')}")
        print()


def build_parser() -> argparse.ArgumentParser:
    """构建CLI参数解析器"""
    parser = argparse.ArgumentParser(
        description='InfoHub - 微信公众号信息收集与自动发布系统')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 交互式菜单（默认）
    subparsers.add_parser('menu', help='交互式菜单')

    # 生成文章
    gen_parser = subparsers.add_parser('generate', help='根据热点生成文章')
    gen_parser.add_argument(
        '-n', '--count', type=int, default=5, help='生成数量（默认5）')
    gen_parser.add_argument(
        '-s', '--style', choices=['news', 'comment', 'deep'],
        help='文章风格: news(资讯)/comment(评论)/deep(深度)')

    # 发布文章
    pub_parser = subparsers.add_parser('publish', help='发布文章到微信公众号')
    pub_parser.add_argument(
        '-i', '--article-id', type=int, help='指定文章ID，不指定则发布所有草稿')
    pub_parser.add_argument(
        '-t', '--publish-type', choices=['draft', 'publish'],
        default='draft', help='发布方式: draft(草稿箱)/publish(直接发布)')

    # 自动运行
    auto_parser = subparsers.add_parser('auto', help='自动运行完整流程')
    auto_parser.add_argument(
        '-n', '--count', type=int, default=5, help='生成数量')
    auto_parser.add_argument(
        '-s', '--style', choices=['news', 'comment', 'deep'],
        help='文章风格')
    auto_parser.add_argument(
        '--auto-publish', action='store_true', help='自动发布到草稿箱')

    # 查看草稿
    subparsers.add_parser('drafts', help='查看草稿文章列表')

    # 查看发布记录
    subparsers.add_parser('published', help='查看发布记录')

    # 兼容旧的 --flag 风格
    parser.add_argument('--generate-news', action='store_true',
                        help='生成文章（等同于 generate 命令）')
    parser.add_argument('--publish-article', action='store_true',
                        help='发布文章（等同于 publish 命令）')
    parser.add_argument('--auto-run', action='store_true',
                        help='自动运行（等同于 auto 命令）')
    parser.add_argument('--list-drafts', action='store_true',
                        help='查看草稿（等同于 drafts 命令）')
    parser.add_argument('--list-published', action='store_true',
                        help='查看发布记录（等同于 published 命令）')

    return parser


def main():
    """主函数 - 支持CLI命令和交互式菜单"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        # 初始化数据库（所有命令都需要）
        db = Database(Config.DATABASE_PATH)

        # 处理 --flag 风格的命令
        if args.generate_news:
            Config.validate()
            cmd_generate_news(db, args)
            return
        if args.publish_article:
            Config.validate_wechat()
            cmd_publish_article(db, args)
            return
        if args.auto_run:
            Config.validate()
            cmd_auto_run(db, args)
            return
        if args.list_drafts:
            cmd_list_drafts(db, args)
            return
        if args.list_published:
            cmd_list_published(db, args)
            return

        # 处理子命令
        if args.command == 'generate':
            Config.validate()
            cmd_generate_news(db, args)
        elif args.command == 'publish':
            Config.validate_wechat()
            cmd_publish_article(db, args)
        elif args.command == 'auto':
            Config.validate()
            cmd_auto_run(db, args)
        elif args.command == 'drafts':
            cmd_list_drafts(db, args)
        elif args.command == 'published':
            cmd_list_published(db, args)
        else:
            # 默认：交互式菜单
            interactive_menu(db)

    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True)
        sys.exit(1)


def interactive_menu(db: Database):
    """交互式菜单（保留原有功能）"""
    Config.validate()
    collector = WeChatCollector()
    analyzer = ContentAnalyzer()

    logger.info("InfoHub 微信公众号信息收集系统")
    logger.info("=" * 50)

    print("\n请选择操作：")
    print("1. 采集文章")
    print("2. 分析文章")
    print("3. 生成报告")
    print("4. 全流程执行（采集 -> 分析 -> 报告）")
    print("5. 生成公众号文章（基于热点）")
    print("6. 查看草稿文章")
    print("7. 查看发布记录")
    print("0. 退出")

    choice = input("\n请输入选项 (0-7): ").strip()

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
    elif choice == '5':
        cmd_generate_news(db, argparse.Namespace(count=5, style=None))
    elif choice == '6':
        cmd_list_drafts(db, argparse.Namespace())
    elif choice == '7':
        cmd_list_published(db, argparse.Namespace())
    elif choice == '0':
        logger.info("退出程序")
        sys.exit(0)
    else:
        logger.warning("无效的选项")

if __name__ == '__main__':
    main()

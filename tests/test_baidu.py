"""
百度热搜采集器测试脚本
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collector.baidu_trending import BaiduTrendingCollector


def test_basic_collection():
    """测试基本采集功能"""
    print("=" * 60)
    print("测试1: 采集百度热搜榜（前5条）")
    print("=" * 60)

    collector = BaiduTrendingCollector()
    results = collector.get_top_n(n=5, tab='realtime')

    if not results:
        print("X 采集失败，未获取到数据")
        return False

    print(f"\n√ 成功采集 {len(results)} 条热搜\n")

    for item in results:
        print(f"排名: {item['rank']}")
        print(f"标题: {item['title']}")
        print(f"链接: {item['url']}")
        print(f"热度标签: {item['hot_tag']}")
        print(f"分类: {item['category']}")
        print(f"置顶: {'是' if item['is_top'] else '否'}")
        print("-" * 60)

    return True


def test_multiple_boards():
    """测试多榜单采集"""
    print("\n" + "=" * 60)
    print("测试2: 采集多个榜单（每个榜单前3条）")
    print("=" * 60)

    collector = BaiduTrendingCollector()

    boards = ['realtime', 'finance', 'sports']
    board_names = {'realtime': '热搜榜', 'finance': '财经榜', 'sports': '体育榜'}

    for board in boards:
        print(f"\n【{board_names[board]}】")
        results = collector.get_top_n(n=3, tab=board)

        if results:
            for item in results:
                print(f"  {item['rank']}. {item['title']}")
        else:
            print(f"  X 采集失败")


def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 60)
    print("测试3: 错误处理（无效榜单）")
    print("=" * 60)

    collector = BaiduTrendingCollector(timeout=5)
    results = collector.collect(tab='invalid_board', limit=5)

    if not results:
        print("V 正确处理了无效榜单请求")
    else:
        print("! 意外获取到了数据")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("百度热搜采集器测试")
    print("=" * 60 + "\n")

    try:
        success = test_basic_collection()

        if success:
            test_multiple_boards()
            test_error_handling()

            print("\n" + "=" * 60)
            print("V 所有测试完成")
            print("=" * 60)
        else:
            print("\nX 基础测试失败，跳过其他测试")

    except KeyboardInterrupt:
        print("\n\n! 测试被用户中断")
    except Exception as e:
        print(f"\nX 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

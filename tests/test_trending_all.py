"""
统一测试脚本 - 依次测试百度、微博、知乎、抖音四个平台的热搜采集器
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.baidu_trending import BaiduTrendingCollector
from collector.weibo_trending import WeiboTrendingCollector
from collector.zhihu_trending import ZhihuTrendingCollector
from collector.douyin_trending import DouyinTrendingCollector


def test_platform(name, collector, top_n=5):
    """测试单个平台的采集器"""
    print(f"\n{'='*60}")
    print(f"  测试平台: {name}")
    print(f"{'='*60}")

    try:
        items = collector.collect(limit=top_n)

        if not items:
            print(f"  [警告] {name} 未获取到数据（可能是网络或反爬限制）")
            return False

        print(f"  成功获取 {len(items)} 条数据:\n")

        for item in items[:top_n]:
            rank = item.get('rank', '?')
            title = item.get('title', '未知')
            hot_value = item.get('hot_value', '-')
            url = item.get('url', '')

            print(f"  {rank:>3}. {title}")
            print(f"       热度: {hot_value}")
            print(f"       链接: {url}")

        return True

    except Exception as e:
        print(f"  [错误] {name} 测试失败: {e}")
        return False


def main():
    print("\n" + "#" * 60)
    print("#  InfoHub 热搜采集器统一测试")
    print("#" + "=" * 58 + "#")

    platforms = [
        ("百度热搜", BaiduTrendingCollector()),
        ("微博热搜", WeiboTrendingCollector()),
        ("知乎热榜", ZhihuTrendingCollector()),
        ("抖音热点", DouyinTrendingCollector()),
    ]

    results = {}
    for name, collector in platforms:
        success = test_platform(name, collector, top_n=5)
        results[name] = success

    # 汇总结果
    print(f"\n{'='*60}")
    print("  测试汇总")
    print(f"{'='*60}")

    for name, success in results.items():
        status = "成功" if success else "失败"
        icon = "[OK]" if success else "[FAIL]"
        print(f"  {icon} {name}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  总计: {passed}/{total} 个平台采集成功")
    print()


if __name__ == '__main__':
    main()

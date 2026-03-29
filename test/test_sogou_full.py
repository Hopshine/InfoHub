#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整测试搜狗微信搜索采集流程
"""

import requests
import sys
import io
import time
import re
from bs4 import BeautifulSoup

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_sogou_search():
    """测试搜狗微信搜索完整流程"""

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    print('=' * 60)
    print('搜狗微信搜索完整流程测试')
    print('=' * 60)

    # 步骤1: 访问首页获取Cookie
    print('\n[1/4] 访问首页获取Cookie...')
    try:
        r = session.get('https://weixin.sogou.com/', headers=headers, timeout=10)
        print(f'      状态码: {r.status_code}')
        print(f'      Cookie数: {len(session.cookies)}')
        time.sleep(1)
    except Exception as e:
        print(f'      失败: {e}')
        return

    # 步骤2: 搜索文章
    print('\n[2/4] 搜索关键词: AI日报...')
    try:
        headers['Referer'] = 'https://weixin.sogou.com/'
        r = session.get(
            'https://weixin.sogou.com/weixin',
            params={'type': 2, 'query': 'AI日报', 'ie': 'utf8'},
            headers=headers,
            timeout=15
        )

        print(f'      状态码: {r.status_code}')

        # 检查验证码
        if '验证码' in r.text or 'antispider' in r.text:
            print('      ✗ 遇到验证码')
            return

        # 解析搜索结果
        soup = BeautifulSoup(r.text, 'lxml')
        news_list = soup.find('ul', class_='news-list')

        if not news_list:
            print('      ✗ 未找到搜索结果')
            return

        items = news_list.find_all('li')
        print(f'      ✓ 搜索到 {len(items)} 篇文章')

        # 获取第一篇
        first_item = items[0]
        a = first_item.find('h3').find('a')
        title = a.get_text(strip=True)
        href = a.get('href', '')

        if not href.startswith('http'):
            href = 'https://weixin.sogou.com' + href

        print(f'\n      第一篇: {title[:50]}...')
        print(f'      跳转链接: {href[:80]}...')

    except Exception as e:
        print(f'      失败: {e}')
        return

    # 步骤3: 获取真实URL
    print('\n[3/4] 解析跳转链接获取真实URL...')
    try:
        time.sleep(2)
        headers['Referer'] = 'https://weixin.sogou.com/weixin'
        r2 = session.get(href, headers=headers, timeout=15, allow_redirects=True)

        print(f'      状态码: {r2.status_code}')

        # 从JS中拼接URL
        pattern = r"url\s*\+=\s*['\"]([^'\"]+)['\"]"
        matches = re.findall(pattern, r2.text)

        if matches:
            real_url = ''.join(matches).replace('@', '')
            print(f'      ✓ 成功拼接URL')
            print(f'      真实URL: {real_url[:80]}...')

            if 'mp.weixin.qq.com' not in real_url:
                print('      ✗ 不是微信URL')
                return
        else:
            print('      ✗ 未找到URL')
            return

    except Exception as e:
        print(f'      失败: {e}')
        return

    # 步骤4: 获取文章内容
    print('\n[4/4] 获取文章内容...')
    try:
        time.sleep(2)
        r3 = session.get(
            real_url,
            headers={'User-Agent': headers['User-Agent']},
            timeout=20
        )
        r3.encoding = 'utf-8'

        print(f'      状态码: {r3.status_code}')

        soup2 = BeautifulSoup(r3.text, 'lxml')

        # 提取标题
        title_elem = soup2.find('h1', id='activity-name')
        if not title_elem:
            title_elem = soup2.find('h1', class_='rich_media_title')
        article_title = title_elem.get_text(strip=True) if title_elem else '未找到'

        # 提取公众号
        account_elem = soup2.find('strong', class_='profile_nickname')
        if not account_elem:
            account_elem = soup2.find('a', id='js_name')
        account_name = account_elem.get_text(strip=True) if account_elem else '未找到'

        # 提取内容
        content_div = soup2.find('div', id='js_content')
        content = ''
        if content_div:
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()
            content = content_div.get_text(separator='\n', strip=True)

        print(f'\n      ✓ 采集成功!')
        print(f'      标题: {article_title}')
        print(f'      公众号: {account_name}')
        print(f'      内容长度: {len(content)} 字符')

        if content:
            print(f'\n      内容预览:')
            print(f'      {content[:200]}...')
        else:
            print(f'      ✗ 内容为空')

    except Exception as e:
        print(f'      失败: {e}')
        return

    print('\n' + '=' * 60)
    print('测试完成！搜狗微信搜索采集流程正常工作')
    print('=' * 60)

if __name__ == '__main__':
    try:
        test_sogou_search()
    except KeyboardInterrupt:
        print('\n\n测试被中断')
    except Exception as e:
        print(f'\n错误: {e}')
        import traceback
        traceback.print_exc()

"""重新评分所有agent文章 - 基于传播力和互动性"""
import sqlite3, json

conn = sqlite3.connect('data/demo.db')
cursor = conn.cursor()

cursor.execute('SELECT id, title, content, keywords, summary FROM agent_articles')
rows = cursor.fetchall()
print(f'重新评分 {len(rows)} 篇文章...')

for row in rows:
    aid, title, content, keywords, summary = row
    title = title or ''
    content = content or ''
    keywords = keywords or ''
    summary = summary or ''

    score_details = []
    total_score = 0.0

    # 1. 标题吸引力 (0-25分)
    title_len = len(title)
    title_score = 0

    if title_len < 10:
        score_details.append({'item': '标题吸引力', 'score': 0, 'reason': f'标题过短({title_len}字)，缺乏信息量'})
    elif title_len > 50:
        title_score = 8
        score_details.append({'item': '标题吸引力', 'score': 8, 'reason': f'标题过长({title_len}字)，不够精炼'})
    else:
        title_score = 15

    hook_words = ['暴涨', '暴跌', '突破', '首次', '曝光', '揭秘', '真相', '内幕', '竟然', '居然', '没想到', '震惊', '重磅']
    conflict_words = ['vs', '对决', '反击', '回应', '质疑', '争议', '翻车']
    number_pattern = any(c.isdigit() for c in title)
    question_pattern = '?' in title or '？' in title or '吗' in title or '呢' in title

    if any(w in title for w in hook_words):
        title_score += 5
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含吸睛词汇，长度{title_len}字'})
    elif any(w in title for w in conflict_words):
        title_score += 4
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含冲突元素，长度{title_len}字'})
    elif number_pattern:
        title_score += 3
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'包含具体数字，长度{title_len}字'})
    elif question_pattern:
        title_score += 3
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'疑问式标题，长度{title_len}字'})
    else:
        score_details.append({'item': '标题吸引力', 'score': title_score, 'reason': f'标题平淡，缺乏钩子，长度{title_len}字'})

    total_score += min(title_score, 25)

    # 2. 开篇吸引力 (0-20分)
    first_100 = content[:100] if len(content) >= 100 else content
    opening_score = 10

    if any(w in first_100 for w in ['最近', '今天', '刚刚', '突发', '紧急']):
        opening_score += 5
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇有时效性，能快速抓住注意力'})
    elif '?' in first_100 or '？' in first_100:
        opening_score += 4
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇设置悬念，引发好奇'})
    elif any(c.isdigit() for c in first_100):
        opening_score += 3
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇有具体数据，增强可信度'})
    else:
        score_details.append({'item': '开篇吸引力', 'score': opening_score, 'reason': '开篇平淡，缺乏冲击力'})

    total_score += min(opening_score, 20)

    # 3. 内容可读性 (0-20分)
    content_len = len(content)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    para_count = len(paragraphs)

    if content_len < 500:
        score_details.append({'item': '内容可读性', 'score': 0, 'reason': f'内容过短({content_len}字)，信息量不足'})
    elif content_len > 3000:
        total_score += 10
        score_details.append({'item': '内容可读性', 'score': 10, 'reason': f'内容过长({content_len}字)，可能导致读者流失'})
    elif 800 <= content_len <= 2000:
        total_score += 20
        score_details.append({'item': '内容可读性', 'score': 20, 'reason': f'长度适中({content_len}字)，{para_count}段，易读完'})
    else:
        total_score += 15
        score_details.append({'item': '内容可读性', 'score': 15, 'reason': f'长度可接受({content_len}字)，{para_count}段'})

    # 4. 情绪共鸣 (0-15分)
    emotion_positive = ['感动', '温暖', '励志', '正能量', '点赞', '支持', '加油', '厉害']
    emotion_negative = ['愤怒', '气愤', '可恶', '无语', '离谱', '荒唐', '过分']
    emotion_surprise = ['震惊', '意外', '没想到', '竟然', '居然', '惊呆', '惊讶']

    emotion_score = 0
    if any(w in content for w in emotion_surprise):
        emotion_score = 15
        score_details.append({'item': '情绪共鸣', 'score': 15, 'reason': '内容有反转/意外，易引发传播'})
    elif any(w in content for w in emotion_negative):
        emotion_score = 12
        score_details.append({'item': '情绪共鸣', 'score': 12, 'reason': '内容引发负面情绪，有讨论价值'})
    elif any(w in content for w in emotion_positive):
        emotion_score = 10
        score_details.append({'item': '情绪共鸣', 'score': 10, 'reason': '内容传递正能量，有分享价值'})
    else:
        emotion_score = 5
        score_details.append({'item': '情绪共鸣', 'score': 5, 'reason': '内容平淡，缺乏情绪触点'})

    total_score += emotion_score

    # 5. 互动潜力 (0-10分)
    interactive_score = 0
    question_count = content.count('?') + content.count('？')

    if '你怎么看' in content or '你觉得' in content or '你认为' in content:
        interactive_score = 10
        score_details.append({'item': '互动潜力', 'score': 10, 'reason': '直接引导读者发表观点'})
    elif question_count >= 2:
        interactive_score = 8
        score_details.append({'item': '互动潜力', 'score': 8, 'reason': f'包含{question_count}个疑问，引发思考'})
    elif '评论区' in content or '留言' in content:
        interactive_score = 7
        score_details.append({'item': '互动潜力', 'score': 7, 'reason': '引导读者互动'})
    else:
        interactive_score = 3
        score_details.append({'item': '互动潜力', 'score': 3, 'reason': '缺少互动引导'})

    total_score += interactive_score

    # 6. 传播价值 (0-10分)
    share_score = 5
    if keywords:
        kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
        if len(kw_list) >= 3:
            share_score = 10
            score_details.append({'item': '传播价值', 'score': 10, 'reason': f'关键词丰富({len(kw_list)}个)，利于搜索传播'})
        else:
            share_score = 7
            score_details.append({'item': '传播价值', 'score': 7, 'reason': f'关键词偏少({len(kw_list)}个)'})
    else:
        score_details.append({'item': '传播价值', 'score': 5, 'reason': '缺少关键词，不利于传播'})

    total_score += share_score

    final_score = round(total_score / 100, 2)

    detail = json.dumps({
        'total_score': total_score,
        'final_score': final_score,
        'details': score_details,
        'metrics': {
            'title_length': title_len,
            'content_length': content_len,
            'paragraph_count': para_count,
            'keyword_count': len([k.strip() for k in keywords.split(',') if k.strip()]),
            'summary_length': len(summary),
            'question_count': question_count
        }
    }, ensure_ascii=False)

    cursor.execute('UPDATE agent_articles SET quality_score = ?, quality_detail = ? WHERE id = ?',
                   (final_score, detail, aid))

conn.commit()
conn.close()
print('Done')

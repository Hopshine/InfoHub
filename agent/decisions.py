"""
Agent决策模块 - 在pipeline各阶段插入智能决策点
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional


def log_decision(agent_state: Dict, stage: str, decision: str, reason: str, action: Optional[str] = None):
    """记录决策到agent_state"""
    if 'decisions' not in agent_state:
        agent_state['decisions'] = []

    decision_record = {
        'timestamp': datetime.now().isoformat(),
        'stage': stage,
        'decision': decision,
        'reason': reason,
        'action': action,
        'type': 'pass' if action is None else 'adjust'
    }
    agent_state['decisions'].append(decision_record)


def _add_dynamic_node(agent_state, key, label, status='running'):
    """动态添加节点到stages和nodes"""
    if 'stages' not in agent_state:
        agent_state['stages'] = {}
    agent_state['stages'][key] = {
        'status': status,
        'total_tasks': 0,
        'completed_tasks': 0,
        'failed_tasks': 0,
    }
    if 'nodes' not in agent_state:
        agent_state['nodes'] = {}
    agent_state['nodes'][key] = {
        'status': status,
        'count': 0,
        'label': label,
    }


async def decision_scan_sufficient(scan_results: List[Dict], agent_state: Dict) -> bool:
    total_count = len(scan_results)
    if total_count < 5:
        log_decision(agent_state, 'scan', 'insufficient',
                     f'仅扫描到{total_count}个热点，低于阈值5', 'retry_scan')
        _add_dynamic_node(agent_state, 'retry_scan', '扩大搜索')
        return False
    log_decision(agent_state, 'scan', 'sufficient',
                 f'扫描到{total_count}个热点，满足要求', None)
    return True


async def decision_enough_valuable(evaluated: List[Dict], agent_state: Dict) -> List[Dict]:
    high_value = [t for t in evaluated if t.get('score', 0) >= 70]
    medium_value = [t for t in evaluated if 50 <= t.get('score', 0) < 70]

    if len(high_value) >= 3:
        selected = high_value[:5]
        log_decision(agent_state, 'evaluate', 'select_high_value',
                     f'发现{len(high_value)}个高价值话题，选取前5个', None)
    elif len(high_value) + len(medium_value) >= 3:
        selected = (high_value + medium_value)[:5]
        log_decision(agent_state, 'evaluate', 'select_mixed',
                     f'高价值{len(high_value)}个+中等{len(medium_value)}个，混合选取', None)
    else:
        selected = evaluated[:3]
        log_decision(agent_state, 'evaluate', 'select_best_available',
                     f'可用话题不足，选取评分最高的{len(selected)}个', 'lower_threshold')
    return selected


async def decision_collect_complete(collected: List[Dict], expected_count: int, agent_state: Dict) -> bool:
    actual_count = len(collected)
    if actual_count < expected_count * 0.5:
        log_decision(agent_state, 'collect', 'incomplete',
                     f'仅采集到{actual_count}/{expected_count}个话题的素材，低于50%', 'retry_collect')
        _add_dynamic_node(agent_state, 'retry_collect', '补充采集')
        return False
    log_decision(agent_state, 'collect', 'complete',
                 f'采集到{actual_count}/{expected_count}个话题的素材', None)
    return True


async def decision_analysis_depth(analyzed: List[Dict], agent_state: Dict) -> str:
    deep = [a for a in analyzed if len(str(a.get('_analysis', ''))) >= 100]
    if len(deep) >= len(analyzed) * 0.7:
        log_decision(agent_state, 'analyze', 'depth_sufficient',
                     f'{len(deep)}/{len(analyzed)}个话题有深度分析', None)
        return 'sufficient'
    else:
        log_decision(agent_state, 'analyze', 'depth_shallow',
                     f'仅{len(deep)}/{len(analyzed)}个话题有深度分析', 'enhance_analysis')
        _add_dynamic_node(agent_state, 'retry_analyze', '补充分析')
        return 'shallow'


async def decision_angles_sufficient(planned: List[Dict], agent_state: Dict) -> bool:
    good = [p for p in planned if len(p.get('angles', [])) >= 2]
    if len(good) >= len(planned) * 0.5:
        log_decision(agent_state, 'plan', 'angles_sufficient',
                     f'{len(good)}/{len(planned)}个话题有充足角度', None)
        return True
    log_decision(agent_state, 'plan', 'angles_insufficient',
                 f'仅{len(good)}/{len(planned)}个话题有充足角度', 'generate_more_angles')
    return False


async def decision_write_precheck(content: str, title: str, agent_state: Dict) -> Dict:
    word_count = len(content)
    if word_count < 500:
        log_decision(agent_state, 'write', 'content_too_short',
                     f'"{title[:20]}"仅{word_count}字，低于500字', 'expand_content')
        return {'action': 'expand', 'reason': f'内容过短({word_count}字)'}
    if word_count > 3000:
        log_decision(agent_state, 'write', 'content_too_long',
                     f'"{title[:20]}"有{word_count}字，超过3000字', 'trim_content')
        return {'action': 'trim', 'reason': f'内容过长({word_count}字)'}
    log_decision(agent_state, 'write', 'content_length_ok',
                 f'"{title[:20]}"{word_count}字，长度合适', None)
    return {'action': 'pass'}


async def decision_quality_routing(article: Dict, score: float, details: List, agent_state: Dict) -> Dict:
    title = article.get('title', '')[:20]
    score_int = int(score * 100)

    if score_int >= 70:
        log_decision(agent_state, 'check', 'quality_good',
                     f'"{title}"得分{score_int}，质量良好', None)
        return {'action': 'save', 'reason': 'quality_good'}

    if score_int >= 50:
        low_items = [d for d in details if d.get('score', 0) < d.get('max_score', 10) * 0.5]
        suggestions = '、'.join([d['item'] for d in low_items[:3]])
        retry_count = article.get('_retry_count', 0)
        if retry_count < 1:
            log_decision(agent_state, 'check', 'quality_mediocre',
                         f'"{title}"得分{score_int}，需优化：{suggestions}', 'optimize')
            _add_dynamic_node(agent_state, 'optimize', '自动优化')
            return {'action': 'optimize', 'reason': f'需优化：{suggestions}', 'weak_items': low_items}
        else:
            log_decision(agent_state, 'check', 'quality_mediocre_accept',
                         f'"{title}"得分{score_int}，已优化过，接受', None)
            return {'action': 'save', 'reason': 'optimized_once'}

    retry_count = article.get('_retry_count', 0)
    if retry_count < 1:
        log_decision(agent_state, 'check', 'quality_poor',
                     f'"{title}"得分{score_int}，质量差，重写', 'rewrite')
        _add_dynamic_node(agent_state, 'retry_write', '重新生成')
        return {'action': 'rewrite', 'reason': 'quality_poor'}
    else:
        log_decision(agent_state, 'check', 'quality_poor_abandon',
                     f'"{title}"得分{score_int}，已重写过仍不达标，放弃', 'abandon')
        return {'action': 'abandon', 'reason': 'quality_unacceptable'}


async def decision_post_optimize(original_score: float, new_score: float, title: str, agent_state: Dict) -> bool:
    improvement = (new_score - original_score) * 100
    if new_score >= 0.6:
        log_decision(agent_state, 'optimize', 'improvement_ok',
                     f'"{title[:20]}"优化后{int(new_score*100)}分(+{improvement:.0f})', None)
        return True
    log_decision(agent_state, 'optimize', 'no_improvement',
                 f'"{title[:20]}"优化后{int(new_score*100)}分，仍不达标', 'abandon')
    return False

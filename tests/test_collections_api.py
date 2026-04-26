import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_app import app, db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_articles():
    """创建测试用的文章"""
    article_ids = []
    for i in range(10):
        article_id = db.insert_generated_article({
            'title': f'测试文章{i+1}',
            'content': f'这是测试文章{i+1}的内容',
            'summary': f'摘要{i+1}',
            'keywords': f'关键词{i+1}',
            'status': 'draft'
        })
        if article_id:
            article_ids.append(article_id)
    yield article_ids
    # 清理
    for aid in article_ids:
        db.delete_generated_article(aid)


class TestCollectionsAPI:
    """合集API集成测试"""

    def test_create_collection_success(self, client, sample_articles):
        """测试创建合集成功（2-8篇）"""
        response = client.post('/api/collections', json={
            'title': '测试合集',
            'description': '这是一个测试合集',
            'article_ids': sample_articles[:5],
            'status': 'draft'
        })
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'id' in data['data']
        collection_id = data['data']['id']
        db.delete_article_collection(collection_id)

    def test_create_collection_too_few(self, client, sample_articles):
        """测试创建合集失败（少于2篇）"""
        response = client.post('/api/collections', json={
            'title': '测试合集',
            'article_ids': sample_articles[:1]
        })
        data = json.loads(response.data)
        assert data['success'] is False
        assert '2-8篇' in data['error']

    def test_create_collection_too_many(self, client, sample_articles):
        """测试创建合集失败（超过8篇）"""
        response = client.post('/api/collections', json={
            'title': '测试合集',
            'article_ids': sample_articles[:9]
        })
        data = json.loads(response.data)
        assert data['success'] is False
        assert '2-8篇' in data['error']

    def test_create_collection_article_not_exist(self, client, sample_articles):
        """测试创建合集失败（文章不存在）"""
        response = client.post('/api/collections', json={
            'title': '测试合集',
            'article_ids': [99999, 99998]
        })
        data = json.loads(response.data)
        assert data['success'] is False
        assert '不存在' in data['error']

    def test_get_collections(self, client, sample_articles):
        """测试获取合集列表"""
        collection_id = db.create_article_collection({
            'title': '测试合集',
            'article_ids': sample_articles[:3],
            'article_count': 3,
            'status': 'draft'
        })
        response = client.get('/api/collections')
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']) > 0
        db.delete_article_collection(collection_id)

    def test_get_collection_detail(self, client, sample_articles):
        """测试获取合集详情"""
        collection_id = db.create_article_collection({
            'title': '测试合集',
            'article_ids': sample_articles[:3],
            'article_count': 3,
            'status': 'draft'
        })
        response = client.get(f'/api/collections/{collection_id}')
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == collection_id
        assert len(data['data']['articles']) == 3
        db.delete_article_collection(collection_id)

    def test_update_collection(self, client, sample_articles):
        """测试更新合集"""
        collection_id = db.create_article_collection({
            'title': '测试合集',
            'article_ids': sample_articles[:3],
            'article_count': 3,
            'status': 'draft'
        })
        response = client.put(f'/api/collections/{collection_id}', json={
            'title': '更新后的标题',
            'article_ids': sample_articles[:4]
        })
        data = json.loads(response.data)
        assert data['success'] is True
        db.delete_article_collection(collection_id)

    def test_delete_collection(self, client, sample_articles):
        """测试删除合集"""
        collection_id = db.create_article_collection({
            'title': '测试合集',
            'article_ids': sample_articles[:3],
            'article_count': 3,
            'status': 'draft'
        })
        response = client.delete(f'/api/collections/{collection_id}')
        data = json.loads(response.data)
        assert data['success'] is True

    def test_preview_collection(self, client, sample_articles):
        """测试预览合集HTML"""
        collection_id = db.create_article_collection({
            'title': '测试合集',
            'article_ids': sample_articles[:3],
            'article_count': 3,
            'status': 'draft'
        })
        response = client.post(f'/api/collections/{collection_id}/preview')
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'html' in data['data']
        assert data['data']['article_count'] == 3
        db.delete_article_collection(collection_id)

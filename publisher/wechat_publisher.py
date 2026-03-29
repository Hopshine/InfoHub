"""
微信公众号发布器 - 通过官方API发布文章到微信公众号
支持：草稿箱发布、直接发布、素材上传
"""
import time
import json
import requests
from typing import Dict, Optional, List
from datetime import datetime
from utils.logger import setup_logger
from config import Config

logger = setup_logger('publisher')


class WeChatPublisher:
    """微信公众号文章发布器"""

    BASE_URL = 'https://api.weixin.qq.com/cgi-bin'

    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or Config.WECHAT_APP_ID
        self.app_secret = app_secret or Config.WECHAT_APP_SECRET
        self._access_token = None
        self._token_expires_at = 0
        self.max_retries = 3
        self.retry_delay = 2  # 秒

    def _get_access_token(self) -> str:
        """获取access_token，带缓存"""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        url = f'{self.BASE_URL}/token'
        params = {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret,
        }

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if 'access_token' not in data:
            errcode = data.get('errcode', 'unknown')
            errmsg = data.get('errmsg', 'unknown')
            raise RuntimeError(f"获取access_token失败: [{errcode}] {errmsg}")

        self._access_token = data['access_token']
        # 提前5分钟过期，避免边界问题
        self._token_expires_at = now + data.get('expires_in', 7200) - 300
        logger.info("access_token获取成功")
        return self._access_token

    def _request_with_retry(self, method: str, url: str, **kwargs) -> Dict:
        """带重试的HTTP请求"""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.request(method, url, timeout=30, **kwargs)
                data = resp.json()

                # access_token过期，刷新后重试
                if data.get('errcode') in (40001, 40014, 42001):
                    logger.warning(f"access_token已过期，刷新重试 (第{attempt}次)")
                    self._access_token = None
                    self._token_expires_at = 0
                    token = self._get_access_token()
                    # 替换URL中的token
                    if 'access_token=' in url:
                        url = url.split('access_token=')[0] + f'access_token={token}'
                    continue

                if data.get('errcode', 0) != 0:
                    errcode = data.get('errcode')
                    errmsg = data.get('errmsg', '')
                    logger.error(f"微信API错误: [{errcode}] {errmsg}")

                return data

            except requests.RequestException as e:
                last_error = e
                logger.warning(f"请求失败 (第{attempt}次): {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)

        raise RuntimeError(f"请求失败，已重试{self.max_retries}次: {last_error}")

    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片素材，返回media_id"""
        token = self._get_access_token()
        url = f'{self.BASE_URL}/media/uploadimg?access_token={token}'

        try:
            with open(image_path, 'rb') as f:
                files = {'media': f}
                data = self._request_with_retry('POST', url, files=files)

            if data.get('url'):
                logger.info(f"图片上传成功: {data['url']}")
                return data['url']
            return None
        except FileNotFoundError:
            logger.error(f"图片文件不存在: {image_path}")
            return None

    def upload_thumb(self, image_path: str) -> Optional[str]:
        """上传封面图（永久素材），返回thumb_media_id"""
        token = self._get_access_token()
        url = f'{self.BASE_URL}/material/add_material?access_token={token}&type=thumb'

        try:
            with open(image_path, 'rb') as f:
                files = {'media': f}
                data = self._request_with_retry('POST', url, files=files)

            media_id = data.get('media_id')
            if media_id:
                logger.info(f"封面图上传成功: {media_id}")
            return media_id
        except FileNotFoundError:
            logger.error(f"封面图文件不存在: {image_path}")
            return None

    def _build_article_item(self, article: Dict, thumb_media_id: str = '') -> Dict:
        """构建文章数据结构"""
        return {
            'title': article.get('title', ''),
            'thumb_media_id': thumb_media_id,
            'author': article.get('author', 'InfoHub'),
            'digest': article.get('summary', '')[:120],
            'content': article.get('content', ''),
            'content_source_url': article.get('source_url', ''),
            'need_open_comment': 0,
            'only_fans_can_comment': 0,
        }

    def add_draft(self, articles: List[Dict],
                  thumb_media_id: str = '') -> Optional[str]:
        """添加草稿（推荐方式）

        Args:
            articles: 文章列表，每篇包含title/content/summary等字段
            thumb_media_id: 封面图media_id，为空则不设置封面

        Returns:
            media_id: 草稿的media_id，失败返回None
        """
        token = self._get_access_token()
        url = f'{self.BASE_URL}/draft/add?access_token={token}'

        article_items = [
            self._build_article_item(a, thumb_media_id) for a in articles
        ]

        payload = {'articles': article_items}
        data = self._request_with_retry('POST', url, json=payload)

        media_id = data.get('media_id')
        if media_id:
            logger.info(f"草稿创建成功: media_id={media_id}")
        else:
            logger.error(f"草稿创建失败: {data}")
        return media_id

    def publish_draft(self, media_id: str) -> Optional[str]:
        """发布草稿（群发）

        Args:
            media_id: 草稿的media_id

        Returns:
            publish_id: 发布任务ID
        """
        token = self._get_access_token()
        url = f'{self.BASE_URL}/freepublish/submit?access_token={token}'

        payload = {'media_id': media_id}
        data = self._request_with_retry('POST', url, json=payload)

        publish_id = data.get('publish_id')
        if publish_id:
            logger.info(f"发布任务已提交: publish_id={publish_id}")
        else:
            logger.error(f"发布失败: {data}")
        return publish_id

    def get_publish_status(self, publish_id: str) -> Dict:
        """查询发布状态"""
        token = self._get_access_token()
        url = f'{self.BASE_URL}/freepublish/get?access_token={token}'

        payload = {'publish_id': publish_id}
        return self._request_with_retry('POST', url, json=payload)

    def publish_article(self, article: Dict, db=None,
                        publish_type: str = 'draft',
                        thumb_media_id: str = '') -> Dict:
        """发布单篇文章的完整流程

        Args:
            article: 文章数据（含title/content/summary）
            db: 数据库实例，用于记录发布状态
            publish_type: 'draft'(仅存草稿) 或 'publish'(草稿+发布)
            thumb_media_id: 封面图media_id

        Returns:
            发布结果字典
        """
        result = {
            'article_id': article.get('id'),
            'platform': 'wechat',
            'publish_type': publish_type,
            'status': 'pending',
            'media_id': '',
            'result': '',
            'published_at': '',
        }

        try:
            # 1. 创建草稿
            media_id = self.add_draft([article], thumb_media_id)
            if not media_id:
                result['status'] = 'failed'
                result['result'] = '草稿创建失败'
                self._save_record(db, result)
                return result

            result['media_id'] = media_id
            result['status'] = 'draft'
            result['result'] = '草稿创建成功'

            # 2. 如果需要直接发布
            if publish_type == 'publish':
                publish_id = self.publish_draft(media_id)
                if publish_id:
                    result['status'] = 'published'
                    result['result'] = json.dumps({
                        'media_id': media_id,
                        'publish_id': publish_id,
                    })
                    result['published_at'] = datetime.now().isoformat()
                else:
                    result['status'] = 'draft'
                    result['result'] = '草稿已创建，但发布失败'

            self._save_record(db, result)
            return result

        except Exception as e:
            logger.error(f"发布流程异常: {e}")
            result['status'] = 'failed'
            result['result'] = str(e)
            self._save_record(db, result)
            return result

    def _save_record(self, db, record: Dict):
        """保存发布记录到数据库"""
        if db is None:
            return
        try:
            record_id = db.insert_publish_record(record)
            if record_id:
                # 更新文章状态
                article_id = record.get('article_id')
                if article_id and record['status'] == 'published':
                    db.update_generated_article_status(article_id, 'published')
                elif article_id and record['status'] == 'draft':
                    db.update_generated_article_status(article_id, 'submitted')
        except Exception as e:
            logger.error(f"保存发布记录失败: {e}")

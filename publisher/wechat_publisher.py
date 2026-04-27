"""
微信公众号发布器 - 通过官方API发布文章到微信公众号
支持：草稿箱发布、直接发布、素材上传
"""
import os
import time
import json
import requests
import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime
from utils.logger import setup_logger
from config import Config

logger = setup_logger('publisher')


class WeChatPublisher:
    """微信公众号文章发布器"""

    BASE_URL = 'https://api.weixin.qq.com/cgi-bin'

    def __init__(self, app_id: str = None, app_secret: str = None, db=None):
        self.app_id = app_id or Config.WECHAT_APP_ID
        self.app_secret = app_secret or Config.WECHAT_APP_SECRET
        self.db = db
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
        # 将 json= 参数转为 data= 显式编码，确保中文不被转义为 \uXXXX
        if 'json' in kwargs:
            payload = kwargs.pop('json')
            kwargs['data'] = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            kwargs.setdefault('headers', {})['Content-Type'] = 'application/json; charset=utf-8'

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

    def upload_image_with_cache(self, image_path: str) -> Optional[Dict]:
        """上传图片并使用缓存（返回url和media_id）"""
        if not self.db:
            return self._upload_image_direct(image_path)

        # 先尝试从缓存获取
        cache = self.db.get_wechat_media_cache(image_path)
        if cache:
            logger.info(f"使用缓存的图片: {image_path}")
            return {'url': cache['url'], 'media_id': cache['media_id']}

        # 缓存未命中，上传图片
        result = self._upload_image_direct(image_path)
        if result and result.get('url'):
            # 保存到缓存
            self.db.save_wechat_media_cache(image_path, result['media_id'])
        return result

    def _upload_image_direct(self, image_path: str) -> Optional[Dict]:
        """直接上传图片（内部方法）"""
        token = self._get_access_token()
        url = f'{self.BASE_URL}/media/uploadimg?access_token={token}'

        try:
            with open(image_path, 'rb') as f:
                files = {'media': f}
                data = self._request_with_retry('POST', url, files=files)

            if data.get('url'):
                logger.info(f"图片上传成功: {data['url']}")
                return {'url': data['url'], 'media_id': data.get('media_id', '')}
            return None
        except FileNotFoundError:
            logger.error(f"图片文件不存在: {image_path}")
            return None

    async def _upload_image_async(self, session: aiohttp.ClientSession,
                                   image_path: str, token: str) -> Dict:
        """异步上传单张图片"""
        url = f'{self.BASE_URL}/media/uploadimg?access_token={token}'
        try:
            with open(image_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('media', f, filename=image_path.split('/')[-1])
                async with session.post(url, data=data, timeout=30) as resp:
                    result = await resp.json()
                    if result.get('url'):
                        return {
                            'success': True,
                            'path': image_path,
                            'url': result['url'],
                            'media_id': result.get('media_id', '')
                        }
                    return {
                        'success': False,
                        'path': image_path,
                        'error': result.get('errmsg', 'Unknown error')
                    }
        except Exception as e:
            return {'success': False, 'path': image_path, 'error': str(e)}

    def upload_images_batch(self, image_paths: List[str],
                           use_cache: bool = True) -> List[Dict]:
        """批量上传图片（并发上传，支持缓存）

        Args:
            image_paths: 图片路径列表
            use_cache: 是否使用缓存

        Returns:
            上传结果列表，每项包含success、path、url、media_id等字段
        """
        if not image_paths:
            return []

        results = []
        to_upload = []

        # 检查缓存
        if use_cache and self.db:
            for path in image_paths:
                cache = self.db.get_wechat_media_cache(path)
                if cache:
                    results.append({
                        'success': True,
                        'path': path,
                        'url': cache['url'],
                        'media_id': cache['media_id'],
                        'from_cache': True
                    })
                else:
                    to_upload.append(path)
        else:
            to_upload = image_paths

        # 并发上传未缓存的图片
        if to_upload:
            token = self._get_access_token()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                upload_results = loop.run_until_complete(
                    self._batch_upload_async(to_upload, token)
                )
                results.extend(upload_results)

                # 保存成功上传的到缓存
                if use_cache and self.db:
                    for r in upload_results:
                        if r['success']:
                            self.db.save_wechat_media_cache(r['path'], r['media_id'])
            finally:
                loop.close()

        return results

    async def _batch_upload_async(self, image_paths: List[str],
                                   token: str) -> List[Dict]:
        """异步批量上传"""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._upload_image_async(session, path, token)
                for path in image_paths
            ]
            return await asyncio.gather(*tasks)

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
        title = article.get('title', '')
        # 微信标题限制：UTF-8编码64字节（约21个汉字）
        title = self._truncate_by_bytes(title, max_bytes=64)

        digest = article.get('summary', '')
        # 摘要限制：120字节
        digest = self._truncate_by_bytes(digest, max_bytes=120)

        # 内容格式化：纯文本转HTML（换行符转<br>，段落用<p>包裹）
        content = article.get('content', '')
        content = self._format_content_to_html(content)

        return {
            'title': title,
            'thumb_media_id': thumb_media_id,
            'author': article.get('author', 'InfoHub'),
            'digest': digest,
            'content': content,
            'content_source_url': article.get('source_url', ''),
            'need_open_comment': 0,
            'only_fans_can_comment': 0,
        }

    @staticmethod
    def _format_content_to_html(text: str) -> str:
        """将纯文本格式化为HTML（保留段落和换行）"""
        if not text:
            return ''

        # 按段落分割（连续两个换行符）
        paragraphs = text.split('\n\n')

        # 每个段落用<p>包裹，段落内的单个换行符转<br>
        html_parts = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # 段落内的单个换行符转<br>
                para = para.replace('\n', '<br>')
                html_parts.append(f'<p>{para}</p>')

        return ''.join(html_parts)

    @staticmethod
    def _truncate_by_bytes(text: str, max_bytes: int) -> str:
        """按UTF-8字节数截断字符串，不切断多字节字符"""
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        # 从后往前找安全截断点
        truncated = encoded[:max_bytes]
        return truncated.decode('utf-8', errors='ignore')

    @staticmethod
    def _truncate_by_bytes(text: str, max_bytes: int) -> str:
        """按UTF-8字节数截断字符串，不切断多字节字符"""
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        # 从后往前找安全截断点
        truncated = encoded[:max_bytes]
        return truncated.decode('utf-8', errors='ignore')

    def add_draft(self, articles: List[Dict],
                  thumb_media_id: str = '') -> Optional[str]:
        """添加草稿（推荐方式）

        Args:
            articles: 文章列表，每篇包含title/content/summary等字段
            thumb_media_id: 封面图media_id，为空则使用默认封面

        Returns:
            media_id: 草稿的media_id，失败返回None
        """
        token = self._get_access_token()
        url = f'{self.BASE_URL}/draft/add?access_token={token}'

        # 如果没有提供封面图，上传默认封面
        if not thumb_media_id:
            default_cover = 'static/uploads/wechat/default_cover.jpg'
            if os.path.exists(default_cover):
                thumb_media_id = self.upload_thumb(default_cover)
                if not thumb_media_id:
                    logger.warning("默认封面图上传失败，尝试继续创建草稿")

        article_items = [
            self._build_article_item(a, thumb_media_id) for a in articles
        ]

        payload = {'articles': article_items}

        # 调试：打印所有文章标题和长度
        for i, item in enumerate(article_items):
            t = item.get('title', '')
            logger.info(f"草稿文章[{i}] title({len(t)}字): {t}")

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

    def publish_collection(self, collection_id: int, db,
                          publish_now: bool = False) -> Dict:
        """发布文章合集

        Args:
            collection_id: 合集ID
            db: 数据库实例
            publish_now: 是否立即群发

        Returns:
            发布结果字典
        """
        result = {
            'collection_id': collection_id,
            'status': 'pending',
            'media_id': '',
            'publish_id': '',
            'message': '',
            'articles_count': 0
        }

        try:
            # 1. 获取合集信息
            collection = db.get_article_collection(collection_id)
            if not collection:
                result['status'] = 'failed'
                result['message'] = '合集不存在'
                return result

            # 2. 获取文章列表
            article_ids = json.loads(collection['article_ids'])
            articles = []
            for aid in article_ids:
                article = db.get_generated_article_by_id(aid)
                if article:
                    articles.append(article)

            if not articles:
                result['status'] = 'failed'
                result['message'] = '合集中没有有效文章'
                return result

            result['articles_count'] = len(articles)

            # 3. 创建草稿（多图文消息）
            media_id = self.add_draft(articles)
            if not media_id:
                result['status'] = 'failed'
                result['message'] = '创建草稿失败'
                return result

            result['media_id'] = media_id
            result['status'] = 'draft'
            result['message'] = f'草稿创建成功，包含{len(articles)}篇文章'

            # 4. 如果需要立即发布
            if publish_now:
                publish_id = self.publish_draft(media_id)
                if publish_id:
                    result['status'] = 'published'
                    result['publish_id'] = publish_id
                    result['message'] = f'发布成功，包含{len(articles)}篇文章'
                else:
                    result['message'] = '草稿已创建，但发布失败'

            # 5. 更新合集状态
            db.update_article_collection(collection_id, {
                'status': 'published' if publish_now else 'submitted'
            })

            return result

        except Exception as e:
            logger.error(f"合集发布异常: {e}")
            result['status'] = 'failed'
            result['message'] = str(e)
            return result

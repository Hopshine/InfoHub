import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()

    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 文章表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                account_name TEXT,
                publish_time TEXT,
                url TEXT UNIQUE,
                content TEXT,
                summary TEXT,
                keywords TEXT,
                category TEXT,
                analysis TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_publish_time
            ON articles(publish_time)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_account_name
            ON articles(account_name)
        ''')

        # 新增字段（兼容已有数据库）
        try:
            cursor.execute('ALTER TABLE articles ADD COLUMN content_hash TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE articles ADD COLUMN source TEXT DEFAULT 'manual'")
        except sqlite3.OperationalError:
            pass

        # 采集任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT,
                params TEXT,
                status TEXT,
                total INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                succeeded INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                progress TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # 内容指纹索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_content_hash ON articles(content_hash)
        ''')

        # 热点数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                rank_num INTEGER,
                title TEXT NOT NULL,
                hot_value TEXT,
                url TEXT,
                label TEXT,
                extra TEXT,
                batch_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trending_platform
            ON trending(platform, created_at DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trending_batch
            ON trending(batch_id)
        ''')

        # 热点新闻表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hotnews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                hot_value TEXT,
                rank_num INTEGER,
                summary TEXT,
                batch_id TEXT,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hotnews_source
            ON hotnews(source, created_at DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hotnews_status
            ON hotnews(status)
        ''')

        # 生成文章表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generated_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotnews_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                keywords TEXT,
                style TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hotnews_id) REFERENCES hotnews(id)
            )
        ''')

        # 发布记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publish_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                platform TEXT DEFAULT 'wechat',
                media_id TEXT,
                publish_type TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                published_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES generated_articles(id)
            )
        ''')

        # 公众号配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wechat_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                app_id TEXT NOT NULL UNIQUE,
                app_secret TEXT NOT NULL,
                topic_keywords TEXT,
                style_preference TEXT,
                custom_prompt TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 工作流状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT UNIQUE,
                hotnews_id INTEGER,
                account_id INTEGER,
                current_node TEXT,
                state_data TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hotnews_id) REFERENCES hotnews(id),
                FOREIGN KEY (account_id) REFERENCES wechat_accounts(id)
            )
        ''')

        conn.commit()
        conn.close()

    def insert_article(self, article: Dict) -> Optional[int]:
        """插入文章记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO articles
                (title, author, account_name, publish_time, url, content, content_hash, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.get('title'),
                article.get('author'),
                article.get('account_name'),
                article.get('publish_time'),
                article.get('url'),
                article.get('content'),
                article.get('content_hash'),
                article.get('source', 'manual')
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def update_analysis(self, article_id: int, analysis: str, summary: str, keywords: str, category: str):
        """更新文章分析结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE articles
            SET analysis = ?, summary = ?, keywords = ?, category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (analysis, summary, keywords, category, article_id))

        conn.commit()
        conn.close()

    def get_unanalyzed_articles(self, limit: int = 10) -> List[Dict]:
        """获取未分析的文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM articles
            WHERE analysis IS NULL
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        articles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return articles

    def get_all_articles(self, limit: int = 100) -> List[Dict]:
        """获取所有文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM articles
            ORDER BY publish_time DESC
            LIMIT ?
        ''', (limit,))

        articles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return articles

    def article_exists(self, url: str) -> bool:
        """检查文章是否已存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT 1 FROM articles WHERE url = ?', (url,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def article_exists_by_hash(self, content_hash: str) -> bool:
        """通过内容指纹检查文章是否已存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM articles WHERE content_hash = ?', (content_hash,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def insert_crawl_job(self, job: Dict) -> str:
        """插入采集任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO crawl_jobs (id, job_type, params, status, total, completed, succeeded, failed, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job['id'], job['job_type'], job.get('params', '{}'),
            job.get('status', 'pending'), job.get('total', 0),
            job.get('completed', 0), job.get('succeeded', 0),
            job.get('failed', 0), job.get('progress', '[]'),
            job.get('created_at', datetime.now().isoformat()),
            job.get('updated_at', datetime.now().isoformat())
        ))
        conn.commit()
        conn.close()
        return job['id']

    def update_crawl_job(self, job_id: str, updates: Dict):
        """更新采集任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f'{key} = ?')
            values.append(value)
        set_clauses.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(job_id)
        cursor.execute(f'''
            UPDATE crawl_jobs SET {", ".join(set_clauses)} WHERE id = ?
        ''', values)
        conn.commit()
        conn.close()

    def get_crawl_job(self, job_id: str) -> Optional[Dict]:
        """获取采集任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM crawl_jobs WHERE id = ?', (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_article(self, article_id: int) -> bool:
        """删除单篇文章"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def delete_articles(self, article_ids: List[int]) -> int:
        """批量删除文章，返回删除数量"""
        if not article_ids:
            return 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in article_ids)
        cursor.execute(f'DELETE FROM articles WHERE id IN ({placeholders})', article_ids)
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count

    # ==================== 热点数据操作 ====================

    def save_trending(self, platform: str, items: list, batch_id: str):
        """保存热点数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for item in items:
            cursor.execute('''
                INSERT INTO trending (platform, rank_num, title, hot_value, url, label, extra, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                platform,
                item.get('rank', 0),
                item.get('title', ''),
                str(item.get('hot_value', '')),
                item.get('url', ''),
                item.get('label', ''),
                json.dumps({k: v for k, v in item.items()
                            if k not in ('rank', 'title', 'hot_value', 'url', 'label')},
                           ensure_ascii=False),
                batch_id
            ))
        conn.commit()
        conn.close()

    def get_latest_trending(self, platform: str = None, limit: int = 50) -> List[Dict]:
        """获取最新一批热点数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 先找到最新的batch_id
        if platform:
            cursor.execute(
                'SELECT batch_id FROM trending WHERE platform = ? ORDER BY created_at DESC LIMIT 1',
                (platform,))
        else:
            cursor.execute('SELECT batch_id FROM trending ORDER BY created_at DESC LIMIT 1')

        row = cursor.fetchone()
        if not row:
            conn.close()
            return []

        batch_id = row['batch_id']

        if platform:
            cursor.execute(
                'SELECT * FROM trending WHERE batch_id = ? AND platform = ? ORDER BY rank_num',
                (batch_id, platform))
        else:
            cursor.execute(
                'SELECT * FROM trending WHERE batch_id = ? ORDER BY platform, rank_num',
                (batch_id,))

        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_trending_history(self, platform: str, hours: int = 24) -> List[Dict]:
        """获取热点历史数据（按batch分组）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT batch_id, created_at FROM trending
            WHERE platform = ? AND created_at >= datetime('now', ?)
            ORDER BY created_at DESC
        ''', (platform, f'-{hours} hours'))
        batches = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return batches

    def cleanup_old_trending(self, keep_hours: int = 72):
        """清理过期热点数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM trending WHERE created_at < datetime('now', ?)",
            (f'-{keep_hours} hours',))
        conn.commit()
        conn.close()

    # ==================== 热点新闻操作 ====================

    def save_hotnews(self, source: str, items: list, batch_id: str):
        """保存热点新闻"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for item in items:
            cursor.execute('''
                INSERT INTO hotnews (source, title, url, hot_value, rank_num, summary, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                source,
                item.get('title', ''),
                item.get('url', ''),
                str(item.get('hot_value', '')),
                item.get('rank', 0),
                item.get('summary', ''),
                batch_id
            ))
        conn.commit()
        conn.close()

    def get_latest_hotnews(self, source: str = None, limit: int = 50) -> List[Dict]:
        """获取最新热点新闻"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if source:
            cursor.execute(
                'SELECT * FROM hotnews WHERE source = ? ORDER BY created_at DESC, rank_num LIMIT ?',
                (source, limit))
        else:
            cursor.execute(
                'SELECT * FROM hotnews ORDER BY created_at DESC, rank_num LIMIT ?',
                (limit,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_unprocessed_hotnews(self, limit: int = 10) -> List[Dict]:
        """获取未处理的热点新闻"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM hotnews WHERE status = 'new' ORDER BY created_at DESC LIMIT ?",
            (limit,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def update_hotnews_status(self, news_id: int, status: str):
        """更新热点新闻状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE hotnews SET status = ? WHERE id = ?', (status, news_id))
        conn.commit()
        conn.close()

    def get_hotnews_by_id(self, news_id: int) -> Optional[Dict]:
        """根据ID获取热点新闻"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM hotnews WHERE id = ?', (news_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def cleanup_old_hotnews(self, keep_hours: int = 72):
        """清理过期热点新闻"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM hotnews WHERE created_at < datetime('now', ?)",
            (f'-{keep_hours} hours',))
        conn.commit()
        conn.close()

    # ==================== 生成文章操作 ====================

    def insert_generated_article(self, article: Dict) -> Optional[int]:
        """插入生成的文章"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO generated_articles
                (hotnews_id, title, content, summary, keywords, style, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.get('hotnews_id'),
                article.get('title', ''),
                article.get('content', ''),
                article.get('summary', ''),
                article.get('keywords', ''),
                article.get('style', 'news'),
                article.get('status', 'draft')
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None
        finally:
            conn.close()

    def get_generated_article(self, article_id: int) -> Optional[Dict]:
        """获取生成的文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM generated_articles WHERE id = ?', (article_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_draft_articles(self, limit: int = 20) -> List[Dict]:
        """获取草稿文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM generated_articles WHERE status = 'draft' ORDER BY created_at DESC LIMIT ?",
            (limit,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_generated_articles(self, status: str = None, limit: int = 20) -> List[Dict]:
        """获取生成的文章列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM generated_articles WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit))
        else:
            cursor.execute(
                "SELECT * FROM generated_articles ORDER BY created_at DESC LIMIT ?",
                (limit,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_generated_article_by_id(self, article_id: int) -> Optional[Dict]:
        """根据ID获取生成的文章"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM generated_articles WHERE id = ?', (article_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_generated_article_status(self, article_id: int, status: str):
        """更新生成文章状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE generated_articles SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (status, article_id))
        conn.commit()
        conn.close()

    # ==================== 发布记录操作 ====================

    def insert_publish_record(self, record: Dict) -> Optional[int]:
        """插入发布记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO publish_records
                (article_id, platform, media_id, publish_type, status, result, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.get('article_id'),
                record.get('platform', 'wechat'),
                record.get('media_id', ''),
                record.get('publish_type', 'draft'),
                record.get('status', 'pending'),
                record.get('result', ''),
                record.get('published_at', '')
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None
        finally:
            conn.close()

    def get_publish_records(self, limit: int = 20) -> List[Dict]:
        """获取发布记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pr.*, ga.title as article_title
            FROM publish_records pr
            LEFT JOIN generated_articles ga ON pr.article_id = ga.id
            ORDER BY pr.created_at DESC LIMIT ?
        ''', (limit,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def update_publish_record(self, record_id: int, updates: Dict):
        """更新发布记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f'{key} = ?')
            values.append(value)
        values.append(record_id)
        cursor.execute(
            f'UPDATE publish_records SET {", ".join(set_clauses)} WHERE id = ?',
            values)
        conn.commit()
        conn.close()

    # ==================== 公众号配置操作 ====================

    def insert_wechat_account(self, account: Dict) -> Optional[int]:
        """插入公众号配置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO wechat_accounts
                (name, app_id, app_secret, topic_keywords, style_preference, custom_prompt, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                account['name'],
                account['app_id'],
                account['app_secret'],
                account.get('topic_keywords', ''),
                account.get('style_preference', 'news'),
                account.get('custom_prompt', ''),
                account.get('is_active', 1)
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_wechat_accounts(self, active_only: bool = False) -> List[Dict]:
        """获取公众号列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if active_only:
            cursor.execute('SELECT * FROM wechat_accounts WHERE is_active = 1 ORDER BY created_at')
        else:
            cursor.execute('SELECT * FROM wechat_accounts ORDER BY created_at')
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_wechat_account(self, account_id: int) -> Optional[Dict]:
        """获取单个公众号配置"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM wechat_accounts WHERE id = ?', (account_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_wechat_account(self, account_id: int, updates: Dict):
        """更新公众号配置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f'{key} = ?')
            values.append(value)
        values.append(account_id)
        cursor.execute(
            f'UPDATE wechat_accounts SET {", ".join(set_clauses)} WHERE id = ?',
            values)
        conn.commit()
        conn.close()

    def delete_wechat_account(self, account_id: int) -> bool:
        """删除公众号配置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM wechat_accounts WHERE id = ?', (account_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    # ==================== 工作流状态操作 ====================

    def insert_workflow_state(self, state: Dict) -> Optional[int]:
        """插入工作流状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO workflow_states
                (thread_id, hotnews_id, account_id, current_node, state_data, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                state['thread_id'],
                state.get('hotnews_id'),
                state.get('account_id'),
                state.get('current_node', ''),
                state.get('state_data', '{}'),
                state.get('status', 'pending')
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_workflow_state(self, thread_id: str) -> Optional[Dict]:
        """获取工作流状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_states WHERE thread_id = ?', (thread_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_workflow_state(self, thread_id: str, updates: Dict):
        """更新工作流状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clauses = ['updated_at = CURRENT_TIMESTAMP']
        values = []
        for key, value in updates.items():
            set_clauses.append(f'{key} = ?')
            values.append(value)
        values.append(thread_id)
        cursor.execute(
            f'UPDATE workflow_states SET {", ".join(set_clauses)} WHERE thread_id = ?',
            values)
        conn.commit()
        conn.close()

    def get_pending_workflows(self) -> List[Dict]:
        """获取待审核的工作流"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ws.*, h.title as hotnews_title, wa.name as account_name
            FROM workflow_states ws
            LEFT JOIN hotnews h ON ws.hotnews_id = h.id
            LEFT JOIN wechat_accounts wa ON ws.account_id = wa.id
            WHERE ws.status = 'pending' AND ws.current_node = 'human_review'
            ORDER BY ws.created_at
        ''')
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

import sqlite3
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

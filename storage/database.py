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

        # LLM模型渠道表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                api_key TEXT,
                base_url TEXT,
                default_model TEXT NOT NULL,
                max_tokens INTEGER DEFAULT 4000,
                is_active INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # LLM功能绑定表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                function_key TEXT NOT NULL UNIQUE,
                provider_id INTEGER NOT NULL,
                model_override TEXT,
                max_tokens_override INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provider_id) REFERENCES llm_providers(id)
            )
        ''')

        # Agent任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                stage TEXT,
                task_key TEXT,
                task_name TEXT,
                status TEXT DEFAULT 'pending',
                input_data TEXT,
                output_data TEXT,
                error_message TEXT,
                parent_task_id INTEGER,
                batch_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT
            )
        ''')

        for sql in [
            "ALTER TABLE agent_tasks ADD COLUMN stage TEXT",
            "ALTER TABLE agent_tasks ADD COLUMN task_key TEXT",
            "ALTER TABLE agent_tasks ADD COLUMN task_name TEXT",
            "ALTER TABLE agent_tasks ADD COLUMN error_message TEXT",
            "ALTER TABLE agent_tasks ADD COLUMN started_at TEXT"
        ]:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_llm_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                batch_id TEXT,
                stage TEXT,
                provider TEXT,
                model TEXT,
                prompt TEXT,
                response TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                metadata TEXT,
                status TEXT DEFAULT 'success',
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_llm_logs_task
            ON agent_llm_logs(task_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_llm_logs_batch
            ON agent_llm_logs(batch_id)
        ''')

        for sql in [
            "ALTER TABLE agent_llm_logs ADD COLUMN provider TEXT",
            "ALTER TABLE agent_llm_logs ADD COLUMN prompt TEXT",
            "ALTER TABLE agent_llm_logs ADD COLUMN response TEXT",
            "ALTER TABLE agent_llm_logs ADD COLUMN total_tokens INTEGER DEFAULT 0",
            "ALTER TABLE agent_llm_logs ADD COLUMN metadata TEXT",
        ]:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

        # Agent任务执行日志表（并行执行器使用）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                batch_id TEXT,
                stage TEXT,
                status TEXT DEFAULT 'pending',
                started_at TEXT,
                completed_at TEXT,
                duration_ms INTEGER,
                input_summary TEXT,
                output_summary TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_task_logs_batch
            ON agent_task_logs(batch_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_task_logs_stage
            ON agent_task_logs(batch_id, stage)
        ''')

        # Agent生成的推文
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_title TEXT NOT NULL,
                platform TEXT,
                hot_value TEXT,
                value_score REAL,
                article_type TEXT,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                keywords TEXT,
                quality_score REAL,
                quality_detail TEXT,
                status TEXT DEFAULT 'draft',
                batch_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                published_at TEXT
            )
        ''')

        # Agent Prompt模板表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                prompt_type TEXT NOT NULL,
                content TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                is_builtin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 话题工作流表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_workflows (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                topic_title TEXT NOT NULL,
                platform TEXT,
                hot_value TEXT,
                current_stage TEXT,
                status TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                completed_at TEXT,
                collect_result TEXT,
                analysis_result TEXT,
                plan_result TEXT,
                article_id INTEGER,
                quality_score REAL,
                decisions TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflow_batch ON topic_workflows(batch_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflow_status ON topic_workflows(status)')

        # 工作流转换记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                from_stage TEXT,
                to_stage TEXT,
                action TEXT,
                reason TEXT,
                timestamp TEXT,
                FOREIGN KEY (workflow_id) REFERENCES topic_workflows(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transition_workflow ON workflow_transitions(workflow_id)')

        # 微信草稿表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wechat_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                article_ids TEXT,
                article_count INTEGER,
                cover_image TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_draft_batch ON wechat_drafts(batch_id)')

        conn.commit()
        conn.close()

        self._init_builtin_prompts()

    def _init_builtin_prompts(self):
        """首次启动时插入内置Prompt模板"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM agent_prompts WHERE is_builtin = 1')
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        builtin_prompts = [
            {
                'name': '热点筛选Prompt',
                'prompt_type': 'topic_filter',
                'content': '请从以下热点列表中筛选出最有价值的话题，考虑热度、时效性和内容深度。返回JSON数组，每项包含title、platform、hot_value、value_score(0-10)字段。',
            },
            {
                'name': '文章生成Prompt',
                'prompt_type': 'article_generate',
                'content': '请根据以下热点话题撰写一篇高质量的自媒体文章。要求：标题吸引人、内容有深度、观点独到、语言流畅。返回JSON，包含title、content、summary、keywords字段。',
            },
            {
                'name': '质量评估Prompt',
                'prompt_type': 'quality_check',
                'content': '请对以下文章进行质量评估，从原创性、可读性、信息量、标题吸引力、结构完整性五个维度打分(0-10)，并给出总分和改进建议。返回JSON，包含quality_score、detail(各维度分数)、suggestions字段。',
            },
        ]

        for p in builtin_prompts:
            cursor.execute('''
                INSERT INTO agent_prompts (name, prompt_type, content, is_active, is_builtin)
                VALUES (?, ?, ?, 1, 1)
            ''', (p['name'], p['prompt_type'], p['content']))

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

    def get_articles_by_ids(self, article_ids: List[int]) -> List[Dict]:
        """根据ID列表获取文章"""
        if not article_ids:
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ','.join('?' * len(article_ids))
        cursor.execute(f'''
            SELECT * FROM articles
            WHERE id IN ({placeholders})
        ''', article_ids)

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

    def update_generated_article(self, article_id: int, data: Dict) -> bool:
        """更新生成的文章"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE generated_articles
                SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                data.get('title', ''),
                data.get('content', ''),
                article_id
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
        finally:
            conn.close()

    def delete_generated_article(self, article_id: int) -> bool:
        """删除生成的文章"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM generated_articles WHERE id = ?', (article_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
        finally:
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

    # ==================== LLM模型渠道操作 ====================

    def create_llm_provider(self, data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO llm_providers
                (name, provider_type, api_key, base_url, default_model, max_tokens, is_active, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'], data['provider_type'], data.get('api_key', ''),
                data.get('base_url', ''), data['default_model'],
                data.get('max_tokens', 4000), data.get('is_active', 1),
                data.get('is_default', 0)
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None
        finally:
            conn.close()

    def get_llm_providers(self, active_only: bool = False) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if active_only:
            cursor.execute('SELECT * FROM llm_providers WHERE is_active = 1 ORDER BY is_default DESC, created_at')
        else:
            cursor.execute('SELECT * FROM llm_providers ORDER BY is_default DESC, created_at')
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_llm_provider(self, provider_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM llm_providers WHERE id = ?', (provider_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_llm_provider(self, provider_id: int, data: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        fields = []
        values = []
        for key in ['name', 'provider_type', 'api_key', 'base_url', 'default_model', 'max_tokens', 'is_active']:
            if key in data:
                fields.append(f'{key} = ?')
                values.append(data[key])
        fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(provider_id)
        cursor.execute(f'UPDATE llm_providers SET {", ".join(fields)} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def delete_llm_provider(self, provider_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM llm_providers WHERE id = ?', (provider_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def set_default_provider(self, provider_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE llm_providers SET is_default = 0')
        cursor.execute('UPDATE llm_providers SET is_default = 1 WHERE id = ?', (provider_id,))
        conn.commit()
        conn.close()

    # ==================== LLM功能绑定操作 ====================

    def get_llm_binding(self, function_key: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM llm_bindings WHERE function_key = ?', (function_key,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_llm_bindings(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM llm_bindings')
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def upsert_llm_binding(self, function_key: str, provider_id: int,
                           model_override: str = None, max_tokens_override: int = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO llm_bindings (function_key, provider_id, model_override, max_tokens_override)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(function_key) DO UPDATE SET
                provider_id = excluded.provider_id,
                model_override = excluded.model_override,
                max_tokens_override = excluded.max_tokens_override,
                updated_at = CURRENT_TIMESTAMP
        ''', (function_key, provider_id, model_override, max_tokens_override))
        conn.commit()
        conn.close()

    # ==================== Agent Tasks ====================

    def create_agent_task(self, task_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_tasks (task_type, status, input_data, output_data, parent_task_id, batch_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_data.get('task_type'), task_data.get('status', 'pending'),
              task_data.get('input_data'), task_data.get('output_data'),
              task_data.get('parent_task_id'), task_data.get('batch_id')))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    def get_agent_task(self, task_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_agent_task(self, task_id: int, updates: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [task_id]
        cursor.execute(f'UPDATE agent_tasks SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def list_agent_tasks(self, batch_id: str = None, status: str = None, stage: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM agent_tasks WHERE 1=1'
        params = []
        if batch_id:
            query += ' AND batch_id = ?'
            params.append(batch_id)
        if status:
            query += ' AND status = ?'
            params.append(status)
        if stage:
            query += ' AND stage = ?'
            params.append(stage)
        query += ' ORDER BY created_at DESC'
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    # ==================== Agent LLM Logs ====================

    def create_agent_llm_log(self, log_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        tokens = log_data.get('tokens', {})
        prompt_tokens = tokens.get('prompt_tokens', 0) if isinstance(tokens, dict) else log_data.get('prompt_tokens', 0)
        completion_tokens = tokens.get('completion_tokens', 0) if isinstance(tokens, dict) else log_data.get('completion_tokens', 0)
        total_tokens = tokens.get('total_tokens', 0) if isinstance(tokens, dict) else log_data.get('total_tokens', 0)
        metadata = log_data.get('metadata')
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata, ensure_ascii=False)
        cursor.execute('''
            INSERT INTO agent_llm_logs (task_id, batch_id, stage, provider, model,
                prompt, response, prompt_tokens, completion_tokens, total_tokens,
                duration_ms, metadata, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_data.get('task_id'), log_data.get('batch_id'),
              log_data.get('stage'), log_data.get('provider'),
              log_data.get('model'), log_data.get('prompt'),
              log_data.get('response'),
              prompt_tokens, completion_tokens, total_tokens,
              log_data.get('duration_ms', 0),
              metadata,
              log_data.get('status', 'success'),
              log_data.get('error')))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_agent_llm_logs_by_task(self, task_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_llm_logs WHERE task_id = ? ORDER BY created_at DESC', (task_id,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_agent_llm_logs_by_batch(self, batch_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_llm_logs WHERE batch_id = ? ORDER BY created_at DESC', (batch_id,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_agent_llm_logs(self, task_id: str = None, batch_id: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM agent_llm_logs WHERE 1=1'
        params = []
        if task_id:
            query += ' AND task_id = ?'
            params.append(task_id)
        if batch_id:
            query += ' AND batch_id = ?'
            params.append(batch_id)
        query += ' ORDER BY created_at DESC'
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    # ==================== Agent Task Logs ====================

    def create_agent_task_log(self, task_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_task_logs (task_id, batch_id, stage, status,
                started_at, completed_at, duration_ms, input_summary, output_summary, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_data.get('task_id'), task_data.get('batch_id'),
              task_data.get('stage'), task_data.get('status', 'pending'),
              task_data.get('started_at'), task_data.get('completed_at'),
              task_data.get('duration_ms'), task_data.get('input_summary'),
              task_data.get('output_summary'), task_data.get('error')))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def update_agent_task_log(self, log_id: int, updates: Dict) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [log_id]
        cursor.execute(f'UPDATE agent_task_logs SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def get_agent_tasks_by_batch(self, batch_id: str, stage: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM agent_task_logs WHERE batch_id = ?'
        params: list = [batch_id]
        if stage:
            query += ' AND stage = ?'
            params.append(stage)
        query += ' ORDER BY created_at DESC'
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    # ==================== Agent Articles ====================

    def create_agent_article(self, article_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_articles (topic_title, platform, hot_value, value_score, article_type,
                                        title, content, summary, keywords, quality_score, quality_detail,
                                        status, batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (article_data.get('topic_title'), article_data.get('platform'),
              article_data.get('hot_value'), article_data.get('value_score'),
              article_data.get('article_type'), article_data.get('title'),
              article_data.get('content'), article_data.get('summary'),
              article_data.get('keywords'), article_data.get('quality_score'),
              article_data.get('quality_detail'), article_data.get('status', 'draft'),
              article_data.get('batch_id')))
        article_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return article_id

    def get_agent_article(self, article_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_articles WHERE id = ?', (article_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_agent_article(self, article_id: int, updates: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [article_id]
        cursor.execute(f'UPDATE agent_articles SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def list_agent_articles(self, status: str = None, batch_id: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = 'SELECT * FROM agent_articles WHERE 1=1'
        params = []
        if status:
            query += ' AND status = ?'
            params.append(status)
        if batch_id:
            query += ' AND batch_id = ?'
            params.append(batch_id)
        query += ' ORDER BY created_at DESC'
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_agent_articles_by_status(self, status: str) -> List[Dict]:
        return self.list_agent_articles(status=status)

    def get_agent_articles_by_batch(self, batch_id: str) -> List[Dict]:
        """根据batch_id获取文章列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_articles WHERE batch_id = ? ORDER BY created_at DESC', (batch_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== Agent Prompts ====================

    def create_agent_prompt(self, prompt_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_prompts (name, prompt_type, content, is_active, is_builtin)
            VALUES (?, ?, ?, ?, ?)
        ''', (prompt_data.get('name'), prompt_data.get('prompt_type'),
              prompt_data.get('content'), prompt_data.get('is_active', 0), 0))
        prompt_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return prompt_id

    def get_agent_prompt(self, prompt_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_prompts WHERE id = ?', (prompt_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_agent_prompt(self, prompt_id: int, updates: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        updates['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [prompt_id]
        cursor.execute(f'UPDATE agent_prompts SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def delete_agent_prompt(self, prompt_id: int) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT is_builtin FROM agent_prompts WHERE id = ?', (prompt_id,))
        row = cursor.fetchone()
        if not row or row[0] == 1:
            conn.close()
            return False
        cursor.execute('DELETE FROM agent_prompts WHERE id = ?', (prompt_id,))
        conn.commit()
        conn.close()
        return True

    def list_agent_prompts(self, prompt_type: str = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if prompt_type:
            cursor.execute('SELECT * FROM agent_prompts WHERE prompt_type = ? ORDER BY created_at DESC', (prompt_type,))
        else:
            cursor.execute('SELECT * FROM agent_prompts ORDER BY created_at DESC')
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_active_agent_prompt(self, prompt_type: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agent_prompts WHERE prompt_type = ? AND is_active = 1 LIMIT 1', (prompt_type,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def activate_agent_prompt(self, prompt_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT prompt_type FROM agent_prompts WHERE id = ?', (prompt_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        prompt_type = row[0]
        cursor.execute('UPDATE agent_prompts SET is_active = 0 WHERE prompt_type = ?', (prompt_type,))
        cursor.execute('UPDATE agent_prompts SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (prompt_id,))
        conn.commit()
        conn.close()

    # ==================== Topic Workflows ====================

    def create_topic_workflow(self, workflow_data: Dict) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO topic_workflows (id, batch_id, topic_title, platform, hot_value,
                    current_stage, status, retry_count, created_at, updated_at, completed_at,
                    collect_result, analysis_result, plan_result, article_id, quality_score, decisions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workflow_data.get('id'), workflow_data.get('batch_id'),
                workflow_data.get('topic_title'), workflow_data.get('platform'),
                workflow_data.get('hot_value'), workflow_data.get('current_stage'),
                workflow_data.get('status'), workflow_data.get('retry_count', 0),
                workflow_data.get('created_at'), workflow_data.get('updated_at'),
                workflow_data.get('completed_at'), workflow_data.get('collect_result'),
                workflow_data.get('analysis_result'), workflow_data.get('plan_result'),
                workflow_data.get('article_id'), workflow_data.get('quality_score'),
                workflow_data.get('decisions')
            ))
            conn.commit()
            return workflow_data.get('id')
        except Exception:
            return None
        finally:
            conn.close()

    def update_topic_workflow(self, workflow_id: str, updates: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        values = list(updates.values()) + [workflow_id]
        cursor.execute(f'UPDATE topic_workflows SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def get_topic_workflows_by_batch(self, batch_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM topic_workflows WHERE batch_id = ? ORDER BY created_at', (batch_id,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    def get_topic_workflow(self, workflow_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM topic_workflows WHERE id = ?', (workflow_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ==================== Workflow Transitions ====================

    def create_workflow_transition(self, transition_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO workflow_transitions (workflow_id, from_stage, to_stage, action, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                transition_data.get('workflow_id'), transition_data.get('from_stage'),
                transition_data.get('to_stage'), transition_data.get('action'),
                transition_data.get('reason'),
                transition_data.get('timestamp', datetime.now().isoformat())
            ))
            transition_id = cursor.lastrowid
            conn.commit()
            return transition_id
        except Exception:
            return None
        finally:
            conn.close()

    def get_workflow_transitions(self, workflow_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM workflow_transitions WHERE workflow_id = ? ORDER BY timestamp',
            (workflow_id,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

    # ==================== WeChat Drafts ====================

    def create_wechat_draft(self, draft_data: Dict) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO wechat_drafts (batch_id, title, summary, article_ids,
                    article_count, cover_image, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                draft_data.get('batch_id'), draft_data.get('title'),
                draft_data.get('summary'), draft_data.get('article_ids'),
                draft_data.get('article_count'), draft_data.get('cover_image'),
                draft_data.get('status', 'draft'),
                draft_data.get('created_at', datetime.now().isoformat())
            ))
            draft_id = cursor.lastrowid
            conn.commit()
            return draft_id
        except Exception:
            return None
        finally:
            conn.close()

    def get_wechat_drafts_by_batch(self, batch_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM wechat_drafts WHERE batch_id = ? ORDER BY created_at DESC',
            (batch_id,))
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results

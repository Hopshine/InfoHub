"""
ChromaDB向量存储封装
用于热点去重和RAG检索
使用魔搭下载的中文embedding模型
"""
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Optional
from utils.logger import setup_logger
import os

logger = setup_logger('vector_store')

# 中文embedding模型路径（从魔搭下载）
EMBEDDING_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'models', 'iic', 'nlp_corom_sentence-embedding_chinese-base'
)


class VectorStore:
    """ChromaDB向量存储管理器（中文优化）"""

    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            persist_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data', 'chroma'
            )
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # 初始化中文embedding函数
        self._embedding_fn = self._init_embedding()

        # 热点去重Collection
        self.hot_topics = self.client.get_or_create_collection(
            name="hot_topics",
            metadata={"description": "热点话题去重"},
            embedding_function=self._embedding_fn
        )

        # 文章内容RAG Collection
        self.article_content = self.client.get_or_create_collection(
            name="article_content",
            metadata={"description": "历史文章RAG检索"},
            embedding_function=self._embedding_fn
        )

        logger.info(f"ChromaDB initialized at {persist_dir}")

    def _init_embedding(self):
        """初始化中文embedding模型"""
        if os.path.isdir(EMBEDDING_MODEL_PATH):
            try:
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=EMBEDDING_MODEL_PATH
                )
                logger.info(f"使用本地中文embedding模型: {EMBEDDING_MODEL_PATH}")
                return ef
            except Exception as e:
                logger.warning(f"加载本地模型失败: {e}，使用默认embedding")
        else:
            logger.info("本地中文模型未找到，使用ChromaDB默认embedding")
        return None

    def add_topic(self, title: str, metadata: Dict) -> str:
        """
        添加热点话题

        Args:
            title: 话题标题
            metadata: 元数据 {source, url, timestamp, ...}

        Returns:
            文档ID
        """
        try:
            doc_id = f"{metadata.get('source', 'unknown')}_{hash(title)}"
            self.hot_topics.add(
                documents=[title],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.debug(f"Added topic: {title[:50]}")
            return doc_id
        except Exception as e:
            logger.error(f"Failed to add topic: {e}")
            raise

    def is_duplicate(self, title: str, threshold: float = 0.0008) -> bool:
        """
        检查话题是否重复

        Args:
            title: 话题标题
            threshold: 距离阈值（余弦距离，越小越相似，默认0.0008）

        Returns:
            是否重复
        """
        try:
            results = self.hot_topics.query(
                query_texts=[title],
                n_results=1
            )

            if not results['distances'] or not results['distances'][0]:
                return False

            # 使用余弦距离：距离越小越相似
            distance = results['distances'][0][0]

            is_dup = distance <= threshold
            if is_dup:
                logger.info(f"Duplicate detected: {title[:50]} (distance={distance:.4f})")

            return is_dup
        except Exception as e:
            logger.error(f"Failed to check duplicate: {e}")
            return False

    def add_article(self, content: str, metadata: Dict) -> str:
        """
        添加文章内容

        Args:
            content: 文章内容
            metadata: 元数据 {title, platform, publish_time, ...}

        Returns:
            文档ID
        """
        try:
            doc_id = f"article_{metadata.get('title', '')}_{hash(content)}"
            self.article_content.add(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.debug(f"Added article: {metadata.get('title', 'untitled')[:50]}")
            return doc_id
        except Exception as e:
            logger.error(f"Failed to add article: {e}")
            raise

    def search_similar(self, query: str, n: int = 5) -> List[Dict]:
        """
        检索相似文章

        Args:
            query: 查询文本
            n: 返回数量

        Returns:
            相似文章列表 [{content, metadata, distance}, ...]
        """
        try:
            results = self.article_content.query(
                query_texts=[query],
                n_results=n
            )

            articles = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    articles.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 1.0
                    })

            logger.info(f"Found {len(articles)} similar articles for query: {query[:50]}")
            return articles
        except Exception as e:
            logger.error(f"Failed to search similar: {e}")
            return []

    def clear_topics(self):
        """清空热点话题Collection"""
        try:
            self.client.delete_collection("hot_topics")
            self.hot_topics = self.client.create_collection(
                name="hot_topics",
                metadata={"description": "热点话题去重"}
            )
            logger.info("Cleared hot_topics collection")
        except Exception as e:
            logger.error(f"Failed to clear topics: {e}")

    def clear_articles(self):
        """清空文章内容Collection"""
        try:
            self.client.delete_collection("article_content")
            self.article_content = self.client.create_collection(
                name="article_content",
                metadata={"description": "历史文章RAG检索"}
            )
            logger.info("Cleared article_content collection")
        except Exception as e:
            logger.error(f"Failed to clear articles: {e}")

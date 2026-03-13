"""URL哈希 + 内容simhash去重"""
import hashlib
import re
from typing import Optional, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


class DeduplicationFilter:
    """去重过滤器：URL哈希 + 内容simhash"""

    def __init__(self, hamming_threshold: int = 3):
        self.hamming_threshold = hamming_threshold
        self._seen_urls: Set[str] = set()
        self._content_hashes: list = []  # list of (simhash_value, article_id)

    def normalize_url(self, url: str) -> str:
        """URL标准化"""
        parsed = urlparse(url)
        # 移除追踪参数
        params = parse_qs(parsed.query)
        clean_params = {k: v for k, v in params.items()
                       if k not in ('utm_source', 'utm_medium', 'utm_campaign', 'from', 'scene', 'subscene')}
        clean_query = urlencode(clean_params, doseq=True)
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ''))
        return normalized.rstrip('/')

    def url_hash(self, url: str) -> str:
        """计算URL的SHA256哈希"""
        normalized = self.normalize_url(url)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def check_url(self, url: str) -> bool:
        """检查URL是否已见过。返回True表示重复"""
        h = self.url_hash(url)
        if h in self._seen_urls:
            return True
        self._seen_urls.add(h)
        return False

    @staticmethod
    def _tokenize(text: str) -> list:
        """中文分词（简单按字符+词组）"""
        # 移除HTML标签和特殊字符
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', '', text)
        # 使用2-gram
        tokens = []
        for i in range(len(text) - 1):
            tokens.append(text[i:i+2])
        return tokens

    @staticmethod
    def simhash(text: str, hashbits: int = 64) -> int:
        """计算文本的simhash指纹"""
        if not text:
            return 0
        tokens = DeduplicationFilter._tokenize(text)
        if not tokens:
            return 0

        v = [0] * hashbits
        for token in tokens:
            token_hash = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
            for i in range(hashbits):
                bitmask = 1 << i
                if token_hash & bitmask:
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(hashbits):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """计算两个simhash的汉明距离"""
        x = hash1 ^ hash2
        count = 0
        while x:
            count += 1
            x &= x - 1
        return count

    def content_hash(self, text: str) -> str:
        """计算内容指纹（返回hex字符串用于存储）"""
        h = self.simhash(text)
        return format(h, '016x')

    def check_content(self, text: str) -> bool:
        """检查内容是否重复。返回True表示重复"""
        if not text:
            return False
        new_hash = self.simhash(text)
        for existing_hash, _ in self._content_hashes:
            if self.hamming_distance(new_hash, existing_hash) < self.hamming_threshold:
                return True
        self._content_hashes.append((new_hash, None))
        return False

    def add_known_hash(self, hash_hex: str, article_id: int = None):
        """添加已知的内容指纹（从数据库加载）"""
        if hash_hex:
            try:
                h = int(hash_hex, 16)
                self._content_hashes.append((h, article_id))
            except ValueError:
                pass

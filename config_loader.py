"""
LLM配置加载器
支持从数据库加载模型配置，带缓存机制
"""
import time
from typing import Dict, Optional
from config import Config


class LLMConfigLoader:
    """LLM配置加载器，带60秒缓存"""

    _cache = {}  # {function_key: (config, timestamp)}
    _cache_ttl = 60  # 60秒缓存

    @classmethod
    def get_config(cls, db, function_key: str) -> Dict:
        """
        获取指定功能的模型配置

        Args:
            db: Database实例
            function_key: 功能标识 (content_analysis / article_generation)

        Returns:
            配置字典 {provider_type, api_key, base_url, model, max_tokens}
        """
        # 检查缓存
        if function_key in cls._cache:
            config, ts = cls._cache[function_key]
            if time.time() - ts < cls._cache_ttl:
                return config

        # 查询绑定
        binding = db.get_llm_binding(function_key)
        if binding:
            provider = db.get_llm_provider(binding['provider_id'])
            if provider and provider['is_active']:
                config = cls._build_config(provider, binding)
                cls._cache[function_key] = (config, time.time())
                return config

        # 回退到默认渠道
        providers = db.get_llm_providers(active_only=True)
        default = next((p for p in providers if p['is_default']), None)
        if default:
            config = cls._build_config(default, None)
            cls._cache[function_key] = (config, time.time())
            return config

        # 最终回退到环境变量
        return cls._fallback_config(function_key)

    @classmethod
    def _build_config(cls, provider: Dict, binding: Optional[Dict]) -> Dict:
        """构建配置字典"""
        model = provider['default_model']
        max_tokens = provider['max_tokens']

        if binding:
            if binding.get('model_override'):
                model = binding['model_override']
            if binding.get('max_tokens_override'):
                max_tokens = binding['max_tokens_override']

        return {
            'provider_type': provider['provider_type'],
            'api_key': provider.get('api_key', ''),
            'base_url': provider.get('base_url', ''),
            'model': model,
            'max_tokens': max_tokens
        }

    @classmethod
    def _fallback_config(cls, function_key: str) -> Dict:
        """回退到config.py环境变量"""
        model = Config.ANALYSIS_MODEL if function_key in ('content_analysis', 'topic_evaluation') else Config.ARTICLE_MODEL
        return {
            'provider_type': Config.LLM_PROVIDER,
            'api_key': Config.LLM_API_KEY,
            'base_url': Config.LLM_BASE_URL or '',
            'model': model,
            'max_tokens': Config.ARTICLE_MAX_TOKENS
        }

    @classmethod
    def invalidate(cls, function_key: Optional[str] = None):
        """
        清除缓存

        Args:
            function_key: 指定功能key，为None则清除所有缓存
        """
        if function_key:
            cls._cache.pop(function_key, None)
        else:
            cls._cache.clear()

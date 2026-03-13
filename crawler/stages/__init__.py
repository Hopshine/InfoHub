"""爬虫管道阶段"""
from .search import SogouSearchStage
from .resolver import RedirectResolverStage
from .fetcher import ContentFetchStage
from .extractor import ExtractorStage
from .storage import StorageStage

"""
LLM引擎

提供统一的LLM调用接口，自动集成缓存机制
"""
import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .cache_db import ExtractCacheDB
from .provider import LLMProvider
from ..exceptions import LLMError


class LLMEngine:
    """LLM调用引擎，集成缓存机制"""
    
    def __init__(self, provider: LLMProvider, cache_db: Optional[ExtractCacheDB] = None):
        """
        初始化LLM引擎
        
        Args:
            provider: LLM Provider实例
            cache_db: 缓存数据库（可选，如果不提供则不使用缓存）
        """
        self.provider = provider
        self.cache_db = cache_db
        self.logger = logging.getLogger(__name__)
        
        if cache_db:
            self.logger.info("LLM缓存已启用")
        else:
            self.logger.info("LLM缓存未启用")
    
    @classmethod
    def from_config_loader(cls, config_loader, cache_db: Optional[ExtractCacheDB] = None):
        """
        从配置加载器创建LLM引擎（推荐方式）
        
        Args:
            config_loader: ConfigLoader 实例
            cache_db: 缓存数据库（可选，如果不提供则从配置读取）
            
        Returns:
            LLMEngine 实例
        """
        provider = LLMProvider.from_config_loader(config_loader)
        
        if cache_db is None:
            config = config_loader.load_config()
            llm_config = config.get('llm', {})
            cache_config = llm_config.get('cache', {})
            
            if cache_config.get('enabled', True):
                db_path = cache_config.get('db_path', 'database/extract_cache.db')
                if not Path(db_path).is_absolute():
                    db_path = config_loader.project_root / db_path
                cache_db = ExtractCacheDB(str(db_path))
        
        return cls(provider, cache_db)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        use_cache: bool = True
    ) -> Tuple[str, bool]:
        """
        调用LLM，自动使用缓存
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数（默认0.7）
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            Tuple[str, bool]: (LLM响应文本, 是否命中缓存)
            
        Raises:
            LLMError: 调用失败时抛出
        """
        if not use_cache or not self.cache_db:
            response = self.provider.chat(messages, temperature)
            return response, False
        
        # 计算提示词哈希（作为缓存键）
        prompt_hash = self._calculate_prompt_hash(messages)
        llm_prompt = json.dumps(messages, ensure_ascii=False)
        
        # 查询缓存
        cached_response = self.cache_db.get(prompt_hash)
        if cached_response:
            self.logger.debug(f"LLM缓存命中: {prompt_hash[:16]}...")
            return cached_response, True
        
        # 缓存未命中，调用LLM
        self.logger.debug(f"LLM缓存未命中，调用API: {prompt_hash[:16]}...")
        response = self.provider.chat(messages, temperature)
        
        # 保存到缓存
        self.cache_db.save(prompt_hash, llm_prompt, response)
        
        return response, False
    
    def _calculate_prompt_hash(self, messages: List[Dict[str, str]]) -> str:
        """
        计算提示词哈希（基于所有user消息的content）
        
        Args:
            messages: 消息列表
            
        Returns:
            提示词哈希（SHA256哈希）
        """
        # 提取所有user消息的content
        prompt_parts = []
        for msg in messages:
            if msg.get("role") == "user":
                prompt_parts.append(msg.get("content", ""))
        
        # 如果没有user消息，使用所有消息的content
        if not prompt_parts:
            prompt_parts = [msg.get("content", "") for msg in messages]
        
        # 合并所有提示词部分
        prompt_text = "\n".join(prompt_parts)
        
        # 计算SHA256哈希
        sha256 = hashlib.sha256()
        sha256.update(prompt_text.encode('utf-8'))
        return sha256.hexdigest()
    
    def clear_cache(self, prompt_hash: Optional[str] = None) -> int:
        """
        清理缓存
        
        Args:
            prompt_hash: 提示词哈希，如果为None则清理所有缓存
            
        Returns:
            删除的记录数
        """
        if not self.cache_db:
            return 0
        return self.cache_db.delete(prompt_hash)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        if not self.cache_db:
            return {"total": 0, "oldest": None, "newest": None}
        return self.cache_db.get_stats()

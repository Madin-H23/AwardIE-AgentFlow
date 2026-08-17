"""
LLM提供者

支持多种LLM Provider，通过配置自动选择
"""
import os
import requests
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    LLM提供者（API类型）
    
    支持通过API调用云端LLM服务
    """

    def __init__(self, api_config: Dict[str, Any]):
        """
        初始化LLM提供者

        Args:
            api_config: API配置字典，包含：
                - url: API地址
                - api_key_env: API Key环境变量名
                - model: 模型名称
                - temperature: 默认温度（可选）
        """
        self._api_config = api_config
        logger.info(f"LLM Provider初始化: {api_config.get('model')}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> str:
        """
        调用LLM

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数

        Returns:
            LLM响应文本

        Raises:
            LLMError: 调用失败时抛出
        """
        try:
            return self._chat_with_api(messages, temperature)
        except Exception as e:
            from ..exceptions import LLMError
            raise LLMError(str(e)) from e

    def _chat_with_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float
    ) -> str:
        """直接调用API"""
        config = self._api_config

        # 从环境变量获取API Key（如果配置了的话）
        api_key_env = config.get("api_key_env")
        headers = {"Content-Type": "application/json"}

        # 只在配置了 api_key_env 时才添加 Authorization header
        if api_key_env:
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ValueError(f"环境变量 {api_key_env} 未设置")
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": config.get("model", "glm-4-flash"),
            "messages": messages,
            "temperature": temperature
        }

        url = config.get("url")
        if not url:
            raise ValueError("api_config 中未指定 url")

        # 从配置获取timeout，默认60秒；重试次数默认3（P1-6/P1-20 韧性）
        timeout = config.get("timeout", 60)
        max_retries = int(config.get("max_retries", 3))

        logger.debug(f"调用LLM API: {url}, model={payload['model']}, timeout={timeout}, retries={max_retries}")

        # P1-10 熔断守卫（LLM 维度单例）：open 时直接抛 4003（不发起调用）
        from backend.utils.circuit_breaker import CircuitBreaker, is_service_failure
        breaker = CircuitBreaker.get("llm")
        breaker.guard()

        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                breaker.record_success()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.debug(f"LLM响应长度: {len(content)}")
                return content
            except Exception as e:
                last_exc = e
                if is_service_failure(e):
                    breaker.record_failure()
                    if attempt < max_retries - 1:      # 指数退避：1/2/4s + 抖动
                        import time as _t, random
                        _t.sleep(min(2 ** attempt, 4) + random.uniform(0, 0.5))
                        continue
                raise
        raise last_exc  # 理论上不可达（最后一次循环内已 raise）

    # ==================== 工厂方法 ====================

    @classmethod
    def from_config_loader(cls, config_loader, provider_name: Optional[str] = None):
        """
        从配置加载器创建 LLMProvider（推荐方式）
        
        自动从 config/settings.json 读取配置，支持环境变量替换
        
        Args:
            config_loader: ConfigLoader 实例
            provider_name: Provider名称（可选，如果不提供则使用default_provider）
            
        Returns:
            LLMProvider 或 OllamaLLMProvider 实例
            
        示例:
            >>> from backend.extract.llm import LLMProvider
            >>> from config.loader import get_config
            >>> 
            >>> config_loader = get_config()
            >>> provider = LLMProvider.from_config_loader(config_loader)
        """
        # 获取默认Provider名称
        if provider_name is None:
            provider_name = config_loader.get_default_provider('llm')
        
        # 获取原始配置（未替换环境变量）以获取 api_key_env
        config = config_loader.load_config()
        raw_provider_config = config['llm']['providers'].get(provider_name)
        
        if not raw_provider_config:
            raise ValueError(f"配置中未找到LLM Provider: {provider_name}")
        
        # 检查是否为Ollama Provider
        provider_type = raw_provider_config.get("type", "api")
        if provider_type == "local" and ("ollama" in provider_name.lower() or "ollama" in raw_provider_config.get("model", "").lower()):
            return OllamaLLMProvider.from_config(raw_provider_config)
        
        # 获取替换后的配置（用于获取其他字段）
        llm_provider_config = config_loader.get_provider_config('llm', provider_name)
        
        # 构建 LLMProvider 期望的配置格式
        api_config = {
            "url": raw_provider_config.get("base_url") or raw_provider_config.get("url") or llm_provider_config.get("base_url") or llm_provider_config.get("url"),
            "api_key_env": raw_provider_config.get("api_key_env"),  # 使用原始配置中的 api_key_env
            "model": llm_provider_config.get("model", raw_provider_config.get("model", "glm-4-flash")),
            "temperature": llm_provider_config.get("temperature", raw_provider_config.get("temperature", 0.7))
        }
        
        # 验证必需字段
        if provider_type == "api":
            if not api_config.get("api_key_env"):
                raise ValueError(
                    f"LLM配置中缺少 'api_key_env' 字段。"
                    f"请在配置文件的 llm.providers.{provider_name} 中添加 'api_key_env' 字段，"
                    f"例如: \"api_key_env\": \"ZHIPUAI_API_KEY\""
                )
            if not api_config.get("url"):
                raise ValueError(
                    f"LLM配置中缺少 'url' 或 'base_url' 字段。"
                    f"请在配置文件的 llm.providers.{provider_name} 中添加 'url' 或 'base_url' 字段。"
                )
        
        return cls(api_config)
    
    def __str__(self) -> str:
        return f"LLMProvider(model={self._api_config.get('model')})"
    
    def __repr__(self) -> str:
        return self.__str__()


class OllamaLLMProvider:
    """
    Ollama LLM Provider
    使用官方 ollama 库调用本地 Ollama 模型

    要求安装: pip install ollama
    """

    def __init__(self, model: str, **kwargs):
        """
        初始化 Ollama LLM Provider

        Args:
            model: 模型名称 (如 'cnshenyang/qwen3-nothink:30b')
            **kwargs: 其他配置 (host, temperature, format 等)
        """
        self.model = model
        self.host = kwargs.get('host', 'http://127.0.0.1:11434')
        self.temperature = kwargs.get('temperature', 0)
        self.format = kwargs.get('format', None)  # 可设置为 "json" 强制返回 JSON
        self._logger = kwargs.get('logger', logging.getLogger(__name__))
        self._client = None  # 延迟初始化

    def _get_client(self):
        """获取或创建 Ollama Client"""
        if self._client is None:
            from ollama import Client
            self._client = Client(host=self.host)
            self._logger.info(f"Ollama Client 初始化完成 (host: {self.host})")
        return self._client

    def chat(self, messages: List[Dict[str, str]], temperature: float = None) -> str:
        """
        发送聊天请求到 Ollama

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数 (可选)

        Returns:
            LLM 响应文本
        """
        try:
            self._logger.info(f"调用 Ollama LLM: {self.model}")

            # 使用 Client 方式调用（与 demo 一致）
            client = self._get_client()

            # 构建 chat 参数
            chat_kwargs = {
                'model': self.model,
                'messages': messages,
                'options': {
                    'temperature': temperature if temperature is not None else self.temperature
                }
            }

            # 如果指定了 format，添加到参数中
            if self.format:
                chat_kwargs['format'] = self.format

            response = client.chat(**chat_kwargs)

            # 提取响应内容
            response_content = response.get("message", {}).get("content", "")

            if not response_content:
                raise ValueError("Ollama 返回的内容为空")

            self._logger.info(f"Ollama LLM 调用完成，响应长度: {len(response_content)}")
            return response_content

        except ImportError:
            self._logger.error("ollama 库未安装")
            from ..exceptions import LLMError
            raise LLMError("ollama 库未安装。请运行: pip install ollama")
        except Exception as e:
            self._logger.error(f"Ollama LLM 调用失败: {e}")
            from ..exceptions import LLMError
            raise LLMError(f"Ollama LLM 调用失败: {e}")

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'OllamaLLMProvider':
        """
        从配置创建实例

        Args:
            config: 配置字典，包含:
                - model: 模型名称 (必需)
                - base_url: Ollama 服务地址 (可选，默认 http://127.0.0.1:11434)
                - base_url_env: Ollama 服务地址环境变量名 (可选)
                - temperature: 温度 (可选，默认 0)
                - format: 返回格式 (可选，如 "json")

        Returns:
            OllamaLLMProvider 实例
        """
        import os

        # 获取 host（优先从环境变量）
        host = config.get('base_url')
        base_url_env = config.get('base_url_env')
        if base_url_env and not host:
            host = os.getenv(base_url_env, 'http://127.0.0.1:11434')
        if not host:
            host = 'http://127.0.0.1:11434'

        return cls(
            model=config['model'],
            host=host,
            temperature=config.get('temperature', 0),
            format=config.get('format')
        )

    def __str__(self) -> str:
        return f"OllamaLLMProvider(model={self.model}, format={self.format})"

    def __repr__(self) -> str:
        return self.__str__()

"""
OCR Provider 实现

所有 Provider 都从配置字典初始化，并使用 @register_provider 装饰器注册
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import requests
import json
import base64
import os
import logging
import io
from pathlib import Path
from PIL import Image, ImageOps

from ..types import OCRResult, FileType
from ..exceptions import OCRAPIServiceError
from .provider_registry import register_provider

# RapidOCR support
try:
    from rapidocr_onnxruntime import RapidOCR
    RapidOCR_AVAILABLE = True
except ImportError:
    RapidOCR = None
    RapidOCR_AVAILABLE = False


class OCRProvider(ABC):
    """OCR Provider 基类
    
    所有 Provider 都应该继承此类，并从配置字典初始化
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        初始化 Provider
        
        Args:
            config: 配置字典（包含通用配置和 Provider 特定配置）
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        
        # 从配置中提取通用参数
        self.debug = config.get('debug', False)
        self.max_image_size = config.get('max_image_size', 2048)
        self.jpeg_quality = config.get('jpeg_quality', 85)
    
    @abstractmethod
    def ocr_image(self, image_path: str) -> str:
        """
        Perform OCR on an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text string (纯文本)
        """
        pass
    
    def _log(self, message: str):
        """Log debug message"""
        if self.debug:
            self.logger.debug(message)
    
    def _compress_image(self, image_path: str) -> bytes:
        """
        压缩图片（通用方法，可被子类覆盖）
        
        Args:
            image_path: 图片路径
            
        Returns:
            压缩后的图片字节
        """
        max_size = self.max_image_size
        jpeg_quality = self.jpeg_quality
        
        try:
            with Image.open(image_path) as img:
                # 仅依据 EXIF Orientation 校正方向 (P0-8)。
                # 已删除"高宽比>1.5 且宽<2000 则强制旋转90°"的启发式——它会把手机竖拍证书
                # (1080x1920) 横置导致 OCR 乱码；方向只应由元数据决定，不由宽高比猜测。
                img = ImageOps.exif_transpose(img)

                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                width, height = img.size
                if max(width, height) > max_size:
                    ratio = max_size / max(width, height)
                    new_size = (int(width * ratio), int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=jpeg_quality)
                    return buffer.getvalue()
                else:
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=jpeg_quality)
                    return buffer.getvalue()
        except Exception as e:
            self.logger.warning(f"Image compression failed, using original: {e}")
            with open(image_path, "rb") as f:
                return f.read()


@register_provider("zhipu")
class ZhipuOCRProvider(OCRProvider):
    """
    Provider for Zhipu AI OCR using GLM-4V vision models

    使用 GLM-4V 多模态视觉模型进行 OCR 识别，支持多种模型：
    - glm-4.6v-flash: 最新免费视觉模型（推荐）
    - glm-4v: 标准视觉模型
    - glm-4v-plus: 增强视觉模型
    """

    # 默认模型列表（按优先级排序，用于失败时回退）
    DEFAULT_MODELS = ["glm-4.6v-flash", "glm-4v", "glm-4v-plus-0111"]
    # 默认提示词
    DEFAULT_PROMPT = "请识别图片中的所有文字内容，按原始排版顺序输出，保留文字的层次结构。请直接输出文字内容，不要添加任何解释或说明。"

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        # 从配置中读取 Zhipu 特定参数
        # 支持 api_key 或 api_key_env
        self.api_key = config.get('api_key', '')
        if not self.api_key:
            api_key_env = config.get('api_key_env', 'ZHIPUAI_API_KEY')
            self.api_key = os.getenv(api_key_env, '')

        self.api_url = config.get('api_url', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')

        # 模型配置：支持单个模型或模型列表（用于回退）
        model_config = config.get('model', 'glm-4.6v-flash')
        if isinstance(model_config, list):
            self.models = model_config
        else:
            self.models = [model_config]

        # 提示词配置
        self.prompt = config.get('prompt', self.DEFAULT_PROMPT)

        # 请求参数
        self.temperature = config.get('temperature', 0.1)
        self.max_tokens = config.get('max_tokens', 4096)
        self.timeout = config.get('timeout', 120)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 5)

        if not self.api_key:
            raise OCRAPIServiceError("Zhipu API key 未配置")

    def ocr_image(self, image_path: str) -> str:
        """使用 GLM-4V 模型进行 OCR 识别"""
        image_base64 = self._encode_image_to_base64(image_path)
        raw_data = self._call_api_with_retry(image_path, image_base64)
        text = self._build_text(raw_data)
        return text

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为 base64 格式"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_text(self, api_response: Dict[str, Any]) -> str:
        """从 API 响应中提取文本"""
        if "choices" in api_response and len(api_response["choices"]) > 0:
            content = api_response["choices"][0]["message"]["content"]
            return content.strip()
        else:
            self.logger.warning(f"Zhipu API 返回格式异常: {api_response}")
            return ""

    def _call_api_with_retry(self, image_path: str, image_base64: str) -> Dict[str, Any]:
        """带重试的 API 调用，支持多模型回退"""
        import time

        last_error = None

        # 遍历模型列表
        for model_idx, model in enumerate(self.models):
            self._log(f"尝试使用模型: {model} ({model_idx + 1}/{len(self.models)})")

            # 对每个模型进行重试
            for attempt in range(self.max_retries):
                try:
                    result = self._call_api(model, image_base64)
                    self.logger.info(f"Zhipu OCR 成功使用模型: {model}")
                    return result

                except requests.exceptions.HTTPError as e:
                    last_error = e
                    if e.response.status_code == 429:
                        # 频率限制，等待后重试
                        wait_time = self.retry_delay * (attempt + 1)
                        self.logger.warning(f"Zhipu API 频率限制 (429)，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    elif e.response.status_code >= 500:
                        # 服务器错误，短暂等待后重试
                        if attempt < self.max_retries - 1:
                            self.logger.warning(f"Zhipu API 服务器错误 ({e.response.status_code})，重试中...")
                            time.sleep(2)
                        else:
                            raise
                    else:
                        # 其他 HTTP 错误，直接抛出
                        raise OCRAPIServiceError(f"Zhipu API HTTP 错误: {e}")

                except Exception as e:
                    last_error = e
                    if attempt < self.max_retries - 1:
                        self.logger.warning(f"Zhipu API 调用失败: {e}，重试中...")
                        time.sleep(2)
                    else:
                        raise OCRAPIServiceError(f"Zhipu OCR API 调用失败: {e}")

        # 所有模型和重试都失败
        raise OCRAPIServiceError(f"所有 Zhipu 模型尝试均失败。最后错误: {last_error}")

    def _call_api(self, model: str, image_base64: str) -> Dict[str, Any]:
        """调用 GLM-4V API"""
        self._log(f"Calling Zhipu GLM-4V API with model: {model}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": self.prompt
                        }
                    ]
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


@register_provider("rapid")
class RapidOCRProvider(OCRProvider):
    """Provider for RapidOCR (local)"""
    
    # 类级别的共享实例（单例）
    _shared_ocr = None
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        if not RapidOCR_AVAILABLE:
            raise ImportError(
                "RapidOCR is not available. Please install: pip install rapidocr-onnxruntime"
            )
        self._ocr = None
    
    def _init_ocr(self):
        """延迟初始化 RapidOCR（使用单例模式）"""
        import os
        process_id = os.getpid()
        
        if RapidOCRProvider._shared_ocr is not None:
            self._ocr = RapidOCRProvider._shared_ocr
            return
        
        if self._ocr is None:
            try:
                self.logger.info(f"正在初始化 RapidOCR（首次初始化或实例丢失，进程ID: {process_id}）")
                RapidOCRProvider._shared_ocr = RapidOCR()
                self._ocr = RapidOCRProvider._shared_ocr
            except Exception as e:
                self.logger.error(f"RapidOCR 初始化失败: {e}")
                raise OCRAPIServiceError(f"RapidOCR 初始化失败: {e}")
    
    def ocr_image(self, image_path: str) -> str:
        self._init_ocr()
        self._log(f"Calling RapidOCR: {image_path}")
        try:
            result, _ = self._ocr(image_path)
            lines = []
            if result:
                for item in result:
                    if len(item) >= 2:
                        text = item[1]
                        lines.append(text)
            text = "\n".join(lines)
            return text
        except Exception as e:
            self.logger.error(f"RapidOCR failed: {e}")
            raise OCRAPIServiceError(f"RapidOCR failed: {e}")


@register_provider("baidu")
class BaiduOCRProvider(OCRProvider):
    """Provider for Baidu OCR"""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        # 从配置中读取 Baidu 特定参数
        # 支持 api_key 或 api_key_env
        self.api_key = config.get('api_key', '')
        if not self.api_key:
            api_key_env = config.get('api_key_env', 'BAIDU_API_KEY')
            self.api_key = os.getenv(api_key_env, '')

        # 支持 secret_key 或 secret_key_env
        self.secret_key = config.get('secret_key', '')
        if not self.secret_key:
            secret_key_env = config.get('secret_key_env', 'BAIDU_SECRET_KEY')
            self.secret_key = os.getenv(secret_key_env, '')

        self.api_url = config.get('api_url', 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic')

        if not self.api_key or not self.secret_key:
            raise OCRAPIServiceError("Baidu API key 或 secret key 未配置")
    
    def ocr_image(self, image_path: str) -> str:
        self._log(f"Calling Baidu OCR: {image_path}")
        access_token = self._get_access_token()
        if not access_token:
            raise OCRAPIServiceError("Failed to get Baidu Access Token")
        
        url = f"{self.api_url}?access_token={access_token}"
        
        try:
            with open(image_path, "rb") as f:
                img_data = f.read()
            
            b64_img = base64.b64encode(img_data).decode('utf-8')
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            payload = {
                'image': b64_img,
                'detect_direction': 'true',
                'detect_language': 'true',
                'paragraph': 'false',
                'probability': 'false'
            }
            
            resp = requests.post(url, headers=headers, data=payload)
            resp.encoding = "utf-8"
            result = resp.json()
            
            if "error_code" in result:
                raise OCRAPIServiceError(f"Baidu API Error: {result.get('error_msg')}")
            
            return self._build_text(result)
        except Exception as e:
            self.logger.error(f"Baidu OCR failed: {e}")
            raise OCRAPIServiceError(f"Baidu OCR failed: {e}")
    
    def _get_access_token(self) -> Optional[str]:
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        try:
            resp = requests.post(url, params=params).json()
            return str(resp.get("access_token"))
        except Exception as e:
            self.logger.error(f"Failed to get Baidu Token: {e}")
            return None
    
    def _build_text(self, ocr_data: Dict[str, Any]) -> str:
        words_result = ocr_data.get("words_result", [])
        lines = [item.get("words", "") for item in words_result]
        return "\n".join(lines)


@register_provider("paddle")
class PaddleOCRProvider(OCRProvider):
    """PaddleOCR Provider - 使用 PP-OCRv5 模型"""
    
    # 类级别的共享实例（单例）
    _shared_ocr = None
    _shared_config = None
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        # 从配置中读取 PaddleOCR 特定参数
        self.device = config.get('device', 'cpu')
        self.lang = config.get('lang', 'ch')
        self.ocr_version = config.get('ocr_version', 'PP-OCRv5')
        self.use_doc_orientation_classify = config.get('use_doc_orientation_classify', False)
        self.use_doc_unwarping = config.get('use_doc_unwarping', False)
        self.use_textline_orientation = config.get('use_textline_orientation', False)
        self._ocr = None
    
    def _init_ocr(self):
        """延迟初始化 PaddleOCR（使用单例模式）"""
        if PaddleOCRProvider._shared_ocr is not None:
            self._ocr = PaddleOCRProvider._shared_ocr
            self._log(f"复用已有的 PaddleOCR 实例 (device={self.device}, lang={self.lang})")
            return
        
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR as PaddleOCRClass
                import os
                
                os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
                os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")  # 国内源下载模型
                os.environ["PADDLP_LOG_LEVEL"] = "ERROR"
                os.environ["PADDLEOCR_LOG_LEVEL"] = "ERROR"
                os.environ["FLAGS_use_mkldnn"] = "0"   # 禁用 MKLDNN，避免 CPU 推理 NotImplementedError
                os.environ["FLAGS_use_dnnl"] = "0"     # 禁用 OneDNN（新 Paddle 命名）
                
                self.logger.info(f"正在初始化 PaddleOCR (device={self.device}, lang={self.lang}, ocr_version={self.ocr_version})")
                PaddleOCRProvider._shared_ocr = PaddleOCRClass(
                    use_doc_orientation_classify=self.use_doc_orientation_classify,
                    use_doc_unwarping=self.use_doc_unwarping,
                    use_textline_orientation=self.use_textline_orientation,
                    lang=self.lang,
                    ocr_version=self.ocr_version,
                    device=self.device,
                    det_limit_side_len=960,
                    det_limit_type='max'
                )
                self._ocr = PaddleOCRProvider._shared_ocr
                PaddleOCRProvider._shared_config = {
                    'device': self.device,
                    'lang': self.lang,
                    'ocr_version': self.ocr_version
                }
                #self.logger.info(f"PaddleOCR 初始化成功 (device={self.device}, lang={self.lang})")
            except ImportError as e:
                self.logger.error(f"PaddleOCR 导入失败: {e}")
                raise OCRAPIServiceError("PaddleOCR 未安装。请运行: pip install paddleocr")
            except Exception as e:
                self.logger.error(f"PaddleOCR 初始化异常: {e}")
                raise OCRAPIServiceError(f"PaddleOCR 初始化失败: {e}")
    
    def ocr_image(self, image_path: str) -> str:
        self._init_ocr()
        self._log(f"调用 PaddleOCR: {image_path}")
        
        try:
            results = self._ocr.ocr(image_path)
            text_lines = []
            
            if results:
                if isinstance(results, list) and len(results) > 0:
                    result = results[0]
                else:
                    result = results
                
                if isinstance(result, dict):
                    rec_texts = result.get('rec_texts', [])
                    if isinstance(rec_texts, str):
                        text_lines = [line.strip() for line in rec_texts.split('\n') if line.strip()]
                    elif isinstance(rec_texts, list):
                        for item in rec_texts:
                            if isinstance(item, str):
                                text_lines.append(item)
                            else:
                                text_lines.append(str(item))
                elif isinstance(result, list):
                    for line in result:
                        if line and len(line) > 1:
                            text_data = line[1]
                            if isinstance(text_data, (list, tuple)) and len(text_data) > 0:
                                text = text_data[0]
                                text_lines.append(str(text) if isinstance(text, str) else str(text))
                            elif isinstance(text_data, str):
                                text_lines.append(text_data)
            
            text_lines = [str(line) for line in text_lines if line]
            text = "\n".join(text_lines)
            
            if not isinstance(text, str):
                self.logger.warning(f"PaddleOCR返回的text不是字符串: {type(text)}, 转换为字符串")
                text = str(text)
            
            self.logger.info(f"PaddleOCR 完成，提取了 {len(text_lines)} 行文本，总长度: {len(text)}")
            return text
        except Exception as e:
            self.logger.error(f"PaddleOCR 失败: {e}")
            raise OCRAPIServiceError(f"PaddleOCR 失败: {e}")


# 向后兼容：ollama 指向 paddle
@register_provider("ollama")
class OllamaOCRProvider(PaddleOCRProvider):
    """向后兼容：ollama provider 指向 paddle"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        import warnings
        warnings.warn("ollama provider 已弃用，使用 paddle 代替", DeprecationWarning)
        super().__init__(config, logger)

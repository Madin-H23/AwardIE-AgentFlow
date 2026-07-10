"""
统一配置加载器
从 config/settings.json 和 .env 文件加载配置
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 尝试导入 dotenv，如果不存在则提供降级方案
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    import warnings
    warnings.warn("python-dotenv 未安装，将无法从 .env 文件加载环境变量。请运行: pip install python-dotenv")


class ConfigLoaderError(Exception):
    """配置加载器基础异常"""
    pass


class ConfigFileNotFoundError(ConfigLoaderError):
    """配置文件不存在"""
    pass


class ConfigParseError(ConfigLoaderError):
    """配置解析失败"""
    pass


class ConfigProviderNotFoundError(ConfigLoaderError):
    """供应商配置不存在"""
    pass


class ConfigLoader:
    """配置加载器"""

    def __init__(self, project_root: Optional[Path] = None):
        # 项目根目录是 config/ 的父目录，使用 resolve() 确保绝对路径（部署时工作目录可能不同）
        _raw = project_root or Path(__file__).resolve().parent.parent
        self.project_root = Path(_raw).resolve()
        self.config_path = self.project_root / "config" / "settings.json"
        self.env_path = self.project_root / ".env"

        # 加载环境变量
        if DOTENV_AVAILABLE and self.env_path.exists():
            load_dotenv(self.env_path)

        # 加载 apikey.json 到环境变量
        self.apikey_path = self.project_root / "apikey" / "apikey.json"
        self._load_api_keys()

        self._config = None

    def _load_api_keys(self):
        """从 apikey.json 加载 API Keys 到环境变量"""
        if self.apikey_path.exists():
            try:
                with open(self.apikey_path, 'r', encoding='utf-8') as f:
                    api_keys = json.load(f)
                    
                # 遍历并将 Keys 设置到环境变量
                # 假设结构为 { "ocr": { "ZHIPUAI_API_KEY": "..." }, "llm": { ... } }
                # 或者扁平结构，或者按 provider 分组。
                # 为了通用性，我们假设它存储的是 { "ENV_VAR_NAME": "value" } 或者是按模块分组的
                # 根据之前的 apikey.json 结构假设，它可能类似于 settings.json 的结构
                # 但为了简单和兼容性，我们只提取其中的 value 并设置到对应的 env var
                
                # 递归查找所有键值对，如果 key 看起来像环境变量（大写），则设置它
                # 或者，我们可以更智能一点：读取 settings.json 找到对应的 env var name，然后从 apikey.json 中取值
                # 但这里我们简单处理：假设 apikey.json 存储的是 {"ZHIPUAI_API_KEY": "xxx"} 这种扁平结构，或者
                # {"ocr": {"zhipu": "key"}, "llm": ...}
                
                # 让我们定义 apikey.json 的结构为:
                # {
                #   "ocr": { "zhipu": "key_value", "baidu": "key_value" },
                #   "llm": { "zhipu": "key_value", ... }
                # }
                # 这种结构比较清晰。我们需要配合 settings.json 中的 `api_key_env` 映射。
                # 但 ConfigLoader 在这里还不知道 settings.json 的内容（load_config 还没调）。
                # 所以，最简单的方式是：在 load_config 中合并处理。
                
                # 暂时先不做处理，留给 load_config 或者专门的方法。
                pass
            except Exception as e:
                # 此时 logging 可能还没配置好，直接 print 或忽略
                print(f"Warning: Failed to load apikey.json: {e}")

    def load_api_keys_into_env(self, settings_config: Dict[str, Any]):
        """
        根据 settings 配置，从 apikey.json 加载 Keys 并注入环境变量
        
        Args:
            settings_config: 已加载的 settings.json 配置字典
        """
        if not self.apikey_path.exists():
            return

        try:
            with open(self.apikey_path, 'r', encoding='utf-8') as f:
                user_keys = json.load(f)
        except Exception:
            return

        # 处理 OCR Keys
        if 'ocr' in settings_config and 'providers' in settings_config['ocr']:
            for name, provider_conf in settings_config['ocr']['providers'].items():
                env_var = provider_conf.get('api_key_env')
                # 尝试从 user_keys['ocr'][name] 获取
                user_key = user_keys.get('ocr', {}).get(name)
                if env_var and user_key:
                    os.environ[env_var] = user_key
                    
                # 处理 secret_key (如百度)
                secret_env = provider_conf.get('secret_key_env')
                user_secret = user_keys.get('ocr', {}).get(f"{name}_secret")
                if secret_env and user_secret:
                    os.environ[secret_env] = user_secret

        # 处理 LLM Keys
        if 'llm' in settings_config and 'providers' in settings_config['llm']:
            for name, provider_conf in settings_config['llm']['providers'].items():
                env_var = provider_conf.get('api_key_env')
                user_key = user_keys.get('llm', {}).get(name)
                if env_var and user_key:
                    os.environ[env_var] = user_key
        
        # 处理 PDF Keys
        if 'pdf' in settings_config and 'providers' in settings_config['pdf']:
             for name, provider_conf in settings_config['pdf']['providers'].items():
                env_var = provider_conf.get('api_key_env')
                user_key = user_keys.get('pdf', {}).get(name)
                if env_var and user_key:
                    os.environ[env_var] = user_key

    def _strip_json_comments(self, content: str) -> str:
        """
        移除 JSON 文件中的注释（支持 // 和 /* */ 格式）
        
        Args:
            content: JSON 文件内容
            
        Returns:
            移除注释后的 JSON 内容
        """
        lines = content.split('\n')
        result = []
        in_multiline_comment = False
        
        for line in lines:
            # 处理多行注释
            if in_multiline_comment:
                if '*/' in line:
                    # 多行注释结束
                    line = line[line.index('*/') + 2:]
                    in_multiline_comment = False
                else:
                    # 仍在多行注释中，跳过整行
                    continue
            
            # 查找多行注释开始
            if '/*' in line:
                comment_start = line.index('/*')
                # 检查是否在同一行结束
                if '*/' in line:
                    comment_end = line.index('*/')
                    line = line[:comment_start] + line[comment_end + 2:]
                else:
                    line = line[:comment_start]
                    in_multiline_comment = True
            
            # 移除单行注释（//）
            if '//' in line:
                # 检查是否在字符串中
                in_string = False
                escape_next = False
                comment_pos = -1
                
                for i, char in enumerate(line):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                    if not in_string and char == '/' and i + 1 < len(line) and line[i + 1] == '/':
                        comment_pos = i
                        break
                
                if comment_pos >= 0:
                    line = line[:comment_pos].rstrip()
            
            result.append(line)
        
        return '\n'.join(result)

    def load_config(self) -> Dict[str, Any]:
        """加载主配置文件 (config/settings.json)，支持注释"""
        if self._config is None:
            try:
                if not self.config_path.exists():
                    raise ConfigFileNotFoundError(
                        f"配置文件不存在: {self.config_path}"
                    )
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 移除注释
                    content = self._strip_json_comments(content)
                    self._config = json.loads(content)
            except ConfigLoaderError as e:
                # 解析错误，直接抛出
                raise e
            except Exception as e:
                raise ConfigParseError(f"加载配置文件失败: {str(e)}")

        # 尝试加载 API Keys
        self.load_api_keys_into_env(self._config)

        return self._config

    def reload(self):
        """强制重新加载配置"""
        self._config = None
        return self.load_config()


    def get_provider_config(self, module: str, provider: str) -> Dict[str, Any]:
        """
        获取特定供应商的配置，自动替换环境变量

        Args:
            module: 'ocr' 或 'llm'
            provider: 供应商名称

        Returns:
            供应商配置字典（环境变量已替换）

        Raises:
            ValueError: 当模块名无效时
            ConfigProviderNotFoundError: 当供应商不存在时
        """
        if module not in ['ocr', 'llm']:
            raise ValueError(f"无效的模块名: {module}，必须是 'ocr' 或 'llm'")

        config = self.load_config()

        if module not in config:
            raise ConfigProviderNotFoundError(f"模块配置不存在: {module}")

        if "providers" not in config[module]:
            raise ConfigProviderNotFoundError(f"模块 '{module}' 缺少 'providers' 配置")

        if provider not in config[module]["providers"]:
            available = list(config[module]["providers"].keys())
            raise ConfigProviderNotFoundError(
                f"供应商 '{provider}' 在模块 '{module}' 中不存在。"
                f"可用的供应商: {available}"
            )

        # 复制配置并替换环境变量
        provider_config = config[module]["providers"][provider].copy()
        return self._replace_env_refs(provider_config)

    def get_default_provider(self, module: str) -> str:
        """获取模块的默认供应商"""
        config = self.load_config()
        if module not in config:
            raise ConfigProviderNotFoundError(f"模块配置不存在: {module}")
        return config[module].get("default_provider", "")
    
    def get_path(self, *path_keys: str) -> Path:
        """
        获取配置中的路径（相对于项目根目录）
        
        Args:
            *path_keys: 路径键，例如 get_path('database', 'competitions_db') 或 get_path('files')
        
        Returns:
            Path对象（相对于项目根目录）
        
        Raises:
            KeyError: 当路径键不存在时
        """
        config = self.load_config()
        value = config
        for key in path_keys:
            if not isinstance(value, dict) or key not in value:
                raise KeyError(f"配置路径不存在: {' -> '.join(path_keys)}")
            value = value[key]
        
        if not isinstance(value, str):
            raise ValueError(f"配置值不是字符串: {' -> '.join(path_keys)}")
        
        # 返回绝对路径，避免部署时因工作目录不同导致路径解析错误
        return (self.project_root / value).resolve()
    
    def get_path_str(self, *path_keys: str) -> str:
        """
        获取配置中的路径字符串（相对于项目根目录）
        
        Args:
            *path_keys: 路径键，例如 get_path_str('database', 'competitions_db') 或 get_path_str('files')
        
        Returns:
            路径字符串（相对于项目根目录）
        """
        return str(self.get_path(*path_keys))

    def _replace_env_refs(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """替换配置中的环境变量引用"""
        result = {}
        for key, value in config.items():
            if isinstance(value, str):
                # 检查是否是环境变量引用 (xxx_env 格式)
                if key.endswith("_env") or "_env:" in value:
                    # 处理 api_key_env: "VAR_NAME" 格式
                    if value.startswith("${") and value.endswith("}"):
                        env_var = value[2:-1]
                        result[key.replace("_env", "")] = os.getenv(env_var, "")
                    else:
                        # 直接从环境变量读取
                        result[key.replace("_env", "")] = os.getenv(value, os.getenv(key, ""))
                else:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._replace_env_refs(value)
            else:
                result[key] = value
        return result

    def validate(self) -> bool:
        """
        验证配置是否有效

        Returns:
            True 如果配置有效

        Raises:
            ConfigLoaderError: 当配置无效时
        """
        config = self.load_config()

        # 验证必需的顶级键
        required_keys = ['ocr', 'llm']
        for key in required_keys:
            if key not in config:
                raise ConfigLoaderError(f"配置文件缺少必需的键: {key}")

        # 验证默认供应商配置
        for module in ['ocr', 'llm']:
            default_provider = config[module].get('default_provider')
            if not default_provider:
                raise ConfigLoaderError(f"{module} 模块缺少默认供应商配置")

            if "providers" not in config[module]:
                raise ConfigLoaderError(f"{module} 模块缺少 'providers' 配置")

            if default_provider not in config[module]["providers"]:
                available = list(config[module]["providers"].keys())
                raise ConfigLoaderError(
                    f"{module} 模块的默认供应商 '{default_provider}' "
                    f"在 providers 中不存在。可用的供应商: {available}"
                )

        return True


# 全局单例
_loader = None

def get_config() -> ConfigLoader:
    """获取全局配置加载器实例"""
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
    return _loader

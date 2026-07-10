import os
import json
import unittest
import tempfile
import shutil
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.loader import ConfigLoader

class TestConfigLoaderApiKey(unittest.TestCase):
    def setUp(self):
        # 创建临时目录结构
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_dir = self.test_dir / "config"
        self.apikey_dir = self.test_dir / "apikey"
        self.config_dir.mkdir()
        self.apikey_dir.mkdir()
        
        # 创建 settings.json
        self.settings_content = {
            "ocr": {
                "providers": {
                    "zhipu": {"api_key_env": "ZHIPUAI_API_KEY"}
                }
            },
            "llm": {
                "providers": {
                    "deepseek": {"api_key_env": "DEEPSEEK_API_KEY"}
                }
            }
        }
        with open(self.config_dir / "settings.json", "w") as f:
            json.dump(self.settings_content, f)
            
        # 创建 apikey.json
        self.apikey_content = {
            "ocr": {"zhipu": "test_zhipu_key"},
            "llm": {"deepseek": "test_deepseek_key"}
        }
        with open(self.apikey_dir / "apikey.json", "w") as f:
            json.dump(self.apikey_content, f)
            
        # 初始化 ConfigLoader
        self.loader = ConfigLoader(project_root=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        # 清理环境变量
        if "ZHIPUAI_API_KEY" in os.environ:
            del os.environ["ZHIPUAI_API_KEY"]
        if "DEEPSEEK_API_KEY" in os.environ:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_load_api_keys(self):
        # 确保环境变量初始为空
        if "ZHIPUAI_API_KEY" in os.environ:
            del os.environ["ZHIPUAI_API_KEY"]
            
        # 加载配置
        config = self.loader.load_config()
        
        # 验证环境变量是否被注入
        self.assertEqual(os.environ.get("ZHIPUAI_API_KEY"), "test_zhipu_key")
        self.assertEqual(os.environ.get("DEEPSEEK_API_KEY"), "test_deepseek_key")
        
        print("ConfigLoader successfully loaded API keys into environment variables.")

if __name__ == "__main__":
    unittest.main()

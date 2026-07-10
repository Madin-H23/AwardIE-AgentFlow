
import unittest
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.loader import ConfigLoader

class TestConfigLoaderDebug(unittest.TestCase):
    def test_load_config(self):
        loader = ConfigLoader()
        config = loader.load_config()
        
        print(f"DEBUG: Config keys: {config.keys()}")
        
        if 'ocr' in config:
            print(f"DEBUG: OCR providers: {config['ocr'].get('providers', {}).keys()}")
        else:
            print("DEBUG: 'ocr' key not found in config")
            
        if 'llm' in config:
            print(f"DEBUG: LLM providers: {config['llm'].get('providers', {}).keys()}")
        else:
            print("DEBUG: 'llm' key not found in config")

        self.assertIn('ocr', config)
        self.assertIn('llm', config)
        self.assertTrue(len(config['ocr']['providers']) > 0)
        self.assertTrue(len(config['llm']['providers']) > 0)

if __name__ == '__main__':
    unittest.main()

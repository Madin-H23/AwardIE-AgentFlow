
import unittest
import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.loader import get_config

class TestAdminSettingsLogic(unittest.TestCase):
    def test_settings_logic(self):
        # Simulate the logic in admin.py settings() function
        config_loader = get_config()
        app_config = config_loader.load_config()
        
        available_ocr_providers = []
        providers_config = {"ocr": {}, "llm": {}}
        
        # Simulate loading user keys (mocking)
        user_keys = {} 
        
        # OCR logic
        if 'ocr' in app_config and 'providers' in app_config['ocr']:
            for name, conf in app_config['ocr']['providers'].items():
                available_ocr_providers.append(name)
                api_key_env = conf.get('api_key_env')
                current_key = user_keys.get('ocr', {}).get(name, '')
                providers_config['ocr'][name] = {
                    'needs_key': bool(api_key_env),
                    'api_key': current_key,
                    'type': conf.get('type')
                }
        
        print(f"OCR Providers: {available_ocr_providers}")
        print(f"Providers Config: {json.dumps(providers_config, indent=2)}")
        
        self.assertTrue(len(available_ocr_providers) > 0)
        self.assertIn('zhipu', providers_config['ocr'])
        self.assertTrue(providers_config['ocr']['zhipu']['needs_key'])

if __name__ == '__main__':
    unittest.main()

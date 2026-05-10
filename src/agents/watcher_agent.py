from typing import Dict, Any, Optional
from tools.web_tools import WebScraperTool
from tools.ocr_tools import BatchOCRTool
import hashlib
import json


class WatcherAgent:
    def __init__(self):
        self.scraper = WebScraperTool()
        self.ocr_tool = BatchOCRTool()
        self.last_hash = None
        self.last_content = None

    def check_website(self, url: str) -> Dict[str, Any]:
        try:
            result_str = self.scraper._run(url)
            result = json.loads(result_str)
            
            content = result.get('text', '')
            images = result.get('images', [])
            
            current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            is_changed = self.last_hash is None or current_hash != self.last_hash
            is_first = self.last_hash is None
            
            old_content = self.last_content
            
            self.last_hash = current_hash
            self.last_content = content
            
            ocr_results = []
            if images and len(images) > 0:
                try:
                    ocr_results = self.ocr_tool._run(images[:3])
                except Exception:
                    pass
            
            return {
                'content': content,
                'images': images,
                'is_changed': is_changed,
                'is_first': is_first,
                'old_content': old_content,
                'ocr_results': ocr_results
            }
        
        except Exception as e:
            return {
                'content': '',
                'images': [],
                'is_changed': False,
                'is_first': False,
                'old_content': None,
                'ocr_results': [],
                'error': str(e)
            }

    def reset(self):
        self.last_hash = None
        self.last_content = None
import sys
import os
import time
import json
import hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_WEBSITE, MONITOR_INTERVAL
from agents.supervisor_agent import (
    SupervisorAgent,
    WatcherAgent,
    ExtractionAgent,
    AnalyzerAgent,
    StorageAgent,
    OCRProcessor,
)
from agents.database_agent import DatabaseAgent
from tools.web_tools import WebScraperTool


class MultiAgentSystem:
    def __init__(self):
        print("=" * 60)
        print("初始化多Agent协同监控系统")
        print("=" * 60)

        self.supervisor = SupervisorAgent()
        self.watcher = WatcherAgent()
        self.extractor = ExtractionAgent()
        self.analyzer = AnalyzerAgent()
        self.storage = StorageAgent()
        self.ocr = OCRProcessor()
        self.db = DatabaseAgent()

        self.last_hash = None
        self.last_content = None

        print("Agent初始化完成")
        print(f"监控目标: {TARGET_WEBSITE}")
        print(f"检查间隔: {MONITOR_INTERVAL}秒")
        print("=" * 60)

    def check_website(self, url: str) -> dict:
        print(f"\n[{datetime.now()}] 检查网站变化...")

        scraper = WebScraperTool()
        content = scraper._run(url)

        if not content or content.startswith("抓取失败"):
            print(f"获取内容失败: {content}")
            return {"success": False, "error": content}

        current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        if self.last_hash and current_hash == self.last_hash:
            print("内容无变化")
            return {
                "success": True,
                "changed": False,
                "hash": current_hash
            }

        print("检测到内容变化!")
        extracted_data = self.extractor.extract_structured_data(content)

        old_data = None
        if self.last_content:
            old_data = self.extractor.extract_structured_data(self.last_content)

        change_analysis = None
        if old_data:
            change_analysis = self.analyzer.analyze_change(
                self.last_content or "",
                content
            )

        keywords = self.supervisor._generate_keywords(content)

        website_id = self.db.get_or_create_website(url)
        if website_id:
            self.db.store_data(
                website_id=website_id,
                title=extracted_data.get("title", ""),
                content=json.dumps(extracted_data, ensure_ascii=False),
                keywords=keywords,
                change_type="updated"
            )

            if old_data:
                self.db.record_changes(website_id, old_data, extracted_data)

        self.last_hash = current_hash
        self.last_content = content

        return {
            "success": True,
            "changed": True,
            "hash": current_hash,
            "extracted_data": extracted_data,
            "keywords": keywords,
            "change_analysis": change_analysis
        }

    def run(self):
        print("\n开始监控...")
        try:
            while True:
                result = self.check_website(TARGET_WEBSITE)

                if result.get("changed"):
                    print("\n--- 变化详情 ---")
                    print(f"标题: {result['extracted_data'].get('title', 'N/A')}")
                    print(f"关键词: {', '.join(result.get('keywords', [])[:5])}")
                    print(f"主要变化: {result.get('change_analysis', {}).get('analysis', 'N/A')[:200]}")

                time.sleep(MONITOR_INTERVAL)

        except KeyboardInterrupt:
            print("\n监控已停止")


if __name__ == "__main__":
    system = MultiAgentSystem()
    system.run()
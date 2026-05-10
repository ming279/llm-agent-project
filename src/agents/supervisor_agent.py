from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from services.qwen_llm import llm_service
from tools.web_tools import WebScraperTool, ContentHasherTool
from tools.ocr_tools import OCRTool, BatchOCRTool
from tools.db_tools import DatabaseTool, QueryHistoryTool


class SupervisorAgent:
    def __init__(self):
        self.llm = llm_service
        self.tools = self._create_tools()
        self.tool_map = {t.name: t for t in self.tools}

    def _create_tools(self):
        return [
            WebScraperTool(),
            ContentHasherTool(),
            OCRTool(),
            BatchOCRTool(),
            DatabaseTool(),
            QueryHistoryTool(),
        ]

    def _create_supervisor_prompt(self):
        system_prompt = """你是一个网站监控系统的Supervisor Agent，负责协调多个专业Agent工作。

可用Agent及其职责：
1. web_scraper - 抓取网页内容
2. content_hasher - 计算内容哈希，检测变化
3. ocr_recognizer - 识别图片中的文字
4. batch_ocr - 批量识别多张图片
5. database_storage - 存储数据到数据库
6. query_history - 查询历史记录

协调流程：
1. 接收监控任务（如：监控 https://news.cctv.com/）
2. 调用 web_scraper 抓取网页内容
3. 调用 content_hasher 计算内容哈希
4. 如果内容有变化：
   - 提取关键数据
   - 调用 ocr_recognizer 识别图片（如有）
   - 调用 database_storage 存储新数据
5. 生成总结报告

请按顺序调用合适的Agent完成监控任务。"""

        return ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content="{task}"),
        ])

    def execute_task(self, task: str) -> Dict[str, Any]:
        result = {
            "task": task,
            "status": "processing",
            "steps": [],
            "result": None,
            "error": None
        }

        try:
            supervisor_chain = self._create_supervisor_prompt() | self.llm | StrOutputParser()
            response = supervisor_chain.invoke({"task": task})
            result["result"] = response
            result["status"] = "completed"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    def monitor_website(self, url: str, previous_hash: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "url": url,
            "changed": False,
            "content": None,
            "hash": None,
            "ocr_results": [],
            "keywords": None,
            "summary": None,
        }

        try:
            scraper = WebScraperTool()
            content = scraper._run(url)
            result["content"] = content

            hasher = ContentHasherTool()
            current_hash = hasher._run(content)
            result["hash"] = current_hash

            if previous_hash and current_hash == previous_hash:
                return result

            result["changed"] = True
            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def analyze_and_store(self, url: str, content: str, extracted_data: Dict) -> Dict[str, Any]:
        result = {
            "url": url,
            "stored": False,
            "keywords": None,
            "change_type": "new",
        }

        try:
            keywords = self._generate_keywords(content)
            result["keywords"] = keywords

            data = {
                "website_url": url,
                "title": extracted_data.get("title", ""),
                "content": content[:500],
                "keywords": keywords,
                "change_type": "new"
            }

            db_tool = DatabaseTool()
            storage_result = db_tool._run(json.dumps(data, ensure_ascii=False))
            result["storage_result"] = storage_result
            result["stored"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def _generate_keywords(self, text: str) -> List[str]:
        prompt = f"""请从以下网页内容中提取10个最重要的关键词，用逗号分隔：

{text[:2000]}

关键词："""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            keywords = [k.strip() for k in response.content.split(',') if k.strip()]
            return keywords[:10]
        except Exception as e:
            return ["关键词提取失败"]


import json


class WatcherAgent:
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.last_hash = None
        self.last_content = None

    def check_for_changes(self, url: str) -> Dict[str, Any]:
        result = self.supervisor.monitor_website(url, self.last_hash)

        if result["changed"]:
            self.last_hash = result["hash"]
            self.last_content = result["content"]

        return result

    def process_change(self, url: str, content: str, extracted_data: Dict) -> Dict[str, Any]:
        return self.supervisor.analyze_and_store(url, content, extracted_data)


class ExtractionAgent:
    def __init__(self):
        self.llm = llm_service

    def extract_structured_data(self, content: str) -> Dict[str, Any]:
        prompt = f"""请从以下网页内容中提取结构化数据，返回JSON格式：

{content[:3000]}

请提取：
- title: 页面标题
- main_content: 主要内容摘要（不超过200字）
- key_points: 关键点列表（不超过5个）
- sentiment: 情感倾向（positive/negative/neutral）

JSON格式输出："""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            import json
            data = json.loads(response.content)
            return data
        except:
            return {
                "title": "提取失败",
                "main_content": content[:200],
                "key_points": [],
                "sentiment": "neutral"
            }


class AnalyzerAgent:
    def __init__(self):
        self.llm = llm_service
        self.extraction_agent = ExtractionAgent()

    def analyze_change(self, old_content: str, new_content: str) -> Dict[str, Any]:
        prompt = f"""请比较以下两段内容，找出变化的地方：

旧内容：
{old_content[:1000]}

新内容：
{new_content[:1000]}

请分析：
1. 主要变化是什么？
2. 新增了什么内容？
3. 删除了什么内容？
4. 给出简短总结"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return {
                "analysis": response.content,
                "has_significant_change": len(new_content) != len(old_content)
            }
        except Exception as e:
            return {"analysis": str(e), "has_significant_change": False}


class StorageAgent:
    def __init__(self):
        self.db_tool = DatabaseTool()

    def save_monitoring_result(self, url: str, data: Dict) -> bool:
        try:
            result = self.db_tool._run(json.dumps(data, ensure_ascii=False))
            return "存储成功" in result
        except Exception:
            return False

    def query_history(self, url: str) -> str:
        query_tool = QueryHistoryTool()
        return query_tool._run(url)


class OCRProcessor:
    def __init__(self):
        self.ocr_tool = OCRTool()
        self.batch_ocr = BatchOCRTool()

    def recognize_single(self, image_url: str) -> str:
        return self.ocr_tool._run(image_url)

    def recognize_batch(self, image_urls: List[str]) -> List[Dict[str, str]]:
        result = self.batch_ocr._run(json.dumps(image_urls))
        items = []
        for line in result.split('\n'):
            if ':' in line:
                idx, text = line.split(':', 1)
                items.append({"index": idx.strip(), "text": text.strip()})
        return items
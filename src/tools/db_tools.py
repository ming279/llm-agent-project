from typing import Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import Field
import json


class DatabaseTool(BaseTool):
    name: str = "database_storage"
    description: str = """存储网站监控数据到数据库。
输入: JSON格式的数据，包含以下字段:
- website_url: 网站URL
- title: 页面标题
- content: 页面内容摘要
- keywords: 关键词列表
- change_type: 变化类型(new/updated/unchanged)
输出: 存储结果"""

    db_agent: Any = Field(default=None, exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.db_agent = self._get_db_agent()

    def _get_db_agent(self):
        from agents.database_agent import DatabaseAgent
        return DatabaseAgent()

    def _run(
        self,
        data: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            data_dict = json.loads(data)
            website_id = self.db_agent.get_or_create_website(
                data_dict.get('website_url', '')
            )
            if website_id:
                result = self.db_agent.store_data(
                    website_id=website_id,
                    title=data_dict.get('title', ''),
                    content=data_dict.get('content', ''),
                    keywords=data_dict.get('keywords', []),
                    change_type=data_dict.get('change_type', 'new')
                )
                return f"存储成功: {result}"
            return "数据库操作失败"
        except Exception as e:
            return f"存储失败: {str(e)}"

    async def _arun(
        self,
        data: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(data, run_manager)


class QueryHistoryTool(BaseTool):
    name: str = "query_history"
    description: str = """查询网站历史记录。
输入: 网站URL
输出: 该网站的历史记录列表"""

    db_agent: Any = Field(default=None, exclude=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.db_agent = self._get_db_agent()

    def _get_db_agent(self):
        from agents.database_agent import DatabaseAgent
        return DatabaseAgent()

    def _run(
        self,
        website_url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            website_id = self.db_agent.get_or_create_website(website_url)
            history = self.db_agent.get_history(website_id)
            if history:
                return json.dumps(history, ensure_ascii=False, indent=2)
            return "无历史记录"
        except Exception as e:
            return f"查询失败: {str(e)}"

    async def _arun(
        self,
        website_url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(website_url, run_manager)
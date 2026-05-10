from typing import Optional, Dict, Any
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import Field
import requests
from bs4 import BeautifulSoup
import hashlib


class WebScraperTool(BaseTool):
    name: str = "web_scraper"
    description: str = """获取指定网址的HTML内容并提取可见文本和图片URL。
输入: URL网址
输出: 包含可见文本内容和图片URL列表的JSON字符串"""

    def _run(
        self,
        url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')

            for tag in soup.find_all(['script', 'style', 'noscript']):
                tag.decompose()

            result = {
                "text": "",
                "images": []
            }

            visible_content = []
            if soup.title and soup.title.string:
                visible_content.append(f"标题: {soup.title.string.strip()}")

            for h in soup.find_all(['h1', 'h2', 'h3']):
                text = h.get_text().strip()
                if text:
                    visible_content.append(f"标题: {text}")

            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text:
                    visible_content.append(f"段落: {text}")

            for a in soup.find_all('a', href=True):
                text = a.get_text().strip()
                if text:
                    visible_content.append(f"链接: {text}")

            result["text"] = "\n".join(visible_content) if visible_content else "未提取到内容"

            for img in soup.find_all('img', src=True):
                img_src = img['src']
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    from urllib.parse import urljoin
                    img_src = urljoin(url, img_src)
                
                if img_src.startswith('http'):
                    result["images"].append(img_src)

            import json
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            import json
            return json.dumps({"text": f"抓取失败: {str(e)}", "images": []})

    async def _arun(
        self,
        url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(url, run_manager)


class ContentHasherTool(BaseTool):
    name: str = "content_hasher"
    description: str = """计算文本内容的MD5哈希值，用于检测内容变化。
输入: 任意文本
输出: MD5哈希值"""

    def _run(
        self,
        text: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    async def _arun(
        self,
        text: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(text, run_manager)
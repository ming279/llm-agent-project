from typing import List, Optional
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import Field
import requests
from io import BytesIO
import os
import traceback

try:
    import pytesseract
    from PIL import Image
    
    if os.path.exists('C:\\Program Files\\Tesseract-OCR\\tesseract.exe'):
        pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    elif os.path.exists('C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe'):
        pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe'
    
    TESSERACT_AVAILABLE = True
except ImportError as e:
    TESSERACT_AVAILABLE = False
    TESSERACT_ERROR = f"导入失败: {str(e)}"
except Exception as e:
    TESSERACT_AVAILABLE = False
    TESSERACT_ERROR = f"初始化失败: {str(e)}"


class OCRTool(BaseTool):
    name: str = "ocr_recognizer"
    description: str = """识别图片中的文字。
输入: 图片URL、图片文件路径或base64编码的图片数据
输出: 图片中的文字内容"""

    def _run(
        self,
        image_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        if not TESSERACT_AVAILABLE:
            return f"OCR识别不可用: {TESSERACT_ERROR}"

        try:
            image = None
            
            if image_input.startswith('http'):
                try:
                    response = requests.get(image_input, timeout=10)
                    response.raise_for_status()
                    content_type = response.headers.get('content-type', '')
                    if 'svg' in content_type.lower():
                        return "无法识别SVG格式图片"
                    if 'webp' in content_type.lower():
                        return "无法识别WebP格式图片"
                    image = Image.open(BytesIO(response.content))
                except Exception as e:
                    return f"图片下载失败: {str(e)[:30]}"
            elif image_input.startswith('data:image'):
                try:
                    import base64
                    header, encoded = image_input.split(',', 1)
                    image_data = base64.b64decode(encoded)
                    image = Image.open(BytesIO(image_data))
                except Exception as e:
                    return f"base64图片解码失败: {str(e)}"
            elif os.path.isfile(image_input):
                try:
                    image = Image.open(image_input)
                except Exception as e:
                    return f"文件打开失败: {str(e)}"
            else:
                try:
                    import base64
                    image_data = base64.b64decode(image_input)
                    image = Image.open(BytesIO(image_data))
                except Exception:
                    return f"无法识别图片输入: 不是有效的URL、文件路径或base64编码数据"

            if image is None:
                return "无法加载图片"
            
            image = image.convert('RGB')
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip() if text.strip() else "未识别到文字"

        except requests.exceptions.RequestException as e:
            return "图片下载失败"
        except Exception as e:
            return "OCR识别失败"

    async def _arun(
        self,
        image_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(image_input, run_manager)


class BatchOCRTool(BaseTool):
    name: str = "batch_ocr"
    description: str = """批量识别多张图片中的文字。
输入: JSON格式的图片URL列表，如: ['url1', 'url2']
输出: 每张图片识别结果的列表"""

    def _run(
        self,
        image_urls: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        if not TESSERACT_AVAILABLE:
            return f"OCR识别不可用: {TESSERACT_ERROR}"

        try:
            import json
            urls = json.loads(image_urls)
            if not isinstance(urls, list):
                return "输入必须是图片URL列表"

            results = []
            ocr_tool = OCRTool()

            for i, url in enumerate(urls):
                result = ocr_tool._run(url)
                results.append(f"图片{i+1}: {result}")

            return "\n".join(results)

        except json.JSONDecodeError as e:
            return f"JSON解析失败: {str(e)}"
        except Exception as e:
            return f"批量OCR失败: {str(e)}\n{traceback.format_exc()}"

    async def _arun(
        self,
        image_urls: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(image_urls, run_manager)
from typing import Optional
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import Field
import os
import time
import base64
import re
from io import BytesIO
import threading


def find_edge_driver():
    import glob
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\*\msedgedriver.exe",
        r"C:\Program Files\Microsoft\Edge\Application\*\msedgedriver.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\*\msedgedriver.exe")
    ]
    
    for pattern in edge_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[-1]
    return None


_driver = None
_driver_lock = threading.Lock()
_driver_creation_time = 0
_max_driver_age = 300  
_driver_path = None


class ScreenshotTool(BaseTool):
    name: str = "website_screenshot"
    description: str = """对指定网址进行截图。
输入: URL网址，可选参数: full_page=True表示长截图，默认为False
输出: 截图图片的base64编码或保存路径"""

    @classmethod
    def _init_driver(cls):
        global _driver, _driver_path, _driver_creation_time
        if _driver is not None:
            try:
                _driver.quit()
            except:
                pass
            _driver = None
        
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service
        
        edge_options = Options()
        edge_options.add_argument('--headless=new')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--window-size=2560,1440')
        edge_options.add_argument('--force-device-scale-factor=1.5')
        edge_options.add_argument('--high-dpi-support=1')
        edge_options.add_argument('--enable-features=VaapiVideoDecoder')
        edge_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')
        edge_options.add_argument('--disable-extensions')
        edge_options.add_argument('--disable-plugins')
        edge_options.add_argument('--ignore-certificate-errors')
        edge_options.add_argument('--allow-running-insecure-content')
        edge_options.add_argument('--disable-web-security')
        edge_options.add_argument('--disable-software-rasterizer')
        edge_options.add_argument('--disable-dev-shm-usage')
        
        driver_path = _driver_path
        if not driver_path:
            driver_path = find_edge_driver()
            _driver_path = driver_path
        
        if driver_path:
            try:
                _driver = webdriver.Edge(service=Service(driver_path), options=edge_options)
                _driver.set_page_load_timeout(20)
                _driver_creation_time = time.time()
                return _driver
            except Exception as e:
                return None
        else:
            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                _driver = webdriver.Edge(
                    service=Service(EdgeChromiumDriverManager().install()),
                    options=edge_options
                )
                _driver.set_page_load_timeout(20)
                _driver_creation_time = time.time()
                return _driver
            except ImportError:
                return None
            except Exception as e:
                return None

    @classmethod
    def _get_driver(cls):
        global _driver, _driver_lock, _driver_creation_time, _max_driver_age
        with _driver_lock:
            if _driver is None:
                return cls._init_driver()
            
            age = time.time() - _driver_creation_time
            if age > _max_driver_age:
                cls._init_driver()
            
            try:
                _driver.current_url
                return _driver
            except Exception:
                return cls._init_driver()

    @classmethod
    def _quit_driver(cls):
        global _driver, _driver_lock
        with _driver_lock:
            if _driver is not None:
                try:
                    _driver.quit()
                except:
                    pass
                _driver = None

    def _run(
        self,
        url: str,
        full_page: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            global _driver
            driver = self._get_driver()
            if driver is None:
                return "截图失败: 无法初始化浏览器"
            
            try:
                driver.get(url)
            except Exception as e:
                self._init_driver()
                driver = self._get_driver()
                if driver is None:
                    return f"截图失败: 无法访问网站 - {str(e)}"
                try:
                    driver.get(url)
                except Exception as e2:
                    return f"截图失败: 无法访问网站 - {str(e2)}"
            
            self._wait_for_page_load(driver)
            
            if full_page:
                screenshot = self._capture_full_page(driver)
            else:
                screenshot = driver.get_screenshot_as_png()
            
            return base64.b64encode(screenshot).decode('utf-8')
            
        except ImportError as e:
            return f"截图功能不可用: 请安装 selenium - {str(e)}"
        except Exception as e:
            self._init_driver()
            return f"截图失败: {str(e)}"

    def _wait_for_page_load(self, driver, timeout=10):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                ready_state = driver.execute_script("return document.readyState")
                if ready_state == "complete":
                    break
            except:
                pass
            time.sleep(0.3)
        time.sleep(0.5)

    def _capture_full_page(self, driver):
        try:
            from PIL import Image
            
            driver.execute_script("window.scrollTo({top: 0, left: 0, behavior: 'instant'});")
            time.sleep(0.3)
            
            total_height = driver.execute_script("""
                return Math.max(
                    document.documentElement.scrollHeight,
                    document.body.scrollHeight,
                    document.documentElement.offsetHeight,
                    document.body.offsetHeight
                );
            """)
            
            viewport_height = driver.execute_script("return window.innerHeight")
            viewport_width = driver.execute_script("return window.innerWidth")
            
            screenshots = []
            current_position = 0
            overlap = 30
            
            while current_position < total_height:
                driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(0.3)
                
                screenshot_part = driver.get_screenshot_as_png()
                screenshots.append(Image.open(BytesIO(screenshot_part)))
                
                current_position += viewport_height - overlap
                if current_position >= total_height:
                    break
            
            if screenshots:
                final_height = screenshots[0].height
                for i in range(1, len(screenshots)):
                    final_height += screenshots[i].height - overlap
                
                full_image = Image.new('RGB', (screenshots[0].width, final_height))
                y_offset = 0
                
                for i, img in enumerate(screenshots):
                    if i == 0:
                        full_image.paste(img, (0, y_offset))
                        y_offset += img.height
                    else:
                        crop_img = img.crop((0, overlap, img.width, img.height))
                        full_image.paste(crop_img, (0, y_offset))
                        y_offset += (img.height - overlap)
                
                output_buffer = BytesIO()
                full_image.save(output_buffer, format='PNG')
                output_buffer.seek(0)
                return output_buffer.getvalue()
            else:
                return driver.get_screenshot_as_png()
        except Exception:
            return driver.get_screenshot_as_png()

    async def _arun(
        self,
        url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(url, run_manager)


def is_likely_garbage(text):
    if not text or len(text) < 2:
        return True
    
    text = text.strip()
    
    if len(text) <= 1:
        return True
    
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_count = len(chinese_chars)
    chinese_ratio = chinese_count / len(text) if len(text) > 0 else 0
    letter_ratio = len(re.findall(r'[a-zA-Z]', text)) / len(text) if len(text) > 0 else 0
    digit_ratio = len(re.findall(r'\d', text)) / len(text) if len(text) > 0 else 0
    
    looks_like_time = bool(re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', text))
    looks_like_date = bool(re.search(r'\d{4}年\d{1,2}月\d{1,2}日', text))
    looks_like_url = bool(re.search(r'[a-zA-Z]+\.[a-zA-Z]{2,}', text))
    
    if looks_like_time or looks_like_date or looks_like_url:
        return False
    
    letter_groups = re.findall(r'[a-zA-Z]+', text)
    word_count = len(re.findall(r'[a-zA-Z]+|\d+|[\u4e00-\u9fff]+', text))
    
    common_garbage_tokens = [
        'al', 'ase', 'be', 'ee', 'e', 'ea', 'he', 'hy', 'ig', 'ne', 'oe', 're',
        'RM', 'SR', 'OR', 'AR', 'CN', 'KR', 'BR', 'FR', 'DE', 'JP', 'US', 'UK',
        'QW', 'QQ', 'QQz', 'ROLE', 'CCM', 'ROS', 'PMO', 'RE', 'HEA', 'RGR',
        'remap', 'be', 'se', 'te', 'ee', 'et', 're', 'ne', 'de', 'as', 'is', 'it',
        'lh', 'LE', 'ew', 'mn', 'we', 'Bm', 'oe', 'mn', 'SR', 'HB', 'KX', 'WR',
        'und', 'as', 'ae', 'ne', 'ape', 'ig', 'teats',
    ]
    
    tokens = re.split(r'[\s,.。，、]+', text)
    garbage_token_count = sum(1 for t in tokens if t in common_garbage_tokens)
    
    if chinese_ratio > 0.3:
        return False
    
    if chinese_count >= 3:
        return False
    
    if chinese_count == 2:
        if garbage_token_count >= 4:
            return True
        if garbage_token_count >= 3 and letter_ratio > 0.5:
            return True
        if len(text) >= 10 and letter_ratio < 0.6:
            return False
        if len(text) >= 8 and garbage_token_count <= 1:
            return False
        if len(text) >= 6 and letter_ratio < 0.5:
            return False
    
    if garbage_token_count >= 3:
        if chinese_count <= 2:
            return True
        if chinese_ratio < 0.3:
            return True
    
    if garbage_token_count >= 2 and len(text) <= 20:
        if chinese_count <= 1:
            return True
    
    if chinese_count == 1 and garbage_token_count >= 2:
        return True
    
    if chinese_count == 2 and garbage_token_count >= 3:
        return True
    
    if letter_ratio > 0.9 and len(text) <= 5:
        return True
    
    if letter_ratio > 0.8 and len(text) <= 4:
        return True
    
    short_letter_groups = [g for g in letter_groups if len(g) <= 3]
    if len(short_letter_groups) >= 3 and len(text) <= 20:
        if chinese_count <= 2:
            return True
    
    if letter_ratio > 0.7 and digit_ratio > 0.05 and len(text) <= 12:
        non_word_chars = re.findall(r'[^a-zA-Z0-9\u4e00-\u9fff\s]', text)
        if len(non_word_chars) <= 2 and chinese_count <= 1:
            return True
    
    if word_count >= 4 and all(len(w) <= 4 for w in letter_groups) and letter_ratio > 0.7:
        if chinese_count <= 2:
            return True
    
    garbage_patterns = [
        r'^[A-Za-z]{1,3}\s*$',
        r'^[A-Za-z]{1,2}[0-9]{1,2}\s*$',
        r'^[0-9]{1,2}[A-Za-z]{1,2}\s*$',
        r'^[A-Za-z]{2,4}\s+[A-Za-z]{2,4}\s*$',
        r'^[A-Za-z]{1,3}\s+[A-Za-z]{1,3}\s+[A-Za-z]{1,3}\s*$',
        r'^[A-Za-z]{1,4}\s+[A-Za-z]{1,4}\s+[A-Za-z]{1,4}\s+[A-Za-z]{1,4}\s*$',
        r'^[a-zA-Z]{1,3}\s+[\u4e00-\u9fff]{1}\s*$',
        r'^[\u4e00-\u9fff]{1}\s+[a-zA-Z]{1,3}\s*$',
        r'^\d{1,2}\s*[A-Za-z]{1,3}\s*$',
        r'^[A-Za-z]{1,3}\s*\d{1,2}\s*$',
    ]
    
    for pattern in garbage_patterns:
        if re.match(pattern, text):
            if chinese_count <= 1:
                return True
    
    if chinese_ratio > 0.25:
        return False
    
    if chinese_count >= 3:
        return False
    
    if chinese_count >= 2 and len(text) >= 6:
        return False
    
    if chinese_ratio == 0 and letter_ratio > 0.6 and len(text) <= 15:
        if digit_ratio > 0.15 and len(text) >= 6:
            return False
        return True
    
    if chinese_count == 0 and digit_ratio > 0.2 and len(text) <= 10:
        return True
    
    valid_tokens = [t for t in tokens if len(t) >= 3 or (len(t) >= 2 and t.isdigit())]
    if len(valid_tokens) >= 2 and chinese_count >= 1:
        return False
    
    if chinese_count >= 1 and len(text) >= 8:
        has_long_token = any(len(t) >= 3 and not t in common_garbage_tokens for t in tokens)
        if has_long_token:
            return False
    
    if chinese_ratio == 0 and letter_ratio > 0.5 and word_count >= 3 and all(len(w) <= 3 for w in letter_groups):
        return True
    
    return False


def filter_and_format_text(text):
    lines = text.split('\n')
    filtered_lines = []
    seen_lines = set()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if len(line) < 2:
            continue
        
        if is_likely_garbage(line):
            continue
        
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', line)
        has_chinese = len(chinese_chars) > 0
        
        has_numbers = bool(re.search(r'\d', line))
        looks_like_time = bool(re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', line))
        looks_like_date = bool(re.search(r'\d{4}年\d{1,2}月\d{1,2}日', line))
        
        if not has_chinese and not has_numbers and not looks_like_time and not looks_like_date and len(line) < 4:
            continue
        
        clean_line = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffefa-zA-Z0-9\s：:，。、；！？,.!?]', '', line)
        clean_line = re.sub(r'\s+', ' ', clean_line).strip()
        
        if len(clean_line) < 2:
            continue
        
        if clean_line not in seen_lines:
            filtered_lines.append(clean_line)
            seen_lines.add(clean_line)
    
    result = '\n'.join(filtered_lines)
    
    result = re.sub(r'(?<=[\u4e00-\u9fff])(?=[a-zA-Z])', ' ', result)
    result = re.sub(r'(?<=[a-zA-Z])(?=[\u4e00-\u9fff])', ' ', result)
    
    return result


def preprocess_image_version1(image):
    from PIL import Image, ImageEnhance, ImageFilter
    
    img = image.convert('RGB')
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    img = img.filter(ImageFilter.MedianFilter(size=1))
    
    return img


def preprocess_image_version2(image):
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np
    import cv2
    
    img = image.convert('RGB')
    open_cv_image = np.array(img)
    open_cv_image = open_cv_image[:, :, ::-1].copy()
    
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    img = Image.fromarray(thresh)
    
    return img


def preprocess_image_version3(image):
    from PIL import Image, ImageEnhance, ImageFilter
    
    img = image.convert('L')
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    img = img.filter(ImageFilter.SHARPEN)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    return img


def score_text(text):
    if not text or not text.strip():
        return 0.0
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    chinese_chars = sum(len(re.findall(r'[\u4e00-\u9fff]', line)) for line in lines)
    total_chars = sum(len(line) for line in lines)
    
    if total_chars == 0:
        return 0.0
    
    chinese_ratio = chinese_chars / total_chars
    
    valid_line_count = sum(1 for line in lines if len(line) >= 2 and not is_likely_garbage(line))
    line_score = valid_line_count / max(len(lines), 1)
    
    avg_line_length = sum(len(line) for line in lines) / max(len(lines), 1)
    length_score = min(avg_line_length / 10, 1.0)
    
    score = (chinese_ratio * 0.5) + (line_score * 0.3) + (length_score * 0.2)
    
    return score


class ScreenshotAnalyzerTool(BaseTool):
    name: str = "screenshot_analyzer"
    description: str = """分析截图内容，识别文字并进行分析。
输入: 截图的base64编码
输出: 分析结果，包含识别的文字和分析内容"""

    def _run(
        self,
        screenshot_base64: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:
            from PIL import Image
            import pytesseract
            
            image_data = base64.b64decode(screenshot_base64)
            original_image = Image.open(BytesIO(image_data))
            
            preprocessors = [
                ('v1', preprocess_image_version1),
                ('v2', preprocess_image_version2),
                ('v3', preprocess_image_version3),
            ]
            
            results = []
            
            for name, preprocessor in preprocessors:
                try:
                    processed_img = preprocessor(original_image)
                    
                    custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
                    
                    text = pytesseract.image_to_string(processed_img, lang='chi_sim+eng', config=custom_config)
                    
                    clean_text = filter_and_format_text(text)
                    
                    score = score_text(clean_text)
                    
                    results.append({
                        'name': name,
                        'text': clean_text,
                        'score': score
                    })
                except Exception as e:
                    continue
            
            if not results:
                return "截图中未识别到文字"
            
            results.sort(key=lambda x: x['score'], reverse=True)
            
            best_result = results[0]
            final_text = best_result['text']
            
            if not final_text.strip():
                return "截图中未识别到有效文字"
            
            lines = final_text.split('\n')
            formatted_lines = []
            for i, line in enumerate(lines, 1):
                formatted_lines.append(f"{i}. {line}")
            
            return "识别文字:\n" + "\n".join(formatted_lines)
            
        except ImportError as e:
            return f"分析功能不可用: 请安装 Pillow 和 pytesseract - {str(e)}"
        except Exception as e:
            return f"分析失败: {str(e)}"

    async def _arun(
        self,
        screenshot_base64: str,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._run(screenshot_base64, run_manager)
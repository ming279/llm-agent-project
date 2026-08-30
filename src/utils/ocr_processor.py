import os
from PIL import Image
import pytesseract

# 配置 Tesseract OCR 路径
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 设置 TESSDATA_PREFIX 环境变量
os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'

class OCRProcessor:
    def __init__(self):
        # 确保tesseract安装正确
        try:
            pytesseract.get_tesseract_version()
            print("Tesseract OCR initialized successfully!")
        except Exception as e:
            print(f"OCR initialization error: {e}")
            print("Please install Tesseract OCR: https://github.com/tesseract-ocr/tesseract")
    
    def extract_text(self, image_path):
        """从图片中提取文本"""
        try:
            image = Image.open(image_path)
            # 尝试使用Tesseract OCR
            try:
                # 先尝试英语
                text = pytesseract.image_to_string(image, lang='eng')
                if text.strip():
                    return text
                # 再尝试中英文混合
                text = pytesseract.image_to_string(image, lang='eng+chi_sim')
                return text
            except Exception as e:
                print(f"Tesseract OCR error: {e}")
                #  fallback: 返回图片信息
                return f"[OCR暂不可用] 图片大小: {image.size}, 模式: {image.mode}"
        except Exception as e:
            print(f"OCR error: {e}")
            return ""
    
    def extract_text_from_url(self, image_url, base_url=None):
        """从网络图片中提取文本"""
        try:
            import requests
            from io import BytesIO
            
            # 构建完整的图片URL
            if not image_url.startswith(('http://', 'https://')):
                if base_url:
                    image_url = base_url.rstrip('/') + '/' + image_url.lstrip('/')
                else:
                    return ""
            
            # 下载图片
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # 打开图片并进行OCR
            image = Image.open(BytesIO(response.content))
            # 尝试使用Tesseract OCR
            try:
                # 先尝试英语
                text = pytesseract.image_to_string(image, lang='eng')
                if text.strip():
                    return text
                # 再尝试中英文混合
                text = pytesseract.image_to_string(image, lang='eng+chi_sim')
                return text
            except Exception as e:
                print(f"Tesseract OCR error: {e}")
                #  fallback: 返回图片信息
                return f"[OCR暂不可用] 图片大小: {image.size}, 模式: {image.mode}"
        except Exception as e:
            print(f"OCR error from URL: {e}")
            return ""
    
    def is_available(self):
        """检查OCR是否可用"""
        try:
            pytesseract.get_tesseract_version()
            return True
        except:
            return False
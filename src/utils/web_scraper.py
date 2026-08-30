import requests
from bs4 import BeautifulSoup

class WebScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_content(self, url):
        """获取网页内容"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            # 自动检测编码并转换
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"Error fetching content: {e}")
            return None
    
    def get_soup(self, html):
        """解析HTML"""
        if html:
            return BeautifulSoup(html, 'html.parser')
        return None
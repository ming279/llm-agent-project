from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import re


class ExtractionAgent:
    def __init__(self):
        pass

    def extract_structured_data(self, html_content: str) -> Dict[str, Any]:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            title = self._extract_title(soup)
            main_content = self._extract_main_content(soup)
            key_points = self._extract_key_points(soup)
            links = self._extract_links(soup)
            
            return {
                'title': title,
                'main_content': main_content,
                'key_points': key_points,
                'links': links
            }
        
        except Exception as e:
            return {
                'title': '',
                'main_content': html_content[:500],
                'key_points': [],
                'links': [],
                'error': str(e)
            }

    def _extract_title(self, soup) -> str:
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        h1_tags = soup.find_all('h1')
        if h1_tags:
            return h1_tags[0].get_text(strip=True)
        
        return ''

    def _extract_main_content(self, soup) -> str:
        content = []
        
        for tag in soup.find_all(['p', 'article', 'div', 'section']):
            text = tag.get_text(strip=True)
            if text and len(text) > 20:
                content.append(text)
        
        return '\n'.join(content)[:2000]

    def _extract_key_points(self, soup) -> List[str]:
        points = []
        
        for tag in soup.find_all(['h2', 'h3', 'li', 'dt']):
            text = tag.get_text(strip=True)
            if text and len(text) > 5:
                points.append(text)
        
        return points[:10]

    def _extract_links(self, soup) -> List[str]:
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text(strip=True)
            if href and text:
                links.append(f"{text}: {href}")
        
        return links[:20]
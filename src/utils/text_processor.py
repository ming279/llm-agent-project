import re
from collections import Counter

def extract_keywords(text, top_n=10):
    """提取关键词"""
    # 移除标点符号，转为小写
    text = re.sub(r'[^\w\s]', '', text.lower())
    
    # 分词
    words = text.split()
    
    # 过滤停用词
    stop_words = set([
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did'
    ])
    
    # 过滤停用词和短词
    words = [word for word in words if word not in stop_words and len(word) > 2]
    
    # 统计词频
    word_counts = Counter(words)
    
    # 返回频率最高的n个词
    return [word for word, _ in word_counts.most_common(top_n)]

def clean_text(text):
    """清理文本"""
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    return text
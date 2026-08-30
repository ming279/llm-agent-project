from services.llm_service import LLMService


class KeywordAgent:
    def __init__(self):
        self.llm_service = LLMService()

    def extract_keywords(self, extracted_data):
        """提取关键词"""
        # 优先使用智能摘要，如果没有则使用原始文本
        summary = extracted_data.get('summary', '')
        if summary:
            text = f"{extracted_data.get('title', '')} {summary}"
        else:
            text = f"{extracted_data.get('title', '')} {' '.join(extracted_data.get('headings', []))} {' '.join(extracted_data.get('paragraphs', []))}"

        # 使用API生成更智能的关键词
        return self.llm_service.generate_keywords(text, use_api=True)

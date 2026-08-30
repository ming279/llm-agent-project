import os
from zhipuai import ZhipuAI
from utils.text_processor import extract_keywords


class LLMService:
    def __init__(self):
        # 初始化智谱AI客户端
        api_key = os.environ.get("ZHIPU_API_KEY")
        if api_key:
            self.client = ZhipuAI(api_key=api_key)
        else:
            self.client = None
            print("Warning: ZHIPU_API_KEY not set, using local keyword extraction only")

    def generate_keywords(self, text, use_api=True):
        """
        生成关键词
        :param text: 输入文本
        :param use_api: 是否使用API（默认True）
        :return: 关键词列表
        """
        if use_api and self.client:
            try:
                # 使用智谱AI API生成关键词
                response = self.client.chat.completions.create(
                    model="glm-4.7-Flash",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个关键词提取助手，从提供的文本中提取最相关的关键词，用逗号分隔。"
                        },
                        {
                            "role": "user",
                            "content": f"从以下文本中提取关键词：{text}"
                        }
                    ],
                    temperature=0.6
                )
                keywords_str = response.choices[0].message.content
                return [keyword.strip() for keyword in keywords_str.split(',') if keyword.strip()]
            except Exception as e:
                print(f"API error, falling back to local extraction: {e}")
                return extract_keywords(text)
        else:
            # 使用本地关键词提取
            return extract_keywords(text)

    def chat_completion(self, messages):
        """
        聊天完成
        :param messages: 消息列表
        :return: 响应文本
        """
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="glm-4.7-Flash",
                    messages=messages,
                    temperature=0.6
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Chat completion error: {e}")
                return "Error: Unable to generate response"
        else:
            return "Error: API not configured"


# 测试代码
if __name__ == "__main__":
    llm_service = LLMService()

    # 测试关键词提取
    test_text = "The quick brown fox jumps over the lazy dog. The fox is very quick and agile."
    keywords = llm_service.generate_keywords(test_text)
    print("Extracted keywords:", keywords)

    # 测试聊天完成
    test_messages = [
        {
            "role": "system",
            "content": "你是一个有用的AI助手。"
        },
        {
            "role": "user",
            "content": "你可以帮我分析图片吗"
        }
    ]
    response = llm_service.chat_completion(test_messages)
    print("Chat response:", response)

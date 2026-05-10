import os
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

if not DASHSCOPE_API_KEY:
    raise ValueError("DASHSCOPE_API_KEY environment variable is not set")

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'database': os.getenv('DB_NAME', 'llm_agent_db')
}

TARGET_WEBSITE = os.getenv('TARGET_WEBSITE', 'https://time.is/zh/China')
MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '60'))

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
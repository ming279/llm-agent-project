import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DB_CONFIG


class DatabaseAgent:
    def __init__(self):
        self.db_config = DB_CONFIG
        self._connection = None

    def connect(self):
        try:
            self._connection = mysql.connector.connect(**self.db_config)
            return self._connection
        except Error as e:
            print(f"数据库连接失败: {e}")
            return None

    def close(self):
        if self._connection and self._connection.is_connected():
            self._connection.close()

    def _ensure_connection(self):
        if not self._connection or not self._connection.is_connected():
            self._connection = self.connect()

    def get_or_create_website(self, url: str) -> Optional[int]:
        self._ensure_connection()
        if not self._connection:
            return None

        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "SELECT id FROM websites WHERE url = %s",
                (url,)
            )
            result = cursor.fetchone()

            if result:
                return result[0]

            cursor.execute(
                "INSERT INTO websites (url, created_at) VALUES (%s, %s)",
                (url, datetime.now())
            )
            self._connection.commit()
            return cursor.lastrowid

        except Error as e:
            print(f"数据库操作失败: {e}")
            return None
        finally:
            cursor.close()

    def store_data(
        self,
        website_id: int,
        title: str,
        content: str,
        keywords: List[str],
        change_type: str = "new"
    ) -> bool:
        self._ensure_connection()
        if not self._connection:
            return False

        cursor = self._connection.cursor()
        try:
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            cursor.execute(
                """INSERT INTO website_data
                (website_id, title, content, keywords, change_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (website_id, title, content, keywords_json, change_type, datetime.now())
            )
            self._connection.commit()
            return True

        except Error as e:
            print(f"存储数据失败: {e}")
            return False
        finally:
            cursor.close()

    def get_history(self, website_id: int, limit: int = 10) -> List[Dict]:
        self._ensure_connection()
        if not self._connection:
            return []

        cursor = self._connection.cursor(dictionary=True)
        try:
            cursor.execute(
                """SELECT * FROM website_data
                WHERE website_id = %s
                ORDER BY created_at DESC
                LIMIT %s""",
                (website_id, limit)
            )
            results = cursor.fetchall()

            for row in results:
                if row.get('keywords') and isinstance(row['keywords'], str):
                    row['keywords'] = json.loads(row['keywords'])

            return results

        except Error as e:
            print(f"查询历史失败: {e}")
            return []
        finally:
            cursor.close()

    def get_last_data(self, website_id: int) -> Optional[Dict]:
        history = self.get_history(website_id, limit=1)
        return history[0] if history else None

    def record_changes(self, website_id: int, old_data: Dict, new_data: Dict) -> bool:
        self._ensure_connection()
        if not self._connection:
            return False

        cursor = self._connection.cursor()
        try:
            old_title = old_data.get('title', '')
            new_title = new_data.get('title', '')
            old_text = str(old_data.get('paragraphs', []))[:500]
            new_text = str(new_data.get('paragraphs', []))[:500]

            cursor.execute(
                """INSERT INTO website_changes
                (website_id, old_title, new_title, old_content, new_content, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (website_id, old_title, new_title, old_text, new_text, datetime.now())
            )
            self._connection.commit()
            return True

        except Error as e:
            print(f"记录变化失败: {e}")
            return False
        finally:
            cursor.close()

    def update_last_checked(self, website_id: int) -> bool:
        self._ensure_connection()
        if not self._connection:
            return False

        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "UPDATE websites SET last_checked = %s WHERE id = %s",
                (datetime.now(), website_id)
            )
            self._connection.commit()
            return True

        except Error as e:
            print(f"更新检查时间失败: {e}")
            return False
        finally:
            cursor.close()
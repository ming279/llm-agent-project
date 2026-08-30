import mysql.connector
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DB_CONFIG


class Database:
    def __init__(self):
        self.config = DB_CONFIG.copy()
        # 添加 UTF-8 字符集配置
        self.config['charset'] = 'utf8mb4'

    def connect(self):
        """建立数据库连接"""
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    def get_or_create_website(self, url):
        """获取或创建网站记录"""
        conn = self.connect()
        if not conn:
            return None

        try:
            cursor = conn.cursor(dictionary=True)
            # 检查网站是否存在
            cursor.execute("SELECT id FROM websites WHERE url = %s", (url,))
            result = cursor.fetchone()

            if result:
                return result['id']
            else:
                # 创建新网站记录
                cursor.execute("INSERT INTO websites (url) VALUES (%s)", (url,))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error in get_or_create_website: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_last_website_data(self, website_id):
        """获取最后存储的网站数据"""
        conn = self.connect()
        if not conn:
            return None

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                           SELECT content, extracted_data, keywords
                           FROM website_data
                           WHERE website_id = %s
                           ORDER BY timestamp DESC
                               LIMIT 1
                           """, (website_id,))
            result = cursor.fetchone()
            # 解析关键词
            if result and result['keywords']:
                result['keywords'] = result['keywords'].split(',')
            # 解析提取的数据
            if result and result['extracted_data']:
                try:
                    result['extracted_data'] = json.loads(result['extracted_data'])
                except:
                    result['extracted_data'] = {}
            return result
        except Exception as e:
            print(f"Error in get_last_website_data: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def store_website_data(self, website_id, content, extracted_data, keywords):
        """存储网站数据"""
        conn = self.connect()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            
            # 只存储提取的数据摘要，不存储原始HTML（原始HTML太大）
            data_summary = {
                'title': extracted_data.get('title', ''),
                'headings': extracted_data.get('headings', [])[:10],  # 只保留前10个标题
                'first_paragraphs': extracted_data.get('paragraphs', [])[:5],  # 只保留前5段
                'links_count': len(extracted_data.get('links', [])),
                'images_count': len(extracted_data.get('images', []))
            }
            
            # 插入新数据（不存储原始HTML内容）
            cursor.execute("""
                           INSERT INTO website_data (website_id, content, extracted_data, keywords)
                           VALUES (%s, %s, %s, %s)
                           """,
                           (website_id, 
                            f"[已提取摘要] {data_summary['title']}",  # 只存储标题作为content
                            json.dumps(data_summary, ensure_ascii=False), 
                            ','.join(keywords[:20])))

            # 更新网站最后更新时间
            cursor.execute("""
                           UPDATE websites
                           SET last_changed = CURRENT_TIMESTAMP
                           WHERE id = %s
                           """, (website_id,))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error in store_website_data: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def record_changes(self, website_id, old_data, new_data):
        """记录数据变化"""
        conn = self.connect()
        if not conn:
            return False

        try:
            # 分析变化
            changes = self._analyze_changes(old_data, new_data)
            
            # 如果没有变化，不记录
            if not changes:
                return True
            
            cursor = conn.cursor()
            # 限制数据大小
            changes_str = json.dumps(changes, ensure_ascii=False)[:30000]
            
            cursor.execute("""
                           INSERT INTO changes (website_id, old_data, new_data, change_type)
                           VALUES (%s, %s, %s, %s)
                           """, (website_id, 
                                  json.dumps({'summary': 'Previous data'}, ensure_ascii=False), 
                                  changes_str, 
                                  'content_update'))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error in record_changes: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def _analyze_changes(self, old_data, new_data):
        """分析数据变化"""
        changes = {}
        
        # 检查标题变化
        if isinstance(old_data, dict) and isinstance(new_data, dict):
            old_title = old_data.get('title', '')
            new_title = new_data.get('title', '')
            if old_title != new_title:
                changes['title'] = {
                    'old': old_title,
                    'new': new_title
                }
            
            # 检查标题列表变化
            old_headings = old_data.get('headings', [])[:5]  # 只比较前5个标题
            new_headings = new_data.get('headings', [])[:5]
            if old_headings != new_headings:
                changes['headings'] = {
                    'old': old_headings,
                    'new': new_headings
                }
            
            # 检查段落变化
            old_paragraphs = old_data.get('first_paragraphs', [])[:3]  # 只比较前3段
            new_paragraphs = new_data.get('paragraphs', [])[:3]  # 新数据中是paragraphs
            if old_paragraphs != new_paragraphs:
                changes['paragraphs'] = {
                    'old': old_paragraphs,
                    'new': new_paragraphs
                }
            
            # 检查链接和图片数量变化
            old_links_count = old_data.get('links_count', 0)
            new_links_count = len(new_data.get('links', []))  # 新数据中是links列表
            if old_links_count != new_links_count:
                changes['links_count'] = {
                    'old': old_links_count,
                    'new': new_links_count
                }
            
            old_images_count = old_data.get('images_count', 0)
            new_images_count = len(new_data.get('images', []))  # 新数据中是images列表
            if old_images_count != new_images_count:
                changes['images_count'] = {
                    'old': old_images_count,
                    'new': new_images_count
                }
        
        return changes

    def update_last_checked(self, website_id):
        """更新最后检查时间"""
        conn = self.connect()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                           UPDATE websites
                           SET last_checked = CURRENT_TIMESTAMP
                           WHERE id = %s
                           """, (website_id,))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error in update_last_checked: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_all_websites(self):
        """获取所有监控的网站"""
        conn = self.connect()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM websites ORDER BY last_checked DESC")
            return cursor.fetchall()
        except Exception as e:
            print(f"Error in get_all_websites: {e}")
            return []
        finally:
            if conn:
                conn.close()
                
    def get_changes(self, website_id, limit=10):
        """获取网站的变化记录"""
        conn = self.connect()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                           SELECT * FROM changes
                           WHERE website_id = %s
                           ORDER BY timestamp DESC
                           LIMIT %s
                           """, (website_id, limit))
            return cursor.fetchall()
        except Exception as e:
            print(f"Error in get_changes: {e}")
            return []
        finally:
            if conn:
                conn.close()
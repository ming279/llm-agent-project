import os
import sys
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.models.database import Database

def safe_str(text, max_len=100):
    """安全字符串处理，避免编码错误"""
    if not text:
        return ""
    # 移除不可打印的字符
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text

def view_database():
    """查看数据库中的数据"""
    print("=" * 80)
    print("数据库查看器")
    print("=" * 80)
    print()
    
    db = Database()
    
    # 查看网站列表
    print("【监控的网站列表】")
    websites = db.get_all_websites()
    if websites:
        for i, website in enumerate(websites, 1):
            print(f"{i}. {website['url']}")
            print(f"   最后检查: {website.get('last_checked', 'N/A')}")
    else:
        print("  暂无监控网站")
    print()
    
    # 查看最新数据
    if websites:
        print("【最新数据】")
        latest_data = db.get_last_website_data(websites[0]['id'])
        if latest_data:
            print(f"标题: {safe_str(latest_data['extracted_data'].get('title', 'N/A'))}")
            print(f"关键词: {safe_str(', '.join(latest_data['keywords'][:10]))}")
            print(f"链接数量: {latest_data['extracted_data'].get('links_count', 0)}")
            print(f"图片数量: {latest_data['extracted_data'].get('images_count', 0)}")
            if latest_data['extracted_data'].get('first_paragraphs'):
                first_para = latest_data['extracted_data']['first_paragraphs'][0]
                print(f"首段内容: {safe_str(first_para, 80)}")
        else:
            print("  暂无数据")
    
    # 查看变化记录
    if websites:
        print("\n【最近10条变化记录】")
        changes = db.get_changes(websites[0]['id'])
        if changes:
            print(f"共找到 {len(changes)} 条变化记录\n")
            for i, change in enumerate(changes, 1):
                print(f"{'='*80}")
                print(f"变化 {i} | 时间: {change['timestamp']}")
                print(f"{'='*80}")
                
                # 显示变化详情
                try:
                    changes_data = json.loads(change['new_data'])
                    if changes_data:
                        for key, value in changes_data.items():
                            if key == 'title':
                                print(f"  [标题变化]")
                                print(f"    旧: {safe_str(value['old'])}")
                                print(f"    新: {safe_str(value['new'])}")
                            elif key == 'headings':
                                print(f"  [标题列表变化]")
                                if value.get('old'):
                                    print(f"    旧前3个: {safe_str(', '.join(value['old'][:3]))}")
                                if value.get('new'):
                                    print(f"    新前3个: {safe_str(', '.join(value['new'][:3]))}")
                            elif key == 'paragraphs':
                                print(f"  [段落内容变化]")
                                if value.get('old') and len(value['old']) > 0:
                                    print(f"    旧首段: {safe_str(value['old'][0], 80)}")
                                if value.get('new') and len(value['new']) > 0:
                                    print(f"    新首段: {safe_str(value['new'][0], 80)}")
                            elif key == 'links_count':
                                print(f"  [链接数量变化]")
                                print(f"    旧: {value['old']} 个")
                                print(f"    新: {value['new']} 个")
                            elif key == 'images_count':
                                print(f"  [图片数量变化]")
                                print(f"    旧: {value['old']} 张")
                                print(f"    新: {value['new']} 张")
                        print()
                    else:
                        print("  无明显变化内容")
                        print()
                except Exception as e:
                    print(f"  变化详情解析失败: {e}")
                    print()
        else:
            print("  暂无变化记录")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    view_database()
import streamlit as st
import time
import sys
import os
import hashlib
import json
from datetime import datetime
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_WEBSITE, MONITOR_INTERVAL
from agents.supervisor_agent import (
    SupervisorAgent,
    WatcherAgent,
    ExtractionAgent,
    AnalyzerAgent,
    OCRProcessor,
)
from agents.database_agent import DatabaseAgent
from tools.web_tools import WebScraperTool
from tools.screenshot_tools import ScreenshotTool, ScreenshotAnalyzerTool


def init_agents():
    if 'supervisor' not in st.session_state:
        st.session_state.supervisor = SupervisorAgent()
    if 'watcher' not in st.session_state:
        st.session_state.watcher = WatcherAgent()
    if 'extractor' not in st.session_state:
        st.session_state.extractor = ExtractionAgent()
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = AnalyzerAgent()
    if 'ocr' not in st.session_state:
        st.session_state.ocr = OCRProcessor()
    if 'db' not in st.session_state:
        st.session_state.db = DatabaseAgent()
    if 'screenshot_tool' not in st.session_state:
        st.session_state.screenshot_tool = ScreenshotTool()
    if 'screenshot_analyzer' not in st.session_state:
        st.session_state.screenshot_analyzer = ScreenshotAnalyzerTool()
    if 'last_hash' not in st.session_state:
        st.session_state.last_hash = None
    if 'last_content' not in st.session_state:
        st.session_state.last_content = None
    if 'records' not in st.session_state:
        st.session_state.records = []
    if 'last_check_time' not in st.session_state:
        st.session_state.last_check_time = None
    if 'history_records' not in st.session_state:
        st.session_state.history_records = {}
    if 'use_screenshot' not in st.session_state:
        st.session_state.use_screenshot = False
    if 'full_page_screenshot' not in st.session_state:
        st.session_state.full_page_screenshot = False
    if 'last_image_hash' not in st.session_state:
        st.session_state.last_image_hash = None


def check_website_change():
    if not st.session_state.monitoring or st.session_state.paused:
        return

    start_time = time.time()
    timings = {}
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    st.session_state.last_check_time = current_time
    
    st.session_state.last_check_duration = 0

    try:
        content = ""
        images = []
        screenshot_base64 = None
        screenshot_analysis = ""

        if st.session_state.use_screenshot:
            screenshot_start = time.time()
            screenshot_result = st.session_state.screenshot_tool._run(
                st.session_state.target_url,
                full_page=st.session_state.full_page_screenshot
            )
            timings['screenshot'] = time.time() - screenshot_start
            
            if screenshot_result.startswith("截图失败") or screenshot_result.startswith("截图功能不可用"):
                st.session_state.status = f"截图失败: {screenshot_result}"
                return
            else:
                screenshot_base64 = screenshot_result
                ocr_start = time.time()
                screenshot_analysis = st.session_state.screenshot_analyzer._run(screenshot_base64)
                timings['ocr'] = time.time() - ocr_start
                content = screenshot_analysis.replace("识别文字:\n", "")
                images = []
        else:
            scraper = WebScraperTool()
            result_str = scraper._run(st.session_state.target_url)
            result = json.loads(result_str)
            content = result.get('text', '')
            images = result.get('images', [])

        if not content or content.startswith("抓取失败"):
            st.session_state.status = f"获取网页内容失败: {content}"
            return

        current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        current_image_hash = None
        if screenshot_base64:
            current_image_hash = hashlib.md5(base64.b64decode(screenshot_base64)).hexdigest()

        is_first_check = st.session_state.last_hash is None
        
        if is_first_check:
            st.session_state.status = "首次检测完成"
            st.session_state.last_change = "first"
        else:
            content_changed = current_hash != st.session_state.last_hash
            image_changed = False
            if st.session_state.use_screenshot and current_image_hash and st.session_state.last_image_hash:
                image_changed = current_image_hash != st.session_state.last_image_hash
            
            if content_changed or image_changed:
                st.session_state.status = "检测到网站变化！"
                st.session_state.last_change = "changed"
                if image_changed and not content_changed:
                    st.session_state.status += " (图片变化)"
            else:
                st.session_state.status = "网站内容无变化"
                st.session_state.last_change = "none"
                st.session_state.last_check_duration = time.time() - start_time
                return

        llm_start = time.time()
        cache_key = f"extraction_{current_hash}"
        if cache_key in st.session_state:
            extracted_data = st.session_state[cache_key]
        else:
            extracted_data = st.session_state.extractor.extract_structured_data(content)
            st.session_state[cache_key] = extracted_data
        timings['llm_extract'] = time.time() - llm_start

        old_data = None
        change_analysis = None
        
        if st.session_state.last_content:
            old_hash = hashlib.md5(st.session_state.last_content.encode('utf-8')).hexdigest()
            old_cache_key = f"extraction_{old_hash}"
            if old_cache_key in st.session_state:
                old_data = st.session_state[old_cache_key]
            else:
                old_data = st.session_state.extractor.extract_structured_data(st.session_state.last_content)
                st.session_state[old_cache_key] = old_data

            if old_data:
                analysis_key = f"analysis_{old_hash}_{current_hash}"
                if analysis_key in st.session_state:
                    change_analysis = st.session_state[analysis_key]
                else:
                    change_analysis = st.session_state.analyzer.analyze_change(
                        st.session_state.last_content or "",
                        content
                    )
                    st.session_state[analysis_key] = change_analysis

        keyword_key = f"keywords_{current_hash}"
        if keyword_key in st.session_state:
            keywords = st.session_state[keyword_key]
        else:
            keywords = st.session_state.supervisor._generate_keywords(content)
            st.session_state[keyword_key] = keywords

        ocr_results = []
        if st.session_state.use_screenshot and screenshot_analysis:
            ocr_results = [{"index": "截图", "text": screenshot_analysis}]
        elif images and len(images) > 0:
            try:
                ocr_results = st.session_state.ocr.recognize_batch(images[:3])
            except Exception as ocr_e:
                ocr_results = [{"index": "错误", "text": f"OCR识别失败: {str(ocr_e)}"}]

        db_start = time.time()
        website_id = st.session_state.db.get_or_create_website(st.session_state.target_url)
        if website_id:
            st.session_state.db.store_data(
                website_id=website_id,
                title=extracted_data.get("title", ""),
                content=json.dumps(extracted_data, ensure_ascii=False),
                keywords=keywords,
                change_type="new" if is_first_check else "updated"
            )
            if old_data:
                st.session_state.db.record_changes(website_id, old_data, extracted_data)
            st.session_state.db.update_last_checked(website_id)
        timings['database'] = time.time() - db_start

        record = {
            'time': current_time,
            'title': extracted_data.get('title', '无标题'),
            'main_content': extracted_data.get('main_content', ''),
            'key_points': extracted_data.get('key_points', []),
            'keywords': keywords,
            'change_analysis': change_analysis.get('analysis', '') if change_analysis else '',
            'status': 'changed',
            'images_count': len(images),
            'images': images[:5],
            'ocr_results': ocr_results,
            'is_first': is_first_check,
            'screenshot_base64': screenshot_base64,
            'has_screenshot': screenshot_base64 is not None and len(screenshot_base64) > 0,
            'timings': timings
        }
        st.session_state.records.insert(0, record)
        if len(st.session_state.records) > 10:
            st.session_state.records.pop()

        url = st.session_state.target_url
        if url not in st.session_state.history_records:
            st.session_state.history_records[url] = []
        
        existing_times = {rec['time'] for rec in st.session_state.history_records[url]}
        if record['time'] not in existing_times:
            st.session_state.history_records[url].insert(0, record)
            if len(st.session_state.history_records[url]) > 50:
                st.session_state.history_records[url].pop()

        st.session_state.last_hash = current_hash
        st.session_state.last_content = content
        if current_image_hash:
            st.session_state.last_image_hash = current_image_hash
        
        st.session_state.last_check_duration = time.time() - start_time
        
        if timings:
            timing_str = " | ".join([f"{k}: {v:.2f}s" for k, v in timings.items()])
            st.session_state.status += f" ({timing_str})"

    except Exception as e:
        st.session_state.status = f"监控错误: {str(e)}"


def main():
    st.set_page_config(
        page_title="LLM Agent 网站监控系统",
        page_icon="🔍",
        layout="wide"
    )

    st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    .btn-primary {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        padding: 8px 24px;
        font-weight: 500;
    }
    .btn-secondary {
        background-color: #e2e8f0;
        color: #475569;
        border-radius: 8px;
        padding: 8px 24px;
        font-weight: 500;
    }
    .status-success { color: #22c55e; }
    .status-warning { color: #f59e0b; }
    .status-error { color: #ef4444; }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #1e293b !important;
    }
    .stRadio label {
        color: #334155 !important;
    }
    .stSelectbox label {
        color: #334155 !important;
    }
    .stExpanderHeader {
        color: #1e293b !important;
        font-weight: 600 !important;
    }
    .status-info { color: #3b82f6; }
    </style>
    """, unsafe_allow_html=True)

    init_agents()

    if 'target_url' not in st.session_state:
        st.session_state.target_url = TARGET_WEBSITE
    if 'monitor_interval' not in st.session_state:
        st.session_state.monitor_interval = MONITOR_INTERVAL
    if 'monitoring' not in st.session_state:
        st.session_state.monitoring = False
    if 'paused' not in st.session_state:
        st.session_state.paused = False
    if 'status' not in st.session_state:
        st.session_state.status = "等待开始监控"
    if 'last_change' not in st.session_state:
        st.session_state.last_change = ""
    if 'remaining_time' not in st.session_state:
        st.session_state.remaining_time = 0

    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.markdown("## 🔍 LLM Agent 网站监控系统")
    with col_time:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        st.markdown(f"<p style='text-align: right; color: #64748b;'>{current_time}</p>", unsafe_allow_html=True)

    st.markdown("---")

    col1, col2, col3 = st.columns([2, 2, 1.5])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ⚙️ 监控配置")
        st.session_state.target_url = st.text_input(
            "网站URL", 
            st.session_state.target_url,
            placeholder="请输入要监控的网站URL",
            label_visibility="collapsed"
        )
        
        screenshot_enabled = st.toggle(
            "📷 使用截图模式",
            value=st.session_state.use_screenshot,
            key="screenshot_toggle"
        )
        st.session_state.use_screenshot = screenshot_enabled
        
        if screenshot_enabled:
            st.markdown("<p style='color: #f59e0b; font-size: 14px;'>⚠️ 截图模式需要安装 Microsoft Edge 浏览器</p>", unsafe_allow_html=True)
            
            full_page_enabled = st.toggle(
                "📄 长截图模式",
                value=st.session_state.full_page_screenshot,
                key="full_page_toggle"
            )
            st.session_state.full_page_screenshot = full_page_enabled
            
            if full_page_enabled:
                st.markdown("<p style='color: #3b82f6; font-size: 14px;'>📝 长截图模式会截取整个网页内容，耗时较长</p>", unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ⏱️ 检查间隔")
        st.session_state.monitor_interval = st.slider(
            "interval_slider", 
            1, 60,
            st.session_state.monitor_interval,
            label_visibility="hidden"
        )
        st.markdown(f"<p style='color: #64748b;'>{st.session_state.monitor_interval} 秒</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📊 数据库状态")
        try:
            conn = st.session_state.db.connect()
            if conn:
                conn.close()
                st.markdown("<p class='status-success'>✅ 数据库连接正常</p>", unsafe_allow_html=True)
            else:
                st.markdown("<p class='status-warning'>⚠️ 不可用</p>", unsafe_allow_html=True)
        except:
            st.markdown("<p class='status-error'>❌ 连接失败</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("")

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 2])
    
    with col_btn1:
        if not st.session_state.monitoring:
            if st.button("▶️ 开始监控", use_container_width=True):
                st.session_state.monitoring = True
                st.session_state.paused = False
                st.rerun()
        else:
            st.button("▶️ 开始监控", disabled=True, use_container_width=True)

    with col_btn2:
        if st.session_state.monitoring:
            btn_text = "⏸️ 暂停检测" if not st.session_state.paused else "▶️ 继续检测"
            if st.button(btn_text, use_container_width=True):
                st.session_state.paused = not st.session_state.paused
                st.rerun()
        else:
            st.button("⏸️ 暂停检测", disabled=True, use_container_width=True)

    with col_btn3:
        if st.session_state.monitoring:
            if st.button("⏹️ 停止监控", use_container_width=True):
                st.session_state.monitoring = False
                st.session_state.paused = False
                st.session_state.last_hash = None
                st.session_state.last_content = None
                st.session_state.last_image_hash = None
                st.session_state.status = "等待开始监控"
                st.session_state.last_change = ""
                st.session_state.records = []
                st.rerun()
        else:
            st.button("⏹️ 停止监控", disabled=True, use_container_width=True)

    st.markdown("---")

    if st.session_state.monitoring and not st.session_state.paused:
        with st.spinner("正在检测网站变化..."):
            check_website_change()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("###  网站变化状态")
    
    if st.session_state.monitoring:
        if st.session_state.last_change == "first":
            st.markdown("<p class='status-info' style='text-align: center; padding: 10px; background-color: #eff6ff; border-radius: 8px;'>🆕 首次检测</p>", unsafe_allow_html=True)
        elif st.session_state.last_change == "changed":
            st.markdown("<p class='status-error' style='text-align: center; padding: 10px; background-color: #fef2f2; border-radius: 8px;'>🔴 发生变化</p>", unsafe_allow_html=True)
        elif st.session_state.last_change == "none":
            st.markdown("<p class='status-success' style='text-align: center; padding: 10px; background-color: #f0fdf4; border-radius: 8px;'>✅ 未发生变化</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p class='status-info' style='text-align: center; padding: 10px; background-color: #eff6ff; border-radius: 8px;'>🔄 监控中...</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p class='status-warning' style='text-align: center; padding: 10px; background-color: #fffbeb; border-radius: 8px;'>⏳ 监控未启动</p>", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📋 监控状态")
    
    if st.session_state.monitoring:
        status_text = st.session_state.status
        if st.session_state.paused:
            status_text = "监控已暂停"
        
        st.markdown(f"<p style='color: #334155;'>{status_text}</p>", unsafe_allow_html=True)
        
        if not st.session_state.paused:
            st.markdown(f"<p style='color: #64748b;'>还有 {st.session_state.monitor_interval} 秒进行下一次检测</p>", unsafe_allow_html=True)
        
        if st.session_state.last_check_time:
            st.markdown(f"<p style='color: #94a3b8;'>{st.session_state.last_check_time} - 检测完成，网站状态正常</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p style='color: #94a3b8;'>等待开始监控...</p>", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.records:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 最新检测结果")
        
        for rec in st.session_state.records[:5]:
            with st.expander(f"{rec['time']} - {rec['title'][:50]}..."):
                st.markdown(f"**标题:** {rec['title']}")
                st.markdown(f"**内容摘要:** {rec['main_content'][:200]}...")
                st.markdown(f"**关键词:** {', '.join(rec['keywords'][:5])}")
                if rec.get('images_count'):
                    st.markdown(f"**图片数量:** {rec['images_count']}")
                
                if rec.get('screenshot_base64') or rec.get('has_screenshot'):
                    st.markdown("**截图预览:**")
                    try:
                        from PIL import Image
                        from io import BytesIO
                        
                        image_data = base64.b64decode(rec['screenshot_base64'])
                        img = Image.open(BytesIO(image_data))
                        
                        # 如果图片太大，进行压缩
                        max_width = 1200
                        if img.width > max_width:
                            ratio = max_width / img.width
                            new_height = int(img.height * ratio)
                            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                        
                        # 转换为RGB格式
                        if img.mode in ('RGBA', 'LA'):
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[1])
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # 重新编码
                        output_buffer = BytesIO()
                        img.save(output_buffer, format='JPEG', quality=85, optimize=True)
                        output_buffer.seek(0)
                        
                        st.image(output_buffer.getvalue(), caption=f"网站截图 - {rec['time']}", width=600, use_container_width=True)
                    except Exception as e:
                        st.markdown(f"图片显示失败: {str(e)}")
                        if rec.get('has_screenshot'):
                            st.markdown(f"*截图已保存，文件大小: 约 {len(rec.get('screenshot_base64', '')) // 1024} KB*")
                
                if rec.get('images') and len(rec['images']) > 0:
                    st.markdown("**网页图片:**")
                    st.markdown(f"*找到 {len(rec['images'])} 张图片*")
                    valid_images = [img for img in rec['images'] if img and not img.lower().endswith('.svg')]
                    if not valid_images:
                        st.markdown("*⚠️ 所有图片都是SVG格式，暂不支持显示*")
                    else:
                        cols = st.columns(3)
                        for i, img_url in enumerate(valid_images[:6]):
                            with cols[i % 3]:
                                try:
                                    st.markdown(f"🖼️ 图片 {i+1}")
                                    st.image(img_url, caption=f"图片 {i+1}", width=200)
                                except Exception as e:
                                    st.markdown(f"❌ 图片 {i+1} 加载失败")
                
                if rec.get('ocr_results') and len(rec['ocr_results']) > 0:
                    st.markdown("**OCR识别结果:**")
                    for ocr_result in rec['ocr_results']:
                        if isinstance(ocr_result, dict):
                            idx = ocr_result.get('index', '未知')
                            text = ocr_result.get('text', '')
                            if text and not text.startswith("截图中未识别"):
                                lines = text.replace("识别文字:\n", "").split('\n')
                                for line in lines[:20]:
                                    if line.strip():
                                        st.markdown(f"- {line.strip()}")
                            else:
                                st.markdown(f"- {text if text else '未识别到文字'}")
                        else:
                            text = str(ocr_result)
                            if text and not text.startswith("截图中未识别"):
                                lines = text.replace("识别文字:\n", "").split('\n')
                                for line in lines[:20]:
                                    if line.strip():
                                        st.markdown(f"- {line.strip()}")
                            else:
                                st.markdown(f"- {text}")
                
                if rec.get('change_analysis'):
                    st.markdown(f"**变化分析:** {rec['change_analysis'][:200]}")
                if rec.get('is_first'):
                    st.markdown("**首次检测记录**")
        
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.history_records and len(st.session_state.history_records) > 0:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📚 历史记录")
        
        col_clear, col_view = st.columns([1, 3])
        with col_clear:
            if st.button("🗑️ 清空历史记录", type="secondary", use_container_width=True):
                st.session_state.history_records = {}
                st.rerun()
        with col_view:
            view_mode = st.radio(
                "查看模式",
                ["按网站分类", "全部记录时间线"],
                key="history_view_mode",
                horizontal=True
            )
        
        if view_mode == "按网站分类":
            selected_url = st.selectbox(
                "选择网站",
                options=list(st.session_state.history_records.keys()),
                key="history_url_select"
            )
            
            if selected_url:
                history_list = st.session_state.history_records.get(selected_url, [])
                st.markdown(f"**记录数量:** {len(history_list)}")
                
                for rec in history_list[:10]:
                    with st.expander(f"{rec['time']} - {rec['title'][:50]}..."):
                        st.markdown(f"**标题:** {rec['title']}")
                        st.markdown(f"**内容摘要:** {rec['main_content'][:200]}...")
                        st.markdown(f"**关键词:** {', '.join(rec['keywords'][:5])}")
                        if rec.get('images_count'):
                            st.markdown(f"**图片数量:** {rec['images_count']}")
                        
                        if rec.get('screenshot_base64') or rec.get('has_screenshot'):
                            st.markdown("**截图预览:**")
                            try:
                                from PIL import Image
                                from io import BytesIO
                                
                                image_data = base64.b64decode(rec['screenshot_base64'])
                                img = Image.open(BytesIO(image_data))
                                
                                max_width = 1200
                                if img.width > max_width:
                                    ratio = max_width / img.width
                                    new_height = int(img.height * ratio)
                                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                                
                                if img.mode in ('RGBA', 'LA'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[1])
                                    img = background
                                elif img.mode != 'RGB':
                                    img = img.convert('RGB')
                                
                                output_buffer = BytesIO()
                                img.save(output_buffer, format='JPEG', quality=85, optimize=True)
                                output_buffer.seek(0)
                                
                                st.image(output_buffer.getvalue(), caption=f"网站截图 - {rec['time']}", width=600, use_container_width=True)
                            except Exception as e:
                                st.markdown(f"图片显示失败: {str(e)}")
                                if rec.get('has_screenshot'):
                                    st.markdown(f"*截图已保存，文件大小: 约 {len(rec.get('screenshot_base64', '')) // 1024} KB*")
                        
                        if rec.get('images') and len(rec['images']) > 0:
                            st.markdown("**网页图片:**")
                            st.markdown(f"*找到 {len(rec['images'])} 张图片*")
                            valid_images = [img for img in rec['images'] if img and not img.lower().endswith('.svg')]
                            if not valid_images:
                                st.markdown("*⚠️ 所有图片都是SVG格式，暂不支持显示*")
                            else:
                                cols = st.columns(3)
                                for i, img_url in enumerate(valid_images[:6]):
                                    with cols[i % 3]:
                                        try:
                                            st.markdown(f"🖼️ 图片 {i+1}")
                                            st.image(img_url, caption=f"图片 {i+1}", width=200)
                                        except Exception as e:
                                            st.markdown(f"❌ 图片 {i+1} 加载失败")
                        
                        if rec.get('ocr_results') and len(rec['ocr_results']) > 0:
                            st.markdown("**OCR识别结果:**")
                            for ocr_result in rec['ocr_results']:
                                if isinstance(ocr_result, dict):
                                    idx = ocr_result.get('index', '未知')
                                    text = ocr_result.get('text', '')
                                    if text and not text.startswith("截图中未识别"):
                                        lines = text.replace("识别文字:\n", "").split('\n')
                                        for line in lines[:20]:
                                            if line.strip():
                                                st.markdown(f"- {line.strip()}")
                                    else:
                                        st.markdown(f"- {text if text else '未识别到文字'}")
                                else:
                                    text = str(ocr_result)
                                    if text and not text.startswith("截图中未识别"):
                                        lines = text.replace("识别文字:\n", "").split('\n')
                                        for line in lines[:20]:
                                            if line.strip():
                                                st.markdown(f"- {line.strip()}")
                                    else:
                                        st.markdown(f"- {text}")
                        
                        if rec.get('change_analysis'):
                            st.markdown(f"**变化分析:** {rec['change_analysis'][:200]}")
                        if rec.get('is_first'):
                            st.markdown("**首次检测记录**")
        else:
            all_history_records = []
            for url, records in st.session_state.history_records.items():
                for rec in records:
                    rec['website'] = url
                    all_history_records.append(rec)
            all_history_records.sort(key=lambda x: x['time'], reverse=True)
            
            st.markdown(f"**记录数量:** {len(all_history_records)}")
            
            for rec in all_history_records[:10]:
                with st.expander(f"{rec['time']} - {rec['title'][:50]}..."):
                    st.markdown(f"**标题:** {rec['title']}")
                    st.markdown(f"**内容摘要:** {rec['main_content'][:200]}...")
                    st.markdown(f"**关键词:** {', '.join(rec['keywords'][:5])}")
                    if rec.get('images_count'):
                        st.markdown(f"**图片数量:** {rec['images_count']}")
                    
                    if rec.get('screenshot_base64') or rec.get('has_screenshot'):
                        st.markdown("**截图预览:**")
                        try:
                            from PIL import Image
                            from io import BytesIO
                            
                            image_data = base64.b64decode(rec['screenshot_base64'])
                            img = Image.open(BytesIO(image_data))
                            
                            max_width = 1200
                            if img.width > max_width:
                                ratio = max_width / img.width
                                new_height = int(img.height * ratio)
                                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                            
                            if img.mode in ('RGBA', 'LA'):
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[1])
                                img = background
                            elif img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            output_buffer = BytesIO()
                            img.save(output_buffer, format='JPEG', quality=85, optimize=True)
                            output_buffer.seek(0)
                            
                            st.image(output_buffer.getvalue(), caption=f"网站截图 - {rec['time']}", width=600, use_container_width=True)
                        except Exception as e:
                            st.markdown(f"图片显示失败: {str(e)}")
                            if rec.get('has_screenshot'):
                                st.markdown(f"*截图已保存，文件大小: 约 {len(rec.get('screenshot_base64', '')) // 1024} KB*")
                    
                    if rec.get('images') and len(rec['images']) > 0:
                        st.markdown("**网页图片:**")
                        st.markdown(f"*找到 {len(rec['images'])} 张图片*")
                        valid_images = [img for img in rec['images'] if img and not img.lower().endswith('.svg')]
                        if not valid_images:
                            st.markdown("*⚠️ 所有图片都是SVG格式，暂不支持显示*")
                        else:
                            cols = st.columns(3)
                            for i, img_url in enumerate(valid_images[:6]):
                                    with cols[i % 3]:
                                        try:
                                            st.markdown(f"🖼️ 图片 {i+1}")
                                            st.image(img_url, caption=f"图片 {i+1}", width=200)
                                        except Exception as e:
                                            st.markdown(f"❌ 图片 {i+1} 加载失败")
                    
                    if rec.get('ocr_results') and len(rec['ocr_results']) > 0:
                        st.markdown("**OCR识别结果:**")
                        for ocr_result in rec['ocr_results']:
                            if isinstance(ocr_result, dict):
                                idx = ocr_result.get('index', '未知')
                                text = ocr_result.get('text', '')
                                if text and not text.startswith("截图中未识别"):
                                    lines = text.replace("识别文字:\n", "").split('\n')
                                    for line in lines[:20]:
                                        if line.strip():
                                            st.markdown(f"- {line.strip()}")
                                else:
                                    st.markdown(f"- {text if text else '未识别到文字'}")
                            else:
                                text = str(ocr_result)
                                if text and not text.startswith("截图中未识别"):
                                    lines = text.replace("识别文字:\n", "").split('\n')
                                    for line in lines[:20]:
                                        if line.strip():
                                            st.markdown(f"- {line.strip()}")
                                else:
                                    st.markdown(f"- {text}")
                    
                    if rec.get('change_analysis'):
                        st.markdown(f"**变化分析:** {rec['change_analysis'][:200]}")
                    if rec.get('is_first'):
                        st.markdown("**首次检测记录**")
        
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.monitoring and not st.session_state.paused:
        duration = st.session_state.get('last_check_duration', 0)
        interval = st.session_state.monitor_interval
        
        if duration >= interval:
            st.rerun()
        else:
            time.sleep(interval - duration)
            st.rerun()


if __name__ == "__main__":
    main()
import streamlit as st
import time
import sys
import os
import hashlib
import json
from datetime import datetime
import base64
import concurrent.futures
import pandas as pd
from io import StringIO, BytesIO

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


def export_to_csv(records):
    """导出历史记录为CSV格式"""
    df = pd.DataFrame(records)
    
    # 处理列表字段
    df['key_points'] = df['key_points'].apply(lambda x: '; '.join(x) if isinstance(x, list) else '')
    df['keywords'] = df['keywords'].apply(lambda x: '; '.join(x) if isinstance(x, list) else '')
    
    # 处理时间字段，在前面加英文单引号强制Excel按文本显示，避免自动按日期解析导致显示####
    if 'time' in df.columns:
        df['time'] = df['time'].apply(lambda x: f"'{x}" if x else '')
    
    # 选择要导出的列
    export_cols = ['time', 'title', 'main_content', 'key_points', 'keywords', 'change_analysis', 'status', 'images_count']
    
    # 如果有website字段，也添加进去
    if 'website' in df.columns:
        export_cols.insert(0, 'website')
    
    for col in export_cols:
        if col not in df.columns:
            df[col] = ''
    
    csv_buffer = StringIO()
    # 使用utf-8-sig确保Excel正确识别UTF-8编码，避免中文乱码
    df[export_cols].to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    return csv_buffer.getvalue()


def export_to_excel(records):
    """导出历史记录为Excel格式"""
    df = pd.DataFrame(records)
    
    # 处理列表字段
    df['key_points'] = df['key_points'].apply(lambda x: '; '.join(x) if isinstance(x, list) else '')
    df['keywords'] = df['keywords'].apply(lambda x: '; '.join(x) if isinstance(x, list) else '')
    
    # 处理时间字段，在前面加英文单引号强制Excel按文本显示，避免自动按日期解析导致显示####
    if 'time' in df.columns:
        df['time'] = df['time'].apply(lambda x: f"'{x}" if x else '')
    
    # 限制字段长度，避免内容过长导致显示问题
    max_lengths = {
        'title': 200,
        'main_content': 1000,
        'key_points': 500,
        'keywords': 300,
        'change_analysis': 1000
    }
    for col, max_len in max_lengths.items():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x)[:max_len] + '...' if len(str(x)) > max_len else x)
    
    # 选择要导出的列
    export_cols = ['time', 'title', 'main_content', 'key_points', 'keywords', 'change_analysis', 'status', 'images_count']
    
    # 如果有website字段，也添加进去
    if 'website' in df.columns:
        export_cols.insert(0, 'website')
    
    for col in export_cols:
        if col not in df.columns:
            df[col] = ''
    
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df[export_cols].to_excel(writer, index=False, sheet_name='历史记录')
        
        # 获取工作表
        worksheet = writer.sheets['历史记录']
        
        # 设置列宽，确保内容完全显示
        column_widths = [
            25,   # website
            20,   # time
            35,   # title
            50,   # main_content
            40,   # key_points
            30,   # keywords
            50,   # change_analysis
            12,   # status
            12    # images_count
        ]
        
        # 根据实际列数调整
        num_cols = len(export_cols)
        for i in range(num_cols):
            col_letter = chr(ord('A') + i)
            worksheet.column_dimensions[col_letter].width = column_widths[i] if i < len(column_widths) else 20
        
        # 设置单元格样式：自动换行、垂直居中、调整行高
        from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
        
        # 表头样式
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        # 内容样式
        content_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        # 边框样式
        thin_border = Border(left=Side(style='thin'), 
                            right=Side(style='thin'), 
                            top=Side(style='thin'), 
                            bottom=Side(style='thin'))
        
        # 应用表头样式
        for col in range(1, len(export_cols) + 1):
            cell = worksheet.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # 应用内容样式
        for row in range(2, len(df) + 2):
            for col in range(1, len(export_cols) + 1):
                cell = worksheet.cell(row=row, column=col)
                cell.alignment = content_alignment
                cell.border = thin_border
        
        # 设置行高
        worksheet.row_dimensions[1].height = 25  # 表头行高
        for row in range(2, len(df) + 2):
            worksheet.row_dimensions[row].height = 15  # 内容行高
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()


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
            # 1. 截图
            screenshot_start = time.time()
            screenshot_result = st.session_state.screenshot_tool._run(
                st.session_state.target_url,
                full_page=st.session_state.full_page_screenshot
            )
            timings['screenshot'] = time.time() - screenshot_start
            
            if screenshot_result.startswith("截图失败") or screenshot_result.startswith("截图功能不可用"):
                st.session_state.status = f"截图失败: {screenshot_result}"
                return
            
            screenshot_base64 = screenshot_result
            
            # 2. 立即计算图片哈希，判断是否有变化
            current_image_hash = hashlib.md5(base64.b64decode(screenshot_base64)).hexdigest()
            is_first_check = st.session_state.last_hash is None
            image_changed = False
            if not is_first_check and st.session_state.last_image_hash:
                image_changed = current_image_hash != st.session_state.last_image_hash
            
            # 3. 如果是首次检查或图片有变化，才继续处理
            if not is_first_check and not image_changed:
                st.session_state.status = "网站内容无变化"
                st.session_state.last_change = "none"
                st.session_state.last_check_duration = time.time() - start_time
                return
            
            # 4. 并行处理OCR识别
            ocr_start = time.time()
            screenshot_analysis = st.session_state.screenshot_analyzer._run(screenshot_base64)
            timings['ocr'] = time.time() - ocr_start
            content = screenshot_analysis.replace("识别文字:\n", "")
            images = []
        else:
            # 普通网页抓取模式
            scraper = WebScraperTool()
            result_str = scraper._run(st.session_state.target_url)
            result = json.loads(result_str)
            content = result.get('text', '')
            images = result.get('images', [])
            
            if not content or content.startswith("抓取失败"):
                st.session_state.status = f"获取网页内容失败: {content}"
                return
            
            current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            is_first_check = st.session_state.last_hash is None
            
            if not is_first_check and current_hash == st.session_state.last_hash:
                st.session_state.status = "网站内容无变化"
                st.session_state.last_change = "none"
                st.session_state.last_check_duration = time.time() - start_time
                return
            
            current_image_hash = None

        # 此时内容肯定有变化（或首次检查），继续处理
        if st.session_state.use_screenshot:
            # 对于截图模式，重新计算内容哈希
            current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        else:
            current_image_hash = None
        
        if is_first_check:
            st.session_state.status = "首次检测完成"
            st.session_state.last_change = "first"
        else:
            st.session_state.status = "检测到网站变化！"
            st.session_state.last_change = "changed"
            if st.session_state.use_screenshot and st.session_state.last_image_hash and current_image_hash:
                st.session_state.status += " (图片变化)"
        
        # 5. 并行处理LLM提取和关键词生成
        llm_start = time.time()
        cache_key = f"extraction_{current_hash}"
        keyword_key = f"keywords_{current_hash}"
        
        extracted_data = None
        keywords = None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 并行启动两个任务
            future_extract = None
            future_keywords = None
            
            if cache_key in st.session_state:
                extracted_data = st.session_state[cache_key]
            else:
                future_extract = executor.submit(
                    st.session_state.extractor.extract_structured_data,
                    content
                )
            
            if keyword_key in st.session_state:
                keywords = st.session_state[keyword_key]
            else:
                future_keywords = executor.submit(
                    st.session_state.supervisor._generate_keywords,
                    content
                )
            
            # 获取结果
            if future_extract:
                extracted_data = future_extract.result()
                st.session_state[cache_key] = extracted_data
            if future_keywords:
                keywords = future_keywords.result()
                st.session_state[keyword_key] = keywords
        
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
            st.markdown("<p style='color: #f59e0b; font-size: 14px;'>⚠️ 截图模式需要安装浏览器驱动，识别时间增加</p>", unsafe_allow_html=True)
            
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
        import time
        
        current_time = time.time()
        last_run = st.session_state.get('last_run_time', 0)
        interval = st.session_state.monitor_interval
        
        if current_time - last_run >= interval:
            with st.spinner("正在检测网站变化..."):
                check_website_change()
            st.session_state.last_run_time = time.time()
            st.rerun()

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
        
        # 简化布局：清空按钮和导出按钮放在同一行
        col_actions = st.columns([1, 2, 1, 1, 3])
        with col_actions[0]:
            if st.button("🗑️ 清空", type="secondary", use_container_width=True, help="清空所有历史记录"):
                st.session_state.history_records = {}
                st.rerun()
        
        with col_actions[1]:
            # 导出范围选择器
            export_options = ["📊 全部记录"] + [f"🌐 {url[:30]}..." for url in list(st.session_state.history_records.keys())]
            selected_export = st.selectbox(
                "导出范围",
                options=export_options,
                key="export_range",
                label_visibility="collapsed",
                help="选择要导出的记录范围"
            )
        
        # 准备导出数据
        export_records = []
        file_suffix = "all"
        
        if selected_export == "📊 全部记录":
            for url, records in st.session_state.history_records.items():
                for rec in records:
                    rec_export = rec.copy()
                    rec_export['website'] = url
                    export_records.append(rec_export)
        else:
            # 提取选中的网站URL
            selected_url = list(st.session_state.history_records.keys())[export_options.index(selected_export) - 1]
            for rec in st.session_state.history_records[selected_url]:
                rec_export = rec.copy()
                rec_export['website'] = selected_url
                export_records.append(rec_export)
            file_suffix = "single"
        
        with col_actions[2]:
            if export_records:
                csv_data = export_to_csv(export_records)
                st.download_button(
                    label="📥 导出 CSV",
                    data=csv_data,
                    file_name=f"website_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_suffix}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="导出选中范围的历史记录为CSV格式"
                )
        
        with col_actions[3]:
            if export_records:
                excel_data = export_to_excel(export_records)
                st.download_button(
                    label="📥 导出 Excel",
                    data=excel_data,
                    file_name=f"website_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_suffix}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="导出选中范围的历史记录为Excel格式"
                )
        
        with col_actions[4]:
            view_mode = st.radio(
                "查看模式",
                ["按网站分类", "全部记录时间线"],
                key="history_view_mode",
                horizontal=True,
                label_visibility="collapsed"
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
                        
                        # 只有在expander展开时才显示截图，避免不必要的处理
                        if rec.get('screenshot_base64') or rec.get('has_screenshot'):
                            st.markdown("**截图预览:**")
                            try:
                                # 直接显示base64图片，不做处理，提高性能
                                st.image(f"data:image/jpeg;base64,{rec['screenshot_base64']}", 
                                        caption=f"网站截图 - {rec['time']}", 
                                        use_container_width=True)
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
                                for i, img_url in enumerate(valid_images[:3]):  # 减少显示数量
                                    with cols[i % 3]:
                                        try:
                                            st.image(img_url, caption=f"图片 {i+1}", width=200)
                                        except Exception as e:
                                            st.markdown(f"❌ 图片 {i+1} 加载失败")
                        
                        if rec.get('ocr_results') and len(rec['ocr_results']) > 0:
                            st.markdown("**OCR识别结果:**")
                            ocr_result = rec['ocr_results'][0] if isinstance(rec['ocr_results'], list) else rec['ocr_results']
                            if isinstance(ocr_result, dict):
                                text = ocr_result.get('text', '')
                                if text and not text.startswith("截图中未识别"):
                                    lines = text.replace("识别文字:\n", "").split('\n')
                                    for line in lines[:10]:  # 减少显示行数
                                        if line.strip():
                                            st.markdown(f"- {line.strip()}")
                                else:
                                    st.markdown(f"- {text if text else '未识别到文字'}")
                            else:
                                text = str(ocr_result)
                                if text and not text.startswith("截图中未识别"):
                                    lines = text.replace("识别文字:\n", "").split('\n')
                                    for line in lines[:10]:
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
                    
                    # 直接显示base64图片，不做处理，提高性能
                    if rec.get('screenshot_base64') or rec.get('has_screenshot'):
                        st.markdown("**截图预览:**")
                        try:
                            st.image(f"data:image/jpeg;base64,{rec['screenshot_base64']}", 
                                    caption=f"网站截图 - {rec['time']}", 
                                    use_container_width=True)
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
                            for i, img_url in enumerate(valid_images[:3]):  # 减少显示数量
                                    with cols[i % 3]:
                                        try:
                                            st.image(img_url, caption=f"图片 {i+1}", width=200)
                                        except Exception as e:
                                            st.markdown(f"❌ 图片 {i+1} 加载失败")
                    
                    if rec.get('ocr_results') and len(rec['ocr_results']) > 0:
                        st.markdown("**OCR识别结果:**")
                        ocr_result = rec['ocr_results'][0] if isinstance(rec['ocr_results'], list) else rec['ocr_results']
                        if isinstance(ocr_result, dict):
                            text = ocr_result.get('text', '')
                            if text and not text.startswith("截图中未识别"):
                                lines = text.replace("识别文字:\n", "").split('\n')
                                for line in lines[:10]:  # 减少显示行数
                                    if line.strip():
                                        st.markdown(f"- {line.strip()}")
                            else:
                                st.markdown(f"- {text if text else '未识别到文字'}")
                        else:
                            text = str(ocr_result)
                            if text and not text.startswith("截图中未识别"):
                                lines = text.replace("识别文字:\n", "").split('\n')
                                for line in lines[:10]:
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
        st.rerun()


if __name__ == "__main__":
    main()
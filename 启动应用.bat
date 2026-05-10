@echo off
cd /d %~dp0
python -m streamlit run src/streamlit_app.py --server.port=8501
pause
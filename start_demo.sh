#!/bin/bash
# Start Streamlit demo app

echo "🚀 Starting PP-DocLayout Demo..."
echo "🌐 App sẽ mở tại: http://localhost:8501"
echo ""

uv run streamlit run demo_app.py --server.port 8501

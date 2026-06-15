#!/bin/bash
cd "$(dirname "$0")"
~/.local/bin/uvx --with-requirements mm_fantasy/requirements.txt streamlit run mm_fantasy/app.py --server.port 8502 --server.headless true

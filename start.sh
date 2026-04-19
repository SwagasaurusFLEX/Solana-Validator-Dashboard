#!/bin/bash
set -e

mkdir -p .streamlit
echo "$STREAMLIT_SECRETS_TOML" > .streamlit/secrets.toml

exec streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
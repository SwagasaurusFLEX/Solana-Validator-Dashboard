#!/bin/bash
set -e

# Write Streamlit secrets from env var to absolute path
mkdir -p /app/.streamlit

if [ -z "$STREAMLIT_SECRETS_TOML" ]; then
  echo "ERROR: STREAMLIT_SECRETS_TOML env var is not set or empty"
  echo "Set it in Railway → Variables tab"
  exit 1
fi

echo "$STREAMLIT_SECRETS_TOML" > /app/.streamlit/secrets.toml
echo "Wrote secrets.toml ($(wc -c < /app/.streamlit/secrets.toml) bytes)"

# Also write to relative path as fallback
mkdir -p .streamlit
cp /app/.streamlit/secrets.toml .streamlit/secrets.toml

exec streamlit run streamlit_app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true
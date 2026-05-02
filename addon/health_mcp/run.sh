#!/usr/bin/with-contenv bashio
set -euo pipefail

export HEALTH_MCP_HOST="0.0.0.0"
export HEALTH_MCP_PORT="$(bashio::config 'port')"
export HEALTH_MCP_DB_HOST="$(bashio::config 'db_host')"
export HEALTH_MCP_DB_PORT="$(bashio::config 'db_port')"
export HEALTH_MCP_DB_NAME="$(bashio::config 'db_name')"
export HEALTH_MCP_DB_USER="$(bashio::config 'db_user')"
export HEALTH_MCP_DB_PASSWORD="$(bashio::config 'db_password')"
export HEALTH_MCP_AUTO_MIGRATE="$(bashio::config 'auto_migrate')"
export HEALTH_MCP_LOG_LEVEL="$(bashio::config 'log_level')"

if bashio::config.has_value 'api_key'; then
    export HEALTH_MCP_API_KEY="$(bashio::config 'api_key')"
fi

bashio::log.info "Starting Health MCP on port ${HEALTH_MCP_PORT}"

cd /usr/src/app
exec python -m health_mcp


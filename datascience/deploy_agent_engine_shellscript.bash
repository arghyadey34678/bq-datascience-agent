#!/bin/bash
# v4_3-deploy-agent.sh
# Deploy agent to Agent Engine as pom_agent_v4.0
# Part of pom_agent_v4.0 deployment workflow
set -e # Exit on error

# Configuration
PROJECT_ID="np-sc-inventory-execution"
REGION="us-central1"
DISPLAY_NAME="pom_agent_v4.0"
AGENT_DIR="bigquery_agent"
VENV_DIR=".venv"
WORKSPACE_DIR="/Users/AXD8G82/mlpoc/agent-poc"
ENGINE_ID_FILE="${WORKSPACE_DIR}/AGENT_ENGINE_V4_ID.txt"

# Check if virtual environment exists
if [ ! -d "${WORKSPACE_DIR}/${VENV_DIR}" ]; then
    echo "❌ Error: Virtual environment not found at ${WORKSPACE_DIR}/${VENV_DIR}"
    echo "   Please create it first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "${WORKSPACE_DIR}/${VENV_DIR}/bin/activate"
echo "✅ Virtual environment activated"

# Change to workspace directory
cd "${WORKSPACE_DIR}"

# Deploy agent
echo "🚀 Deploying agent to Agent Engine..."
echo "   This may take 2-3 minutes..."
adk deploy agent_engine \
  --display_name="${DISPLAY_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  "${AGENT_DIR}"

# Extract engine ID from output
if [ -f "${WORKSPACE_DIR}/bigquery_agent/.agent_engine_config.json" ]; then
    ENGINE_ID=$(grep -o '"reasoning_engine_id": "[^"]*"' "${WORKSPACE_DIR}/bigquery_agent/.agent_engine_config.json" | cut -d'"' -f4)

    if [ -n "$ENGINE_ID" ]; then
        echo "$ENGINE_ID" > "$ENGINE_ID_FILE"
        echo ""
        echo "✅ Agent deployed successfully"
        echo "   Engine ID: ${ENGINE_ID}"
        echo "   Saved to: ${ENGINE_ID_FILE}"
    fi
fi

echo ""
echo "📄 View your agent at:"
echo "   https://console.cloud.google.com/vertex-ai/reasoning-engines?project=${PROJECT_ID}"
echo ""
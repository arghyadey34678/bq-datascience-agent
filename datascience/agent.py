"""
POM Data Science Agent - Advanced Analytics and Forecasting
This agent specializes in:
- Statistical analysis
- Forecasting and trend analysis
- Data visualization
- Anomaly detection
- Predictive modeling
It works alongside the BigQuery agent to provide advanced analytics capabilities.
"""

from google.adk.agents import Agent
from google.genai import types
import os
from pathlib import Path
from dotenv import load_dotenv
from .instructions import DATA_SCIENCE_INSTRUCTIONS

# Try to import VertexAiCodeExecutor, but make it optional for local dev
try:
    from google.adk.code_executors import VertexAiCodeExecutor
    HAS_CODE_EXECUTOR = True
except ImportError:
    HAS_CODE_EXECUTOR = False

# Load .env file (optional for local development)
try:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass # .env file not required in deployed environment

# Configuration
AGENT_NAME = "POM_DataScience_Agent"
GEMINI_MODEL = "gemini-2.5-pro" # Pro model for advanced reasoning and code execution
PROJECT_ID = os.getenv("PROJECT_ID", "np-sc-inventory-execution")
LOCATION = os.getenv("LOCATION", "us-central1")

# Set environment variables for google-genai client to use Vertex AI
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = PROJECT_ID
os.environ['GOOGLE_CLOUD_LOCATION'] = LOCATION

# Create code executor if available (for deployed environment)
code_executor = None
if HAS_CODE_EXECUTOR:
    try:
        code_executor = VertexAiCodeExecutor(
            location=LOCATION,
            project=PROJECT_ID,
        )
        print(f"✅ Code executor enabled for {AGENT_NAME}")
    except Exception as e:
        print(f"⚠️ Code executor unavailable: {e}")
        pass # Code executor not available in local dev
        
# Create the analytics agent with code execution capabilities
root_agent = Agent(
    name=AGENT_NAME,
    model=GEMINI_MODEL,
    description="""
Advanced data science agent specializing in statistical analysis,
forecasting, trend detection, and data visualization for supply chain operations.

Use this agent for:
- Time series forecasting
- Anomaly detection
- Correlation analysis
- Trend analysis
- Data visualization (charts, graphs)
- Statistical modeling
- Predictive analytics

This agent works with data provided by the BigQuery agent and performs
Python-based analysis using pandas, numpy, matplotlib, and scipy.
""",
    instruction=DATA_SCIENCE_INSTRUCTIONS,
    code_executor=code_executor,
    tools=[],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.01, # Low temperature for precise analytical tasks
        # Enable safety settings for code execution
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH"
            )
        ]
    ),
)

# Export for ADK deployment
app = root_agent
from google.adk.agents import Agent
from google.adk.tools import bigquery
import os
from pathlib import Path
from google.adk.tools.bigquery import BigQueryCredentialsConfig
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
from google.genai import import types
import google.auth
from google.auth.transport.requests import import Request
from google.cloud import bigquery as bq_client # aliased for clarity
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from google.adk.memory import VertexAiMemoryBankService
from google.adk.runners import Runner
from .instructions import ENTRY_AGENT_INSTRUCTIONS

# Commented out for standalone Agent Engine deployment
# from search_agent.agent import search_agent
# from confluence_agent.agent import confluence_agent
# from jira_agent.agent import jira_agent

from datetime import datetime, timedelta
import threading

# Load .env file for ADK web (which doesn't auto-load it)
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Define constants for this example agent
AGENT_NAME = "POM_Agent"
APP_NAME = "agents"  # Changed to match ADK's expected app name
USER_ID = "arghya_dey@homedepot.com"
# GEMINI_MODEL = "gemini-2.0-flash-exp"
GEMINI_MODEL = "gemini-1.5-pro"
PROJECT_ID = "np-sc-inventory-execution"
LOCATION = "us-central1"  # Agent Engine region
DEFAULT_DATASET = "pom_ai_analytics"  # Default dataset to work with
FULL_DATASET = f"{PROJECT_ID}.{DEFAULT_DATASET}"

# RAG Corpus ID (in us-east1, referenced cross-region)
RAG_LOCATION = "us-east1"  # RAG corpus location
# Load corpus ID from file
RAG_CORPUS_ID_FILE = Path(__file__).parent.parent / "RAG_CORPUS_ID.txt"
if RAG_CORPUS_ID_FILE.exists():
    with open(RAG_CORPUS_ID_FILE, 'r') as f:
        RAG_CORPUS_POM_AI = f.read().strip()
else:
    RAG_CORPUS_POM_AI = "2189312368855482368"  # Default corpus ID for POM_KB_RAG
    
# Agent Engine ID for Memory Bank (load from file after deployment)
AGENT_ENGINE_ID_FILE = Path(__file__).parent.parent / "AGENT_ENGINE_ID.txt"
if AGENT_ENGINE_ID_FILE.exists():
    with open(AGENT_ENGINE_ID_FILE, 'r') as f:
        AGENT_ENGINE_ID = f.read().strip()
else:
    AGENT_ENGINE_ID = os.getenv('AGENT_ENGINE_ID', None)  # Fallback to env var

# Load RAG memory content from corpus
def load_rag_memory():
    """Load all documents from RAG corpus dynamically."""
    # This function retrieves all files from the RAG corpus instead of using 
    # a static file. It combines all documents to create a comprehensive 
    # knowledge base for the agent.
    try:
        from google.cloud.aiplatform_v1beta1 import VertexRagDataServiceClient
        
        corpus_name = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/ragCorpora/{RAG_CORPUS_POM_AI}"
        print(f"Loading RAG memory from corpus: {corpus_name}")

        # Create RAG data service client
        client = VertexRagDataServiceClient(
            client_options={"api_endpoint": f"{RAG_LOCATION}-aiplatform.googleapis.com"}
        )

        # List all files in corpus
        from google.cloud.aiplatform_v1beta1.types import ListRagFilesRequest
        request = ListRagFilesRequest(parent=corpus_name)
        response = client.list_rag_files(request=request)

        # Count files
        file_list = list(response)
        print(f" Found {len(file_list)} files in corpus")

        # For static memory, we'll use the fact that files are in the corpus
        # The RAG retrieval tool will access them dynamically during queries
        combined_content = []
        for rag_file in file_list:
            display_name = rag_file.display_name or rag_file.name.split('/')[-1]
            print(f" - Registered: {display_name}")
            # Add file reference to memory
            combined_content.append(f"# Corpus File: {display_name}\n")

        if combined_content:
            memory_content = f"# RAG Corpus Files (Total: {len(file_list)})\n\n"
            memory_content += "The following files are available in the RAG corpus and will be retrieved dynamically:\n\n"
            memory_content += "\n".join(combined_content)
            print(f"✅ Loaded {len(file_list)} documents from corpus")
            return memory_content
        else:
            print("⚠️ No documents found in corpus")
            return ""

    except Exception as e:
        print(f"❌ Could not load from corpus: {str(e)}")
        print("  Please ensure the corpus is properly configured and accessible")
        return ""

RAG_MEMORY = load_rag_memory()
# Schema cache with timestamp
class SchemaCache:
    """Thread-safe cache for dataset schema with automatic refresh."""
    def __init__(self, refresh_interval_minutes=360):
        self.schema = ""
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=refresh_interval_minutes)
        self.lock = threading.Lock()

    def get_schema(self, force_refresh=False):
        """Get schema, refreshing if expired or forced."""
        with self.lock:
            now = datetime.now()
            should_refresh = (
                force_refresh or
                self.last_refresh is None or
                (now - self.last_refresh) > self.refresh_interval
            )

            if should_refresh:
                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Refreshing BigQuery schema...")
                self.schema = self._fetch_schema()
                self.last_refresh = now
                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Schema refresh complete.")
            
            return self.schema

    def _fetch_schema(self):
        """Retrieve schema information for all tables in the default dataset."""
        try:
            client = bq_client.Client(project=PROJECT_ID)
            tables = client.list_tables(FULL_DATASET)

            schema_info = []
            for table in tables:
                table_ref = client.get_table(f"{FULL_DATASET}.{table.table_id}")
                columns = []
                for field in table_ref.schema:
                    columns.append(f" - {field.name} ({field.field_type}): {field.description or 'No description'}")
                
                schema_info.append(f"\nTable: {table.table_id}\nColumns:\n" + "\n".join(columns))
            
            return "\n".join(schema_info) if schema_info else "No tables found in dataset."
        except Exception as e:
            return f"Unable to retrieve schema: {str(e)}"

# Initialize schema cache (refreshes every 6 hours by default)
schema_cache = SchemaCache(refresh_interval_minutes=360)

# Function to manually refresh schema
    def refresh_schema():
        """Manually refresh the dataset schema cache."""
        return schema_cache.get_schema(force_refresh=True)

    # Get initial schema
    DATASET_SCHEMA = schema_cache.get_schema()
    # Set environment variables for google-genai client to use Vertex AI
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = PROJECT_ID
os.environ['GOOGLE_CLOUD_LOCATION'] = LOCATION
# Set BigQuery default project and dataset via environment variables
os.environ['BIGQUERY_PROJECT'] = PROJECT_ID
os.environ['BIGQUERY_DATASET'] = DEFAULT_DATASET
os.environ['BIGQUERY_LOCATION'] = LOCATION

# Define a tool configuration
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

# Get credentials - will use the service account configured in Agent Engine
application_default_credentials, project = google.auth.default(
    scopes=['https://www.googleapis.com/auth/bigquery', 'https://www.googleapis.com/auth/cloud-platform'],
    quota_project_id=PROJECT_ID
)

print(f"Using credentials for project: {project}")
print(f"Credential type: {type(application_default_credentials).__name__}")

# Refresh credentials if expired or about to expire
if not application_default_credentials.valid:
    print("Refreshing expired credentials...")
    application_default_credentials.refresh(Request())
    print("Credentials refreshed successfully!")

credentials_config = BigQueryCredentialsConfig(credentials=application_default_credentials)

bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    bigquery_tool_config=tool_config
)

# Create RAG retrieval tool with pom-ai corpus (cross-region reference)
rag_retrieval = VertexAiRagRetrieval(
    name="rag_knowledge_base",
    description="Retrieves information from the pom-ai knowledge base including documentation, guidelines, and best practices",
    rag_corpora=[
        f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/ragCorpora/{RAG_CORPUS_POM_AI}"
    ],
    similarity_top_k=10, # Return top 10 results
    vector_distance_threshold=0.3 # Similarity threshold
)

def _create_agent_instruction():
    """Create agent instruction with fresh schema."""
    # Load instruction template and replace placeholders
    # instruction.md already contains the complete system prompt with identity
    base_instruction = ENTRY_AGENT_INSTRUCTIONS

    # Replace template variables
    base_instruction = base_instruction.replace("{PROJECT_ID}", PROJECT_ID)
    base_instruction = base_instruction.replace("{DEFAULT_DATASET}", DEFAULT_DATASET)
    base_instruction = base_instruction.replace("{LOCATION}", LOCATION)
    base_instruction = base_instruction.replace("{schema_cache_schema}", DATASET_SCHEMA)

    return base_instruction

def create_agent():
    """Create or recreate agent with fresh schema."""
    
    # Attempt to load DataScience agent (may take time on first initialization)
    datascience_agent = None
    try:
        print(" Loading DataScience agent...")
        from datascience_agent.agent import root_agent as datascience_agent
        print(" ✅ DataScience agent loaded successfully")
    except Exception as e:
        print(f" ⚠️ DataScience agent could not be loaded: {str(e)}")
        print("   The agent will run without advanced analytics capabilities")
        print("   This is usually due to Vertex AI Code Executor initialization")

    # Prepare sub-agents list
    sub_agents = []
    if datascience_agent is not None:
        sub_agents.append(datascience_agent)
        print(" - DataScience agent enabled for analytics")
    else:
        print(" - DataScience agent disabled")

    agent = Agent(
        name=AGENT_NAME,
        model=GEMINI_MODEL,
        description="A helpful assistant that can answer questions about Purchase Orders from BigQuery with access to pom-ai RAG kn...",
        instruction=_create_agent_instruction(),
        static_instruction=RAG_MEMORY, # Add RAG.md as static memory bank
        tools=[bigquery_toolset, rag_retrieval], # BigQuery and RAG retrieval tools
        sub_agents=sub_agents, # Data science agent as helper for analytics (if available)
        # For multi-agent setup, add: AgentTool(search_agent), AgentTool(confluence_agent), AgentTool(jira_agent)
    )

    # Log RAG and Memory Bank configuration
    print(f"✅ Agent created with:")
    print(f" - Model: {GEMINI_MODEL}")
    print(f" - RAG Corpus ID: {RAG_CORPUS_POM_AI}")
    print(f" - Agent Engine ID: {AGENT_ENGINE_ID or 'Not configured (deploy first)'}")
    print(f" - Memory Bank: {'Enabled' if AGENT_ENGINE_ID else 'Disabled (will be enabled on deployment)'}")

    return agent
    
def create_runner_with_memory_bank(agent_engine_id=None):
    """Create a Runner with Memory Bank service enabled for local testing.

    NOTE: When deployed to Agent Engine, Memory Bank is automatically enabled.
    This function is primarily for local testing and development.
    
    Args:
        agent_engine_id: The ID of the deployed Agent Engine (e.g., '135538667527147392')
                        If None, Memory Bank will not be enabled until agent is deployed.
    Returns:
        A Runner configured with Memory Bank service.
    """
    agent = create_agent()

    # Configure Memory Bank service if agent_engine_id is provided
    if agent_engine_id:
        memory_service = VertexAiMemoryBankService(
            project=PROJECT_ID,
            location=LOCATION,
            agent_engine_id=agent_engine_id
        )
        print(f"✅ Memory Bank enabled for Agent Engine ID: {agent_engine_id}")
    else:
        memory_service = None
        print("ℹ️ Memory Bank not configured (no agent_engine_id provided)")
        print("   When deployed to Agent Engine, Memory Bank is automatically enabled")

    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        user_id=USER_ID,
        memory_service=memory_service
    )
    return runner

# Export the raw agent for Agent Engine deployment
# ADK will wrap this with a Runner automatically when deploying
root_agent = create_agent()

# For local testing with Memory Bank, create a runner if AGENT_ENGINE_ID is available
if AGENT_ENGINE_ID:
    try:
        from google.adk.sessions import InMemorySessionService
        session_service = InMemorySessionService()
        memory_service = VertexAiMemoryBankService(
            project=PROJECT_ID,
            location=LOCATION,
            agent_engine_id=AGENT_ENGINE_ID
        )
        # Create a runner for local testing with memory
        local_runner_with_memory = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=session_service,
            memory_service=memory_service,
        )
        print(f"✅ Local runner created with Memory Bank (Agent Engine ID: {AGENT_ENGINE_ID})")
    except Exception as e:
        print(f"⚠️ Could not initialize Memory Bank for local testing: {e}")
        print("   Memory Bank will still be enabled when deployed to Agent Engine")

# Note: When deployed via `adk deploy agent_engine`, the agent is automatically
# wrapped with a Runner that includes Memory Bank service. The Runner exposes
# the agent's generate() method through its own interface.

# Export alias for ADK deployment (some versions expect 'app')
app = root_agent
"""
Agent instructions loader module.
Loads instruction templates from GCS bucket or local markdown files.
"""

from pathlib import Path
from google.cloud import storage

PROJECT_ID = "np-sc-inventory-execution"
GCS_BUCKET = "pom-ai-agent-kb"
PROMPT_FOLDER = "POM_PROMPT"

def load_instruction_template() -> str:
    
    """Load all instruction files from GCS bucket POM_PROMPT folder or local POM_PROMPT folder"""
    all_content = []
    try:
        # Try loading from GCS bucket first
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET)
        
        # List all files in POM_PROMPT folder
        blobs = list(bucket.list_blobs(prefix=f"{PROMPT_FOLDER}/"))
        
        # Filter for markdown files and exclude directory markers
        instruction_files = [blob for blob in blobs if blob.name.endswith('.md') and not blob.name.endswith('/')]
        
        if not instruction_files:
            raise FileNotFoundError(f"No instruction files found in gs://{GCS_BUCKET}/{PROMPT_FOLDER}/")
            
        print(f"✅ Found {len(instruction_files)} instruction file(s) in GCS")
        
        for blob in instruction_files:
            content = blob.download_as_string().decode('utf-8')
            all_content.append(content)
            print(f" - Loaded {blob.name}")
            
        return "\n\n".join(all_content)

    except Exception as e:
        print(f"⚠️ Could not load from GCS: {str(e)}")
        print(" Falling back to local files...")
        
        # Fallback to local files
        local_folder = Path(__file__).parent / "POM_PROMPT"
        
        if not local_folder.exists():
            raise FileNotFoundError(f"POM_PROMPT folder not found: {local_folder}")
            
        instruction_files = list(local_folder.glob("*.md"))
        
        if not instruction_files:
            raise FileNotFoundError(f"No instruction files found in {local_folder}")
            
        print(f"✅ Found {len(instruction_files)} instruction file(s) locally")
        
        for file_path in instruction_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                all_content.append(content)
                print(f" - Loaded {file_path.name}")
                
        return "\n\n".join(all_content)

# Load the instruction template
ENTRY_AGENT_INSTRUCTIONS = load_instruction_template()
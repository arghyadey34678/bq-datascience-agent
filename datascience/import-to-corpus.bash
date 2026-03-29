#!/bin/bash
# v4_2-import-to-corpus.sh
# Dynamically import all RAG files from GCS to corpus POM_KB_RAG
set -e # Exit on error
CORPUS_ID="2189312368855482368"
PROJECT_ID="np-sc-inventory-execution"
LOCATION="us-east1"
GCS_BUCKET="pom-ai-agent-kb"
RAG_FOLDER="POM_RAG"

echo "🔑 Getting access token..."
ACCESS_TOKEN=$(gcloud auth print-access-token)
if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Error: Could not get access token Please run: gcloud auth login"
    exit 1
fi

echo "✅ Access token obtained"

# List all .md files in the RAG folder
echo "🔍 Discovering RAG files in GCS..."
FILES=($(gsutil ls "gs://${GCS_BUCKET}/${RAG_FOLDER}/" | grep '\.md$'))
if [ ${#FILES[@]} -eq 0 ]; then
    echo "❌ Error: No .md files found in gs://${GCS_BUCKET}/${RAG_FOLDER}/"
    exit 1
fi

echo "✅ Found ${#FILES[@]} files to import:"
for file in "${FILES[@]}"; do
    echo " - $file"
done

# Build JSON array of file URIs
FILE_URIS=$(printf '%s\n' "${FILES[@]}" | jq -R . | jq -s .)

# Import files to corpus
echo "🚀 Importing files to corpus..."
RESPONSE=$(curl -s -X POST \
-H "Authorization: Bearer ${ACCESS_TOKEN}" \
-H "Content-Type: application/json" \
"https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora/${CORPUS_ID}/ragFiles:import" \
-d "{
    \"importRagFilesConfig\": {
        \"gcsSource\": {
            \"uris\": ${FILE_URIS}
        }
    }
}")

# Parse response
OPERATION_NAME=$(echo "$RESPONSE" | jq -r '.name // empty')
if [ -z "$OPERATION_NAME" ]; then
    echo "❌ Error: Import failed"
    echo "Response: $RESPONSE"
    exit 1
fi

OPERATION_ID=$(echo "$OPERATION_NAME" | awk -F'/' '{print $NF}')
echo "✅ Import operation started gcloud ai operations describe ${OPERATION_ID} --region=${LOCATION}"
echo "✨ Operation ID: ${OPERATION_ID}"
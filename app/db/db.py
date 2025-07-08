from azure.cosmos import CosmosClient, PartitionKey
from dotenv import load_dotenv
import os
from pathlib import Path


load_dotenv()

# === Cosmos DB Setup ===
COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")
COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")

client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
database = client.create_database_if_not_exists(id=COSMOS_DB_NAME)
container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER_NAME,
    partition_key=PartitionKey(path="/user_id"),
    offer_throughput=400
)

# === Save metadata ===
def save_metadata(data: dict):
    try:
        # Ensure fields are JSON-safe (no custom number formats)
        if "tags" in data and isinstance(data["tags"], dict):
            try:
                data["tags"]["price"] = float(data["tags"].get("price", 0.0))
            except:
                data["tags"]["price"] = 0.0

        container.create_item(body=data)
    except Exception as e:
        print(f"[DB] Error saving metadata: {e}")

# === Check if file already processed ===
def was_already_processed(blob_path: str) -> bool:
    query = "SELECT * FROM c WHERE c.original_blob_name = @blob_path"
    items = list(container.query_items(
        query=query,
        parameters=[{"name": "@blob_path", "value": blob_path}],
        enable_cross_partition_query=True
    ))
    return len(items) > 0

# === Get all docs for a user ===
def get_user_docs(user_id: str) -> list[dict]:
    query = "SELECT * FROM c WHERE c.user_id = @user_id"
    items = list(container.query_items(
        query=query,
        parameters=[{"name": "@user_id", "value": user_id}],
        enable_cross_partition_query=True
    ))
    return items

# === Get document summaries ===

def get_summary_by_job(user_id: str, job_id: str):
    docs = get_user_docs(user_id)  # This already filters by user_id
    for doc in docs:
        if doc.get("job_id") == job_id:
            return {
                "job_id": doc.get("job_id"),
                "user_id": doc.get("user_id"),
                "user_directory": doc.get("user_directory"),
                "filename": Path(doc.get("original_blob_name", "")).name,
                "summary": doc.get("summary", "No summary available.")
            }
    return None
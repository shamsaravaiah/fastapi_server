# app/db.py

from tinydb import TinyDB, Query
from pathlib import Path

# === DB Setup ===
DB_PATH = Path("app/db/metadata.json")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = TinyDB(DB_PATH)
docs_table = db.table("documents")


def save_metadata(data: dict):
    docs_table.insert(data)


def was_already_processed(blob_path: str) -> bool:
    Document = Query()
    result = docs_table.search(Document.original_blob_name == blob_path)
    return len(result) > 0


def get_user_docs(user_directory: str) -> list[dict]:
    Document = Query()
    return docs_table.search(Document.user_directory == user_directory)

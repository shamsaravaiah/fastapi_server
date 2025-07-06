from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from app.pipeline import process_file
from app.db import save_metadata, get_user_docs
from typing import Optional

app = FastAPI()

# Allow frontend (adjust if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === POST: Upload and process file ===
@app.post("/upload/")
async def upload_file(
    file: UploadFile,
    user_directory: str = Form(...)
):
    try:
        result = await process_file(file, user_directory)
        if result:
            save_metadata(result)
            return {"status": "success", "metadata": result}
        else:
            return {"status": "skipped", "reason": "Already processed or unsupported format"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# === GET: Retrieve processed documents by user ===
@app.get("/documents/{user_directory}")
def get_documents(user_directory: str):
    try:
        docs = get_user_docs(user_directory)
        return {"status": "success", "documents": docs}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

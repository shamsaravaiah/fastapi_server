# app/main.py

from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from app.pipeline import process_file
from app.db import save_metadata, get_user_docs
from typing import Optional

app = FastAPI()

# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === POST: Upload file ===
@app.post("/upload/")
async def upload_file(
    file: UploadFile,
    user_id: str = Form(...),
    user_directory: str = Form(...)
):
    try:
        result = await process_file(file, user_id=user_id, user_directory=user_directory)
        if result:
            save_metadata(result)
            return {"status": "success", "metadata": result}
        else:
            return {"status": "skipped", "reason": "Already processed or unsupported format"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# === GET: Fetch all docs by user ID ===
@app.get("/documents/{user_id}")
def get_documents(user_id: str):
    try:
        docs = get_user_docs(user_id)
        return {"status": "success", "documents": docs}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

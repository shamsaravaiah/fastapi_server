# app/main.py

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.pipeline import process_file
from app.db import save_metadata, get_user_docs

app = FastAPI()

# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend domain if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === POST: Upload one or more files ===
@app.post("/upload/")
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...),
    user_directory: str = Form(...)
):
    results = []

    for file in files:
        try:
            result = await process_file(file, user_id=user_id, user_directory=user_directory)
            if result:
                save_metadata(result)
        except Exception as e:
            print(f"[ERROR] Processing file '{file.filename}': {e}")

    # After all processing, fetch updated metadata from DB
    try:
        documents = get_user_docs(user_id)
        return {"status": "success", "documents": documents}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
# 
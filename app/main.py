# app/main.py

from fastapi import FastAPI, UploadFile, Form, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List

from app.pipeline import process_file
from app.db import save_metadata, get_user_docs
from app.db import get_summary_by_job

app = FastAPI()

# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "FastAPI backend is running."}

# === POST: Upload one or more files ===
@app.post("/upload/")
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...),
    user_directory: str = Form(...)
):
    for file in files:
        try:
            result = await process_file(file, user_id=user_id, user_directory=user_directory)
            if result:
                save_metadata(result)
        except Exception as e:
            print(f"[ERROR] Processing file '{file.filename}': {e}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "detail": f"Failed to process {file.filename}: {e}"}
            )

    return {"status": "success", "detail": "Files processed and metadata saved."}

# === GET: Retrieve metadata documents for a user ===
@app.get("/documents/")
async def get_documents(user_id: str = Query(...)):
    try:
        documents = get_user_docs(user_id)
        return {"status": "success", "documents": documents}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    

    # === GET: Specific summary for a document belonging to a specific user ===
@app.get("/summary/{job_id}")
async def get_summary_for_document(job_id: str, user_id: str = Query(...)):
    try:
        summary_data = get_summary_by_job(user_id=user_id, job_id=job_id)
        if summary_data:
            return {"status": "success", "summary": summary_data}
        else:
            return {"status": "not_found", "detail": "No matching document or summary found."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
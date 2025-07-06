import os
import time
import json
import fitz  # PyMuPDF
from uuid import uuid4
from pathlib import Path
from google.cloud import vision
import google.generativeai as genai
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from app.db import was_already_processed

# === Load .env configuration ===
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
DEFAULT_USER_DIRECTORY = os.getenv("DEFAULT_USER_DIRECTORY")

# === Set up clients ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
genai.configure(api_key=GEMINI_KEY)
vision_client = vision.ImageAnnotatorClient()
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]

# === OCR Function ===
def run_ocr(file_bytes: bytes, ext: str) -> str:
    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            image = vision.Image(content=pix.tobytes("png"))
            res = vision_client.document_text_detection(image=image)
            text += f"\n--- Page {i+1} ---\n"
            text += res.text_annotations[0].description.strip() if res.text_annotations else "No text"
        return text.strip()
    else:
        image = vision.Image(content=file_bytes)
        res = vision_client.document_text_detection(image=image)
        return res.text_annotations[0].description.strip() if res.text_annotations else "No text"

# === Gemini LLM Tagging ===
def extract_tags(ocr_text: str) -> dict:
    prompt = f"""
Extract this info from the OCR receipt:

- vendor
- product_or_service
- price (SEK)

Only return valid JSON:
\"\"\"{ocr_text}\"\"\"
JSON:
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        output = model.generate_content(prompt).text.strip()
        json_start = output.find("{")
        json_end = output.rfind("}") + 1
        return json.loads(output[json_start:json_end])
    except Exception:
        return {
            "vendor": "Unknown",
            "product_or_service": "Unknown",
            "price": "Unknown"
        }

# === Main Pipeline Logic ===
async def process_file(file, user_directory: str = DEFAULT_USER_DIRECTORY) -> dict | None:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None

    unique_name = f"{int(time.time())}_{uuid4().hex}{ext}"
    rawdrop_path = f"rawdrop/{user_directory}/{unique_name}"

    blob_raw = container_client.get_blob_client(rawdrop_path)
    file_bytes = await file.read()
    blob_raw.upload_blob(file_bytes, overwrite=True)

    # Skip if already processed
    if was_already_processed(rawdrop_path):
        return None

    # OCR + LLM
    ocr = run_ocr(file_bytes, ext)
    tags = extract_tags(ocr)

    metadata = {
        "user_directory": user_directory,
        "job_id": str(uuid4()),
        "original_blob_name": rawdrop_path,
        "ingested_path": blob_raw.url,
        "original_filename": file.filename,
        "timestamp": time.time(),
        "tags": tags
    }

    return metadata

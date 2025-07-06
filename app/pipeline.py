import os
import re
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

# === Set up clients ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
genai.configure(api_key=GEMINI_KEY)
vision_client = vision.ImageAnnotatorClient()
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]

# === ocr output sanitation ===
def sanitize_ocr(ocr_text: str) -> str:
    lines = ocr_text.splitlines()
    clean_lines = []
    last_line = ""

    skip_keywords = [
        "swish", "kort", "orgnr", "vat", "moms", "kopiakvitto",
        "terminal", "powered", "verifikat", "service", "id",
        "barcode", "total att betala", "vxl", "tack för besöket",
        "betalning", "summa att betala"
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Lowercase filter
        if any(kw in line.lower() for kw in skip_keywords):
            continue

        # Remove barcode-like lines
        if re.fullmatch(r"[0-9]{8,}", line):
            continue

        # Replace Swedish comma decimals with dots
        line = re.sub(r"(\d+),(\d{2})", r"\1.\2", line)

        # Merge broken lines (e.g., product name + price on separate lines)
        if last_line and not any(char.isdigit() for char in line):
            clean_lines[-1] = clean_lines[-1] + " " + line
        else:
            clean_lines.append(line)
            last_line = line

    return "\n".join(clean_lines)

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
def extract_tags(ocr_text: str) -> dict[str, str]:
    santized_text = sanitize_ocr(ocr_text)
    prompt = f"""
You are a strict data extractor. Given a raw receipt text, extract exactly this information:

- "vendor": Store name
- "product_or_service": A comma-separated list of purchased items
- "price": Total paid amount in SEK as a number (float)

Do not guess or invent any information.
Only use what is explicitly visible in the receipt text.
If any field is missing, return "Unknown" or 0.

Return only valid JSON in this format:
{{
  "vendor": "...",
  "product_or_service": "...",
  "price": ...
}}

Here is the receipt text:
\"\"\"{santized_text}\"\"\"
"""


    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        output = model.generate_content(prompt)
        response_text = output.text.strip()

        # Try to extract JSON block from anywhere in the output
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        cleaned_json = response_text[json_start:json_end]

        return json.loads(cleaned_json)

    except Exception as e:
        print(f"[extract_tags error] {e}")
        return {
            "vendor": "Unknown",
            "product_or_service": "Unknown",
            "price": 0.0
        }
    
# === Main Pipeline Logic ===
async def process_file(file, user_id: str, user_directory: str) -> dict | None:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None

    unique_name = f"{int(time.time())}_{uuid4().hex}{ext}"
    rawdrop_path = f"rawdrop/{user_directory}/{unique_name}"

    blob_raw = container_client.get_blob_client(rawdrop_path)
    file_bytes = await file.read()
    blob_raw.upload_blob(file_bytes, overwrite=True)

    if was_already_processed(rawdrop_path):
        return None

    ocr = run_ocr(file_bytes, ext)
    tags = extract_tags(ocr)

    # === Format price ===
    try:
        price = float(tags.get("price", "0"))
    except:
        price = 0.0
    tags["price"] = price

    job_id = str(uuid4())
    metadata = {
        "id": job_id,  # REQUIRED for Cosmos DB!
        "user_id": user_id,
        "user_directory": user_directory,
        "job_id": job_id,
        "original_blob_name": rawdrop_path,
        "ingested_path": blob_raw.url,
        "original_filename": file.filename,
        "timestamp": time.time(),
        "status": "tagged",
        "tags": tags
}


    return metadata

import re
import io
import collections
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pypdf import PdfReader
from PIL import Image
import pytesseract
from firebase_admin import firestore


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
smart_notes_router = APIRouter()


def algorithm_summarize(full_text: str, num_keywords: int = 6, instruction: str = "") -> str:
    full_text = re.sub(r'\s+', ' ', full_text)
    sentences = re.split(r'(?<=[.!?])\s+', full_text.strip())

    cleaned_sentences = []
    for sentence in sentences:
        word_count = len(sentence.split())
        if 5 <= word_count <= 50: 
            cleaned_sentences.append(sentence.strip())

    sentences = cleaned_sentences

    if not sentences:
        return "No readable text discovered in this file. Please verify it contains typed text lines."

    stop_words = {
        'the', 'and', 'a', 'of', 'to', 'is', 'in', 'that',
        'it', 'for', 'on', 'with', 'as', 'this', 'by',
        'an', 'be', 'are', 'was', 'were', 'from', 'or',
        'at', 'which', 'into', 'their', 'they', 'them',
        'these', 'those', 'have', 'has', 'had', 'will',
        'can', 'would', 'could', 'should', 'been', 'being',
        'about', 'than', 'also', 'such', 'through', 'more', 'focus'
    }

    # Extract target focal terms from the user's custom instruction
    instruction_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', instruction.lower()))
    instruction_words = instruction_words.difference(stop_words)

    words = re.findall(r'\b[a-zA-Z]{4,}\b', full_text.lower())
    filtered_words = [word for word in words if word not in stop_words]

    if not filtered_words:
        return "Unable to compile structural summary definitions from the content."

    word_frequencies = collections.Counter(filtered_words)
    
    priority_keywords = [w for w in instruction_words if w in word_frequencies]
    standard_keywords = [word for word, _ in word_frequencies.most_common(num_keywords * 2)]
    
    top_raw_keywords = list(collections.OrderedDict.fromkeys(priority_keywords + standard_keywords))

    markdown_output = "## Core Keyword Definitions & Summaries\n\n"
    if instruction.strip():
        markdown_output += f"> *Applied Summary Filter Instruction: \"{instruction}\"*\n\n"

    used_sentences = set()
    keywords_processed = 0

    for raw_keyword in top_raw_keywords:
        if keywords_processed >= num_keywords:
            break

        best_sentence = None
        max_score = -1

        for sentence in sentences:
            if sentence in used_sentences:
                continue

            lower_sentence = sentence.lower()
            if re.search(r'\b' + re.escape(raw_keyword) + r'\b', lower_sentence):
                score = 0
                
                if any(cue in lower_sentence for cue in ["is a", "refers to", "defined as", "dedicated to", "treatment", "symptoms"]):
                    score += 150
                for user_word in instruction_words:
                    if re.search(r'\b' + re.escape(user_word) + r'\b', lower_sentence):
                        score += 250 

                sentence_words = re.findall(r'\b[a-zA-Z]+\b', lower_sentence)
                score += sum(word_frequencies[w] for w in sentence_words if w in word_frequencies)

                if score > max_score:
                    max_score = score
                    best_sentence = sentence

        if best_sentence:
            used_sentences.add(best_sentence)
            clean_display_sentence = re.sub(r'^\s*[\bullet\•\-\*0-9\.\s]+', '', best_sentence)
            markdown_output += f"- **{raw_keyword.title()}**: {clean_display_sentence}\n\n"
            keywords_processed += 1

    return markdown_output


@smart_notes_router.post("/summarize")
async def summarize_document(
    file: UploadFile = File(...),
    instruction: str = Form("") # Added optional instruction parameter form receiver
):
    filename_lower = file.filename.lower()
    
    pdf_extensions = {'.pdf', '.docs', '.txt'}
    image_extensions = {'.png', '.jpg', '.jpeg', '.jfif'}
    
    allowed_extensions = pdf_extensions.union(image_extensions)
    has_valid_ext = any(filename_lower.endswith(ext) for ext in allowed_extensions)
    
    if not has_valid_ext:
        raise HTTPException(
            status_code=400,
            detail="Unsupported asset extension. Only PDFs and Image files (.png, .jpg, .jpeg, .jfif) are accepted."
        )

    try:
        extracted_text = ""

        if any(filename_lower.endswith(ext) for ext in pdf_extensions):
            pdf_reader = PdfReader(file.file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + " "
        else:
            image_bytes = await file.read()
            image_object = Image.open(io.BytesIO(image_bytes))
            extracted_text = pytesseract.image_to_string(image_object)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="The upload processed successfully but contains no visible extractable textual data."
            )

        # Pass custom user guidance string context safely into calculations
        summary = algorithm_summarize(extracted_text, num_keywords=6, instruction=instruction)

        db = firestore.client()

        note_data = {
            "title": file.filename,
            "summary": summary,
            "custom_instruction": instruction,
            "created_at": datetime.utcnow(),
            "source_type": "pdf_upload" if filename_lower.endswith('.pdf') else "image_upload"
        }

        doc_ref = db.collection("smart_notes").document()
        doc_ref.set(note_data)

        return {
            "status": "success",
            "document_id": doc_ref.id,
            "title": note_data["title"],
            "summary": summary
        }

    except Exception as e:
        print(f"Smart Notes Routing Failure: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Local extraction failure: {str(e)}"
        )
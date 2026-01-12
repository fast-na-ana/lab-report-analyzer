# Medical Lab Report Analyzer (RAG-Enabled)

An AI-powered medical lab report analyzer that parses medical PDFs, extracts patient profiles, normalizes lab tests against a local JSON knowledge base, and provides clinical significance analysis using Groq.

## Features
- **Streamlit Web UI**: User-friendly interface for uploading and analyzing lab reports
- **Multilingual Support**: Full support for English, Urdu (اردو), and Punjabi (پنجابی) languages
- **Voice Input & Output**: Voice-enabled profile entry and audio report narration
- **Smart PDF Parsing**: Extracts PDF content and splits into Profile and Bloodwork chunks using pymupdf4llm
- **AI-Powered Profile Extraction**: Uses Groq (llama-3.3-70b-versatile) to extract patient demographics from reports
- **Semantic Test Normalization**: Maps raw test names (e.g., "HGB") to KB test_ids using Groq
- **Pregnancy-Aware Analysis**: Intelligently handles pregnancy-specific reference ranges with intelligent fallback
- **Gender-Specific Mapping**: Automatically selects appropriate test_ids based on patient gender
- **Intelligent Lookup**: Checks reference ranges with patient stratification (age, gender, pregnancy status)
- **Robust File Handling**: Retry logic for medical_kb.json loading with 3 attempts
- **Clinical Significance Analysis**: Reports abnormal values with clinical context from KB (NO DIAGNOSIS)
- **Local Reference Integration**: Uses Pakistani RI Study (2024) reference ranges with global fallback

## Architecture
```
PDF Upload → Parser (2 chunks) → Profile Extraction (Groq) → Test Normalization (Groq) → Lookup (KB) → Clinical Analysis → Results Display
```

## Requirements
- Python 3.8 or higher
- Groq API key (free tier available at https://console.groq.com/)

## Installation

1. Clone or download this project
2. Navigate to the project directory:
```bash
cd medical-agentic-system
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your Groq API key:
   - Get your API key from [Groq Console](https://console.groq.com/)
   - Create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your-groq-api-key-here
   ```

## Usage

1. Run the Streamlit app:
```bash
streamlit run main.py
```

2. The app will open in your browser. Follow these steps:
   - **Step 1**: Upload a medical lab report PDF
   - **Step 2**: Review and complete patient profile (age, gender, pregnancy status)
   - **Step 3**: Click "Start Analysis" to process lab tests
   - **Step 4**: View detailed analysis results with reference ranges and clinical significance

3. Click "Analyze Another Report" in the sidebar to reset and analyze a new report.

## Project Structure

```
├── main.py              # Streamlit UI orchestrator and state management
├── parser.py            # PDF extraction and 2-chunk strategy (Profile/Bloodwork)
├── normalizer.py        # Groq-based semantic mapping with pregnancy logic
├── lookup.py            # Deterministic retrieval from medical_kb.json
├── decision.py          # Clinical significance analysis (NO DIAGNOSIS)
├── medical_kb.json      # Medical knowledge base with Pakistani RI ranges
├── requirements.txt     # Python dependencies
├── .env                 # API keys (create this file, gitignored)
└── README.md           # This file
```

## Key Features Explained

### Profile Extraction
- Automatically extracts patient name, age, gender, and pregnancy status from PDF
- If any required field (except name) is missing, displays a form for manual entry
- Analysis cannot proceed until profile is 100% complete

### Test Normalization
- Uses Groq to map raw test names to KB test_ids
- Handles gender-specific variants (e.g., "haemoglobin_male" vs "haemoglobin_female")
- Pregnancy-aware: Checks if substance is drastically affected by pregnancy
- Returns errors if pregnancy-specific data is required but unavailable

### Reference Range Lookup
- Prioritizes `pakistan_reference_range` over `global_reference_range`
- Supports age-based stratification (infant, adult, elderly)
- Supports pregnancy trimester-specific ranges (pregnancy_t1, pregnancy_t2, pregnancy_t3)
- Falls back gracefully when specific ranges are unavailable

### Clinical Analysis
- **NO DIAGNOSIS**: Only reports if values are high/low and what KB says
- Includes clinical significance and source citations from KB
- Adds required disclaimer for abnormal values
- Professional formatting with status indicators

## Technologies Used
- **Streamlit**: Web UI framework
- **Groq API**: llama-3.3-70b-versatile for profile extraction and test normalization
- **PyMuPDF4LLM**: Advanced PDF text extraction with medical document settings
- **Python-dotenv**: Secure environment variable management
- **Pydantic**: Data validation (for future enhancements)

## Safety & Disclaimers
- **No Medical Diagnosis**: This tool provides automated analysis based on reference ranges and does NOT diagnose
- **No Treatment Recommendations**: This tool does NOT suggest treatments
- **Consult Healthcare Providers**: All results should be reviewed by qualified medical professionals
- Every abnormal value analysis includes a disclaimer

## Configuration Notes
- Groq API key must be set as `GROQ_API_KEY` environment variable
- The `medical_kb.json` file contains the complete knowledge base - do not modify unless you understand the structure
- All API calls use the `llama-3.3-70b-versatile` model for consistency and speed

## Troubleshooting
- **"GROQ_API_KEY not set"**: Create a `.env` file with your API key
- **"PDF processing error"**: Ensure the PDF is not corrupted and contains readable text
- **"No lab results found"**: The PDF might not contain structured lab tables - check the document format
- **"Test normalization failed"**: The test name might not be recognized - check the KB for available test_ids
"""
Medical Lab Report Analyzer - Streamlit UI Orchestrator
RAG-Enabled with Groq Integration
"""

import streamlit as st
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from parser import extract_pdf_to_chunks
from normalizer import normalize_test, extract_tests_from_bloodwork, get_groq_client
from lookup import lookup_test_info
from decision import analyze_clinical_significance, generate_batch_analysis, generate_clinical_analysis
from voice_utils import speech_to_text, speak_text, play_audio, get_language_code
try:
    from streamlit_mic_recorder import speech_to_text as mic_speech_to_text
    MIC_RECORDER_AVAILABLE = True
except ImportError:
    MIC_RECORDER_AVAILABLE = False


# Page configuration
st.set_page_config(
    page_title="Medical Lab Report Analyzer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if "pdf_uploaded" not in st.session_state:
    st.session_state.pdf_uploaded = False
if "chunks" not in st.session_state:
    st.session_state.chunks = None
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {
        "name": None,
        "age": None,
        "gender": None,
        "is_pregnant": False,
        "trimester": None
    }
if "profile_complete" not in st.session_state:
    st.session_state.profile_complete = False
if "test_results" not in st.session_state:
    st.session_state.test_results = []
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "English"
if "currently_playing_audio" not in st.session_state:
    st.session_state.currently_playing_audio = None
if "voice_profile_field" not in st.session_state:
    st.session_state.voice_profile_field = None
if "voice_transcript" not in st.session_state:
    st.session_state.voice_transcript = None

# Language options for consistent mapping
LANGUAGE_OPTIONS = ["English", "Urdu (اردو)", "Punjabi (پنجابی)"]
LANGUAGE_KEY_MAP = {
    "English": "English",
    "Urdu (اردو)": "Urdu (اردو)",
    "Punjabi (پنجابی)": "Punjabi (پنجابی)"
}

# UI Dictionary for multilingual support
ui_text = {
    "English": {
        "title": "🔬 Medical Lab Report Analyzer",
        "subtitle": "Upload a medical lab report PDF to analyze test results against Pakistani reference ranges.",
        "upload_button": "Choose a PDF file",
        "upload_help": "Upload a medical lab report in PDF format",
        "step1_header": "Step 1: Upload Lab Report PDF",
        "step2_header": "Step 2: Patient Profile Extraction",
        "step3_header": "Step 3: Laboratory Test Analysis",
        "step4_header": "Step 4: Analysis Results"
    },
    "Urdu (اردو)": {
        "title": "🔬 میڈیکل لیب رپورٹ تجزیہ کار",
        "subtitle": "پاکستانی حوالہ حدود کے خلاف ٹیسٹ کے نتائج کا تجزیہ کرنے کے لیے میڈیکل لیب رپورٹ PDF اپ لوڈ کریں۔",
        "upload_button": "PDF فائل منتخب کریں",
        "upload_help": "PDF فارمیٹ میں میڈیکل لیب رپورٹ اپ لوڈ کریں",
        "step1_header": "مرحلہ 1: لیب رپورٹ PDF اپ لوڈ کریں",
        "step2_header": "مرحلہ 2: مریض پروفائل نکالنا",
        "step3_header": "مرحلہ 3: لیبارٹری ٹیسٹ کا تجزیہ",
        "step4_header": "مرحلہ 4: تجزیہ کے نتائج"
    },
    "Punjabi (پنجابی)": {
        "title": "🔬 میڈیکل لیب رپورٹ تجزیہ کار",
        "subtitle": "پاکستانی حوالہ حدود دے خلاف ٹیسٹ دے نتائج دا تجزیہ کرن لئی میڈیکل لیب رپورٹ PDF اپ لوڈ کرو۔",
        "upload_button": "PDF فائل چنو",
        "upload_help": "PDF فارمیٹ وچ میڈیکل لیب رپورٹ اپ لوڈ کرو",
        "step1_header": "مرحلہ 1: لیب رپورٹ PDF اپ لوڈ کرو",
        "step2_header": "مرحلہ 2: مریض پروفائل کڈھنا",
        "step3_header": "مرحلہ 3: لیبارٹری ٹیسٹ دا تجزیہ",
        "step4_header": "مرحلہ 4: تجزیہ دے نتائج"
    }
}


def get_ui_text(language: str = None) -> Dict:
    """
    Safely get UI text for the selected language.
    
    Args:
        language: Language string, defaults to session state
        
    Returns:
        dict: UI text dictionary for the selected language
    """
    if language is None:
        language = st.session_state.get("selected_language", "English")
    
    # Ensure language is valid, fallback to English
    if language not in ui_text:
        language = "English"
        st.session_state.selected_language = "English"
    
    return ui_text[language]


def get_language_index(language: str) -> int:
    """
    Get the index of a language in LANGUAGE_OPTIONS.
    
    Args:
        language: Language string
        
    Returns:
        int: Index in LANGUAGE_OPTIONS, defaults to 0 (English)
    """
    try:
        return LANGUAGE_OPTIONS.index(language)
    except (ValueError, AttributeError):
        return 0


def reset_session():
    """Reset all session state variables."""
    st.session_state.pdf_uploaded = False
    st.session_state.chunks = None
    st.session_state.user_profile = {
        "name": None,
        "age": None,
        "gender": None,
        "is_pregnant": False,
        "trimester": None
    }
    st.session_state.profile_complete = False
    st.session_state.test_results = []
    st.session_state.analysis_complete = False


def extract_profile_from_chunk(profile_chunk: str) -> Dict:
    """
    Extract user profile from Chunk 1 using Groq (llama-3.3-70b-versatile).
    
    Returns:
        dict: {"name": str, "age": int, "gender": "male"|"female", 
               "is_pregnant": bool, "trimester": 1|2|3|null}
    """
    try:
        client = get_groq_client()
    except ValueError as e:
        st.error(f"Configuration error: {e}")
        return {
            "name": None,
            "age": None,
            "gender": None,
            "is_pregnant": False,
            "trimester": None
        }
    
    prompt = f"""
Extract patient profile information from the following medical report text.
Return ONLY a valid JSON object with these exact fields:
- "name": string or null (patient name if available)
- "age": integer or null (patient age in years)
- "gender": "male" or "female" or null
- "is_pregnant": boolean (true if pregnant, false otherwise)
- "trimester": integer 1, 2, or 3 if pregnant, or null if not pregnant

If any information is not found in the text, use null for that field.

Medical report text:
{profile_chunk[:2000]}

Return ONLY the JSON object, no other text:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        # Extract JSON if wrapped in code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        profile = json.loads(content)
        
        # Validate and normalize
        return {
            "name": profile.get("name"),
            "age": profile.get("age"),
            "gender": profile.get("gender", "").lower() if profile.get("gender") else None,
            "is_pregnant": profile.get("is_pregnant", False),
            "trimester": profile.get("trimester")
        }
        
    except Exception as e:
        error_msg = str(e)
        if "GROQ_API_KEY" in error_msg or "api_key" in error_msg.lower():
            st.error("❌ Groq API key not configured. Please set GROQ_API_KEY environment variable.")
        else:
            st.error(f"Error extracting profile: {error_msg}")
        return {
            "name": None,
            "age": None,
            "gender": None,
            "is_pregnant": False,
            "trimester": None
        }


def check_profile_complete(profile: Dict) -> bool:
    """Check if profile has all required fields (except name)."""
    return (
        profile.get("age") is not None and
        profile.get("gender") in ["male", "female"] and
        (not profile.get("is_pregnant") or profile.get("trimester") in [1, 2, 3])
    )


def process_voice_transcript_for_profile(transcript: str, field_name: str, language: str) -> Optional[str]:
    """
    Process voice transcript using LLM to extract profile field value.
    
    Args:
        transcript: Voice transcript text
        field_name: Field to extract ("age", "gender", "name")
        language: Selected language
        
    Returns:
        str or None: Extracted value or None
    """
    try:
        client = get_groq_client()
        
        prompt = f"""
Extract the {field_name} value from the following voice transcript.
Return ONLY the extracted value, nothing else.

Field to extract: {field_name}
Transcript: "{transcript}"

Rules:
- If field_name is "age": Return ONLY a number (e.g., "25", "30")
- If field_name is "gender": Return ONLY "male" or "female"
- If field_name is "name": Return the name as a string
- If no value can be extracted, return "null"

Extracted value:"""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=50
        )
        
        extracted = response.choices[0].message.content.strip().strip('"').strip("'")
        
        if extracted.lower() == "null" or not extracted:
            return None
        
        # Special handling for age
        if field_name == "age":
            try:
                age_num = int(extracted)
                if 0 <= age_num <= 150:
                    return str(age_num)
            except:
                pass
        
        # Special handling for gender
        if field_name == "gender":
            extracted_lower = extracted.lower()
            if "male" in extracted_lower or "مرد" in extracted_lower or "ਨਰ" in extracted_lower:
                return "male"
            elif "female" in extracted_lower or "عورت" in extracted_lower or "ਮਹਿਲਾ" in extracted_lower:
                return "female"
        
        return extracted
        
    except Exception as e:
        st.error(f"Error processing voice transcript: {e}")
        return None


def main():
    """Main Streamlit app."""
    
    # Sidebar for "Analyze Another" button and settings
    with st.sidebar:
        if st.button("🔄 Analyze Another Report", use_container_width=True, key="analyze_another_btn"):
            reset_session()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Settings")
        
        # Language Selector - use selectbox for stable, reliable behavior
        # Get current language from session state with validation
        current_lang = st.session_state.get("selected_language", "English")
        if current_lang not in LANGUAGE_OPTIONS:
            current_lang = "English"
            st.session_state.selected_language = "English"
        
        # Get the correct index for the current language
        current_index = get_language_index(current_lang)
        
        # Language selector - selectbox provides stable state management
        # Streamlit automatically stores the value in st.session_state.language_selector
        # and triggers a rerun when the selection changes
        selected_language = st.selectbox(
            "Select Language / زبان منتخب کریں",
            options=LANGUAGE_OPTIONS,
            index=current_index,
            key="language_selector"
        )
        
        # Sync selectbox value to our session state variable
        # This ensures consistency - use the return value which matches the key state
        st.session_state.selected_language = selected_language
        
        st.markdown("---")
        
        # Check for Groq API key
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            st.error("⚠️ GROQ_API_KEY not set in environment variables")
            st.info("Please set your Groq API key as an environment variable.")
        else:
            st.success("✅ Groq API key configured")
    
    # Get UI text based on selected language (after sidebar to ensure language is updated)
    current_ui = get_ui_text()
    
    # Inject CSS to hide audio players and style voice features
    st.markdown("""
    <style>
    /* Hide audio player controls - buttons will trigger playback */
    .stAudio {
        display: none !important;
    }
    /* Style voice buttons */
    .voice-button {
        margin-top: 0.5rem;
    }
    /* Status indicator styling */
    .voice-status {
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title(current_ui["title"])
    st.markdown(current_ui["subtitle"])
    st.divider()
    
    # Step 1: PDF Upload
    if not st.session_state.pdf_uploaded:
        st.header(current_ui["step1_header"])
        uploaded_file = st.file_uploader(
            current_ui["upload_button"],
            type=["pdf"],
            help=current_ui["upload_help"],
            key="pdf_uploader"
        )
        
        if uploaded_file is not None:
            try:
                # DIRECTIVE 5: Clear previous analysis data when new file is uploaded
                # Reset all session state variables to prevent "ghost" data from old report
                st.session_state.test_results = []
                st.session_state.analysis_complete = False
                st.session_state.profile_complete = False
                st.session_state.user_profile = {
                    "name": None,
                    "age": None,
                    "gender": None,
                    "is_pregnant": False,
                    "trimester": None
                }
                st.session_state.chunks = None
                
                with st.spinner("Extracting PDF content..."):
                    tmp_path = None
                    try:
                        # Save uploaded file temporarily
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        
                        # Extract and chunk PDF (file handle is closed after this)
                        chunks = extract_pdf_to_chunks(tmp_path)
                        st.session_state.chunks = chunks
                        st.session_state.pdf_uploaded = True
                        
                    finally:
                        # Clean up temp file (with retry for Windows file locks)
                        if tmp_path and os.path.exists(tmp_path):
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    os.unlink(tmp_path)
                                    break  # Successfully deleted
                                except (OSError, PermissionError) as cleanup_error:
                                    if attempt < max_retries - 1:
                                        # Wait a bit before retrying (Windows file handle release delay)
                                        time.sleep(0.1)
                                    else:
                                        # Final attempt failed - file might still be locked
                                        # This is acceptable on Windows - temp files will be cleaned up by OS
                                        pass
                    
                st.success("✅ PDF processed successfully!")
                st.rerun()
                
            except RuntimeError as e:
                error_msg = str(e)
                if "re.error" in error_msg or "regex" in error_msg.lower() or "unterminated" in error_msg.lower():
                    st.error("⚠️ **Regex parsing error detected**")
                    st.error(f"Error details: {error_msg}")
                    st.warning("""
                    **Possible causes:**
                    - The PDF contains special characters that broke the parsing engine
                    - The PDF structure is unusual or corrupted
                    - The PDF extraction library encountered an issue
                    
                    **Suggested fixes:**
                    - Try converting the PDF to a different format and back to PDF
                    - Use a different PDF file if available
                    - Ensure the PDF is not password-protected or encrypted
                    """)
                else:
                    st.error(f"Error processing PDF: {error_msg}")
                    st.info("Please ensure the PDF is not corrupted and try again.")
            except Exception as e:
                error_msg = str(e)
                st.error(f"Error processing PDF: {error_msg}")
                if "re.error" in error_msg or "regex" in error_msg.lower():
                    st.warning("A regex parsing error occurred. This may be due to special characters in the PDF.")
                st.info("Please ensure the PDF is not corrupted and try again.")
    
    # Step 2: Profile Extraction
    elif st.session_state.chunks and not st.session_state.profile_complete:
        st.header(current_ui["step2_header"])
        
        with st.spinner("Extracting patient profile from report..."):
            profile_chunk = st.session_state.chunks.get("profile", "")
            extracted_profile = extract_profile_from_chunk(profile_chunk)
            st.session_state.user_profile.update(extracted_profile)
        
        # Check if profile is complete
        if check_profile_complete(st.session_state.user_profile):
            st.session_state.profile_complete = True
            st.success("✅ Profile extracted successfully!")
            st.rerun()
        else:
            # Display extracted profile and form for missing data
            st.subheader("Review and Complete Patient Profile")
            st.info("Please complete the missing profile information to proceed with analysis.")
            
            # Check for missing fields and add voice input prompts
            profile = st.session_state.user_profile
            missing_fields = []
            if not profile.get("name"):
                missing_fields.append("name")
            if not profile.get("age"):
                missing_fields.append("age")
            if not profile.get("gender"):
                missing_fields.append("gender")
            
            # Show voice input prompts for missing fields
            if missing_fields:
                for field in missing_fields:
                    if field == "age":
                        st.info(f"🎤 **Voice Input Available**: I noticed your age is missing. Please use the microphone button next to the Age field to speak your age.")
                    elif field == "gender":
                        st.info(f"🎤 **Voice Input Available**: I noticed your gender is missing. Please use the microphone button next to the Gender field to speak your gender (male or female).")
                    elif field == "name":
                        st.info(f"🎤 **Voice Input Available**: Name is optional, but you can use the microphone button to speak your name if you'd like.")
            
            with st.form("profile_form"):
                selected_lang = st.session_state.selected_language
                lang_code = get_language_code(selected_lang, "speech_to_text")
                
                # Name field with voice input
                name_col1, name_col2 = st.columns([4, 1])
                with name_col1:
                    name = st.text_input(
                        "Patient Name (Optional)",
                        value=st.session_state.user_profile.get("name") or "",
                        help="Patient name is optional",
                        key="profile_name_input"
                    )
                with name_col2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Align with input
                    if MIC_RECORDER_AVAILABLE:
                        name_audio = mic_speech_to_text(
                            start_prompt="🎤",
                            stop_prompt="🛑",
                            language=lang_code,
                            key="name_voice_input"
                        )
                        if name_audio:
                            with st.spinner("Processing voice input..."):
                                transcript = speech_to_text(name_audio, selected_lang)
                                if transcript:
                                    extracted_name = process_voice_transcript_for_profile(transcript, "name", selected_lang)
                                    if extracted_name:
                                        name = extracted_name
                                        st.session_state.user_profile["name"] = extracted_name
                                        st.toast(f"✅ Name set to: {extracted_name}", icon="✅")
                    else:
                        st.markdown("🎤", help="Voice input requires streamlit-mic-recorder package")
                
                # Age field with voice input
                age_col1, age_col2 = st.columns([4, 1])
                with age_col1:
                    age = st.number_input(
                        "Age *",
                        min_value=0,
                        max_value=150,
                        value=st.session_state.user_profile.get("age") or 0,
                        help="Patient age in years (required)",
                        key="profile_age_input"
                    )
                with age_col2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Align with input
                    if MIC_RECORDER_AVAILABLE:
                        age_audio = mic_speech_to_text(
                            start_prompt="🎤",
                            stop_prompt="🛑",
                            language=lang_code,
                            key="age_voice_input"
                        )
                        if age_audio:
                            with st.spinner("Processing voice input..."):
                                transcript = speech_to_text(age_audio, selected_lang)
                                if transcript:
                                    extracted_age = process_voice_transcript_for_profile(transcript, "age", selected_lang)
                                    if extracted_age:
                                        try:
                                            age = int(extracted_age)
                                            st.session_state.user_profile["age"] = age
                                            st.toast(f"✅ Age set to: {age}", icon="✅")
                                            st.rerun()
                                        except:
                                            st.error(f"Could not parse age: {extracted_age}")
                    else:
                        st.markdown("🎤", help="Voice input requires streamlit-mic-recorder package")
                
                # Gender field with voice input
                gender_col1, gender_col2 = st.columns([4, 1])
                with gender_col1:
                    gender = st.selectbox(
                        "Gender *",
                        options=["", "male", "female"],
                        index=0 if not st.session_state.user_profile.get("gender") 
                        else (1 if st.session_state.user_profile.get("gender") == "male" else 2),
                        help="Patient gender (required)",
                        key="profile_gender_input"
                    )
                with gender_col2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Align with selectbox
                    if MIC_RECORDER_AVAILABLE:
                        gender_audio = mic_speech_to_text(
                            start_prompt="🎤",
                            stop_prompt="🛑",
                            language=lang_code,
                            key="gender_voice_input"
                        )
                        if gender_audio:
                            with st.spinner("Processing voice input..."):
                                transcript = speech_to_text(gender_audio, selected_lang)
                                if transcript:
                                    extracted_gender = process_voice_transcript_for_profile(transcript, "gender", selected_lang)
                                    if extracted_gender and extracted_gender in ["male", "female"]:
                                        gender = extracted_gender
                                        st.session_state.user_profile["gender"] = extracted_gender
                                        st.toast(f"✅ Gender set to: {extracted_gender}", icon="✅")
                                        st.rerun()
                    else:
                        st.markdown("🎤", help="Voice input requires streamlit-mic-recorder package")
                
                # Pregnancy fields (no voice input needed)
                is_pregnant = st.checkbox(
                    "Pregnant",
                    value=st.session_state.user_profile.get("is_pregnant", False),
                    help="Check if patient is pregnant",
                    key="profile_pregnant_input"
                )
                trimester = None
                if is_pregnant:
                    trimester = st.selectbox(
                        "Trimester *",
                        options=[None, 1, 2, 3],
                        index=0 if not st.session_state.user_profile.get("trimester")
                        else st.session_state.user_profile.get("trimester"),
                        help="Pregnancy trimester (required if pregnant)",
                        key="profile_trimester_input"
                    )
                
                submitted = st.form_submit_button("Continue to Analysis", use_container_width=True)
                
                if submitted:
                    # Validate form
                    if age <= 0:
                        st.error("Please enter a valid age.")
                    elif not gender:
                        st.error("Please select a gender.")
                    elif is_pregnant and trimester is None:
                        st.error("Please select a trimester if patient is pregnant.")
                    else:
                        # Update profile
                        st.session_state.user_profile = {
                            "name": name if name else None,
                            "age": int(age),
                            "gender": gender,
                            "is_pregnant": is_pregnant,
                            "trimester": trimester if is_pregnant else None
                        }
                        st.session_state.profile_complete = True
                        st.rerun()
    
    # Step 3: Lab Analysis
    elif st.session_state.profile_complete and not st.session_state.analysis_complete:
        st.header(current_ui["step3_header"])
        
        # Display profile summary
        with st.expander("📋 Patient Profile Summary", expanded=False):
            profile = st.session_state.user_profile
            st.write(f"**Name**: {profile.get('name') or 'Not provided'}")
            st.write(f"**Age**: {profile.get('age')} years")
            st.write(f"**Gender**: {profile.get('gender').title()}")
            if profile.get('is_pregnant'):
                st.write(f"**Pregnancy Status**: Pregnant, Trimester {profile.get('trimester')}")
            else:
                st.write("**Pregnancy Status**: Not pregnant")
        
        if st.button("🚀 Start Analysis", use_container_width=True, key="start_analysis_btn"):
            bloodwork_chunk = st.session_state.chunks.get("bloodwork", "")
            
            if not bloodwork_chunk or "No lab results" in bloodwork_chunk:
                st.error("No lab results found in the PDF. Please check the document.")
            else:
                # Extract tests from bloodwork
                try:
                    with st.spinner("Extracting lab tests from report..."):
                        raw_tests = extract_tests_from_bloodwork(bloodwork_chunk)
                except (FileNotFoundError, IOError) as e:
                    error_msg = str(e)
                    if "medical_kb.json" in error_msg:
                        st.error(f"❌ **Medical Knowledge Base Error**")
                        st.error(f"Error: {error_msg}")
                        st.error("The medical_kb.json file is missing, locked, or unreadable after 3 retry attempts.")
                        st.info("Please ensure medical_kb.json exists in the project directory and is not locked by another process.")
                        st.stop()
                    else:
                        st.error(f"File error: {error_msg}")
                        st.stop()
                except ValueError as e:
                    st.error(f"Configuration error: {e}")
                    st.stop()
                except Exception as e:
                    st.error(f"Error extracting tests from report: {e}")
                    st.info("Please ensure the PDF contains readable lab test results.")
                    st.stop()
                
                if not raw_tests:
                    st.warning("No lab tests could be extracted from the report.")
                else:
                    st.info(f"Found {len(raw_tests)} test(s). Processing...")
                    
                    # Process each test
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    test_results = []
                    
                    for idx, test in enumerate(raw_tests):
                        raw_name = test.get("raw_name", "")
                        value = test.get("value")
                        
                        if not raw_name or value is None:
                            continue
                        
                        status_text.text(f"Processing: {raw_name} = {value}")
                        
                        # Normalize test
                        try:
                            norm_result = normalize_test(raw_name, st.session_state.user_profile)
                        except (FileNotFoundError, IOError) as e:
                            error_msg = str(e)
                            if "medical_kb.json" in error_msg:
                                test_results.append({
                                    "raw_name": raw_name,
                                    "test_id": None,
                                    "test_info": None,
                                    "error": f"Medical Knowledge Base Error: {error_msg}. The medical_kb.json file is missing, locked, or unreadable.",
                                    "warning": None
                                })
                            else:
                                test_results.append({
                                    "raw_name": raw_name,
                                    "test_id": None,
                                    "test_info": None,
                                    "error": f"File error during normalization: {error_msg}",
                                    "warning": None
                                })
                            progress_bar.progress((idx + 1) / len(raw_tests))
                            continue
                        except Exception as e:
                            test_results.append({
                                "raw_name": raw_name,
                                "test_id": None,
                                "test_info": None,
                                "error": f"Error during normalization: {str(e)}",
                                "warning": None
                            })
                            progress_bar.progress((idx + 1) / len(raw_tests))
                            continue
                        
                        if norm_result["status"] == "success":
                            test_id = norm_result["test_id"]
                            
                            # Lookup reference range and check status
                            try:
                                profile = st.session_state.user_profile
                                test_info = lookup_test_info(
                                    test_id=test_id,
                                    found_value=float(value),
                                    age=profile["age"],
                                    gender=profile["gender"],
                                    trimester=profile.get("trimester")
                                )
                            except (FileNotFoundError, IOError) as e:
                                error_msg = str(e)
                                if "medical_kb.json" in error_msg:
                                    test_results.append({
                                        "raw_name": raw_name,
                                        "test_id": test_id,
                                        "test_info": None,
                                        "error": f"Medical Knowledge Base Error: {error_msg}. The medical_kb.json file is missing, locked, or unreadable after 3 retry attempts.",
                                        "warning": norm_result.get("warning")
                                    })
                                else:
                                    test_results.append({
                                        "raw_name": raw_name,
                                        "test_id": test_id,
                                        "test_info": None,
                                        "error": f"File error during lookup: {error_msg}",
                                        "warning": norm_result.get("warning")
                                    })
                                progress_bar.progress((idx + 1) / len(raw_tests))
                                continue
                            
                            test_results.append({
                                "raw_name": raw_name,
                                "test_id": test_id,
                                "test_info": test_info,
                                "warning": norm_result.get("warning")
                            })
                        elif norm_result["status"] == "error":
                            # Store error for display
                            test_results.append({
                                "raw_name": raw_name,
                                "test_id": None,
                                "test_info": None,
                                "error": norm_result.get("message"),
                                "warning": norm_result.get("warning")
                            })
                        
                        progress_bar.progress((idx + 1) / len(raw_tests))
                    
                    st.session_state.test_results = test_results
                    st.session_state.analysis_complete = True
                    status_text.empty()
                    progress_bar.empty()
                    st.rerun()
    
    # Step 4: Results Display
    elif st.session_state.analysis_complete:
        st.header(current_ui["step4_header"])
        
        if not st.session_state.test_results:
            st.warning("No test results to display.")
        else:
            # MASTER REPORT READ-OUT BUTTON - At the top of results section
            st.markdown("<br>", unsafe_allow_html=True)
            master_read_col1, master_read_col2 = st.columns([1, 4])
            with master_read_col1:
                if st.button("🔊 Read Entire Report Summary", use_container_width=True, key="master_report_read"):
                    with st.spinner("🔊 Generating audio summary..."):
                        # Combine all test analyses into master summary
                        summary_parts = []
                        red_flags = []
                        overall_assessment = []
                        
                        for result in st.session_state.test_results:
                            if result.get("test_info"):
                                test_info = result["test_info"]
                                test_name = test_info.get("display_name", result.get("raw_name"))
                                status = test_info.get("status", "unknown")
                                value = test_info.get("found_value")
                                units = test_info.get("units", "")
                                
                                # Generate analysis text for this test
                                analysis_text = generate_clinical_analysis(test_info, st.session_state.selected_language)
                                
                                # Extract plain text from markdown (remove markdown formatting)
                                import re
                                plain_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', analysis_text)
                                plain_text = re.sub(r'\*([^*]+)\*', r'\1', plain_text)
                                plain_text = re.sub(r'#+\s*', '', plain_text)
                                
                                overall_assessment.append(f"{test_name}: {value} {units} - {plain_text[:200]}")
                                
                                if status in ["low", "high"]:
                                    red_flags.append(f"{test_name} is {status} at {value} {units}")
                        
                        # Build complete summary
                        if red_flags:
                            summary_parts.append("Red Flags: " + ". ".join(red_flags))
                        
                        summary_parts.append("Overall Assessment: " + ". ".join(overall_assessment[:10]))  # Limit to first 10 for audio length
                        
                        full_summary = ". ".join(summary_parts)
                        
                        # Generate and play audio
                        audio_path = speak_text(full_summary, st.session_state.selected_language, slow=False)
                        if audio_path:
                            st.session_state.currently_playing_audio = "master_report"
                            play_audio(audio_path)
                            st.toast("🔊 Playing report summary...", icon="🔊")
                        else:
                            st.error("Failed to generate audio. Please try again.")
            
            # Display results in a table format
            results_data = []
            
            for result in st.session_state.test_results:
                if result.get("error"):
                    results_data.append({
                        "Test Name": result.get("raw_name"),
                        "Status": "❌ Error",
                        "Value": "N/A",
                        "Reference Range": "N/A",
                        "Analysis": result.get("error")
                    })
                elif result.get("test_info"):
                    test_info = result["test_info"]
                    status_icon = "✅" if test_info["status"] == "normal" else "⚠️"
                    
                    range_str = "N/A"
                    if test_info["min_value"] is not None and test_info["max_value"] is not None:
                        range_str = f"{test_info['min_value']} - {test_info['max_value']} {test_info['units']}"
                    
                    results_data.append({
                        "Test Name": test_info.get("display_name", result.get("raw_name")),
                        "Status": f"{status_icon} {test_info['status'].title()}",
                        "Value": f"{test_info['found_value']} {test_info['units']}",
                        "Reference Range": range_str,
                        "Analysis": "See details below"
                    })
            
            # Display summary table
            if results_data:
                st.subheader("📊 Results Summary")
                st.dataframe(results_data, use_container_width=True, hide_index=True)
            
            # Display detailed analysis
            st.subheader("📋 Detailed Analysis")
            
            for idx, result in enumerate(st.session_state.test_results, 1):
                test_name = result.get('raw_name', 'Unknown')
                test_key = test_name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "").lower()
                
                # Create expander with test name and voice button inside
                with st.expander(f"Test {idx}: {test_name} 🔊", expanded=True):
                    # Voice button and content in same expander
                    if result.get("test_info"):
                        voice_col1, voice_col2 = st.columns([10, 1])
                        with voice_col2:
                            if st.button("🔊", key=f"speak_{test_key}", help=f"Listen to {test_name} explanation"):
                                with st.spinner("🔊 Generating audio..."):
                                    test_info = result["test_info"]
                                    # Generate clinical analysis in selected language
                                    analysis_text = generate_clinical_analysis(test_info, st.session_state.selected_language)
                                    
                                    # Extract plain text from markdown (remove markdown formatting for cleaner audio)
                                    import re
                                    plain_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', analysis_text)
                                    plain_text = re.sub(r'\*([^*]+)\*', r'\1', plain_text)
                                    plain_text = re.sub(r'#+\s*', '', plain_text)
                                    plain_text = re.sub(r'\n+', '. ', plain_text)
                                    
                                    # Generate and play audio
                                    audio_path = speak_text(plain_text, st.session_state.selected_language, slow=False)
                                    if audio_path:
                                        st.session_state.currently_playing_audio = test_key
                                        play_audio(audio_path)
                                        st.toast(f"🔊 Playing {test_name} explanation...", icon="🔊")
                                    else:
                                        st.error("Failed to generate audio. Please try again.")
                        
                    if result.get("error"):
                        st.error(result["error"])
                        if result.get("warning"):
                            st.warning(result["warning"])
                    elif result.get("test_info"):
                        test_info = result["test_info"]
                        
                        # Display fallback message if applicable (MANDATORY OUTPUT FLAG)
                        if test_info.get("is_fallback") and test_info.get("fallback_message"):
                            st.info(f"📌 {test_info['fallback_message']}")
                        
                        # Generate clinical analysis in selected language
                        analysis_text = generate_clinical_analysis(test_info, st.session_state.selected_language)
                        st.markdown(analysis_text)
                        
                        if result.get("warning"):
                            st.warning(result["warning"])
            
            # Final disclaimer
            st.divider()
            st.info("""
            **Important**: This analysis is based on automated extraction and comparison against reference ranges 
            from the Pakistani Reference Interval Study (2024). All interpretations are for informational purposes only 
            and do not constitute medical diagnosis, treatment recommendation, or professional medical advice. 
            Please consult with a qualified healthcare provider for proper medical evaluation.
            """)


if __name__ == "__main__":
    main()

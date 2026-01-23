"""
Ultra-Modern Medical Lab Report Analyzer (Streamlit)
Visual overhaul with glassmorphism while preserving core logic.
"""

import os
import json
import time
import tempfile
from typing import Dict, Optional, List

import streamlit as st
from dotenv import load_dotenv

from parser import extract_pdf_to_chunks
from normalizer import normalize_test, extract_tests_from_bloodwork, get_groq_client
from lookup import lookup_test_info
from decision import analyze_clinical_significance, generate_clinical_analysis
from voice_utils import speech_to_text, speak_text, play_audio, get_language_code

try:
    from streamlit_mic_recorder import speech_to_text as mic_speech_to_text
    MIC_RECORDER_AVAILABLE = True
except ImportError:
    MIC_RECORDER_AVAILABLE = False

# --- Load environment ---
load_dotenv()

# --- Page meta ---
st.set_page_config(
    page_title="🔬 Lab Analyzer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Global Styles ---
def local_css(theme: str = "light"):
    # "Serene Pulse" theme tokens
    if theme == "dark":
        base_bg = "#0F172A"
        bg_layer = """
          radial-gradient(120% 120% at 50% 40%, rgba(30,41,59,0.35) 0, transparent 45%),
          radial-gradient(140% 140% at 50% 60%, rgba(2,6,23,0.8) 0, transparent 55%),
          #0F172A
        """
        mesh_a = "rgba(45,212,191,0.18)"
        mesh_b = "rgba(56,189,248,0.14)"
        mesh_c = "rgba(244,63,94,0.10)"
        glass_bg = "var(--glass-bg-dark)"
        glass_border = "var(--glass-border-dark)"
        glass_shadow = "var(--glass-shadow-dark)"
        text_main = "var(--text-main-dark)"
        text_muted = "#94A3B8"
        heading_gradient = "linear-gradient(90deg, #2DD4BF, #38BDF8)"
    else:
        base_bg = "#F0F4F8"
        bg_layer = """
          radial-gradient(120% 140% at 0% 0%, #E0F2FE 0, transparent 45%),
          radial-gradient(140% 120% at 100% 100%, #F0FDFA 0, transparent 45%),
          #F0F4F8
        """
        mesh_a = "rgba(224,242,254,0.65)"
        mesh_b = "rgba(240,253,250,0.65)"
        mesh_c = "rgba(14,165,233,0.10)"
        glass_bg = "var(--glass-bg-light)"
        glass_border = "var(--glass-border-light)"
        glass_shadow = "var(--glass-shadow-light)"
        text_main = "var(--text-main-light)"
        text_muted = "#64748B"
        heading_gradient = "linear-gradient(90deg, #0F766E, #0284C7)"

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@600;700&display=swap');

        :root {
            /* Core gradients */
            --primary-gradient: linear-gradient(135deg, #0EA5E9 0%, #06B6D4 100%);
            /* Glass tokens */
            --glass-bg-light: rgba(255, 255, 255, 0.65);
            --glass-border-light: 1px solid rgba(255, 255, 255, 0.9);
            --glass-shadow-light: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
            --text-main-light: #1E293B;

            --glass-bg-dark: rgba(30, 41, 59, 0.70);
            --glass-border-dark: 1px solid rgba(255, 255, 255, 0.08);
            --glass-shadow-dark: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            --text-main-dark: #F1F5F9;

            /* Semantic colors */
            --status-normal: #10B981;
            --status-warning: #F59E0B;
            --status-critical: #F43F5E;
            --status-normal-glass: rgba(16, 185, 129, 0.15);
            --status-warning-glass: rgba(245, 158, 11, 0.15);
            --status-critical-glass: rgba(244, 63, 94, 0.15);
        }

        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
            color: """ + text_main + """;
            background: """ + bg_layer + """;
        }
        footer, .stDeployButton {visibility: hidden;}

        h1, h2, h3, h4 {
            font-family: 'Poppins', sans-serif;
            background: """ + heading_gradient + """;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .glass-card {
            background: """ + glass_bg + """;
            border-radius: 20px;
            padding: 1.75rem;
            box-shadow: """ + glass_shadow + """;
            backdrop-filter: blur(14px);
            border: """ + glass_border + """;
            animation: fadeIn 0.5s ease;
        }

        .mesh-bg {
            background: radial-gradient(circle at 10% 20%, """ + mesh_a + """ 0, transparent 25%),
                        radial-gradient(circle at 90% 10%, """ + mesh_b + """ 0, transparent 20%),
                        radial-gradient(circle at 30% 80%, """ + mesh_c + """ 0, transparent 30%);
            padding: 0.5rem 0;
        }

        .stButton>button {
            background: var(--primary-gradient);
            color: #fff;
            border: none;
            padding: 0.75rem 1.25rem;
            border-radius: 999px;
            font-weight: 600;
            box-shadow: 0 12px 25px rgba(6,182,212,0.25);
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.01);
            box-shadow: 0 16px 32px rgba(15,118,110,0.25);
        }

        .stFileUploader>div>div {
            border: 2px dashed rgba(6,182,212,0.6) !important;
            border-radius: 16px;
            background: rgba(255,255,255,0.85);
        }

        .progress-steps {
            display: flex;
            gap: 0.75rem;
            margin: 1.25rem 0;
            flex-wrap: wrap;
        }
        .step-pill {
            padding: 0.6rem 0.95rem;
            border-radius: 999px;
            background: rgba(14,165,233,0.10);
            color: """ + text_main + """;
            border: 1px solid rgba(14,165,233,0.2);
            font-weight: 600;
        }
        .step-pill.active {
            background: var(--primary-gradient);
            color: #fff;
            box-shadow: 0 10px 24px rgba(6,182,212,0.25);
        }

        .result-card {
            border-left: 6px solid var(--primary-gradient);
            border-radius: 18px;
            padding: 1rem 1.25rem;
            background: """ + glass_bg + """;
            box-shadow: """ + glass_shadow + """;
            margin-bottom: 1rem;
        }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            background: rgba(6,182,212,0.12);
            color: #0F766E;
            border: 1px solid rgba(6,182,212,0.25);
        }
        .badge.warn {
            background: rgba(244,63,94,0.12);
            color: #b91c1c;
            border-color: rgba(244,63,94,0.25);
        }

        .stExpander {
            border: 1px solid rgba(0,0,0,0.05);
            border-radius: 12px !important;
            background: rgba(255,255,255,0.85);
            box-shadow: var(--glass-shadow);
        }

        @keyframes fadeIn {
            from {opacity: 0; transform: translateY(6px);}
            to {opacity: 1; transform: translateY(0);}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# --- Helpers copied from original main flow (logic preserved) ---
def extract_profile_from_chunk(profile_chunk: str) -> Dict:
    try:
        client = get_groq_client()
    except ValueError as e:
        st.error(f"Configuration error: {e}")
        return {"name": None, "age": None, "gender": None, "is_pregnant": False, "trimester": None}

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
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        profile = json.loads(content)
        return {
            "name": profile.get("name"),
            "age": profile.get("age"),
            "gender": profile.get("gender", "").lower() if profile.get("gender") else None,
            "is_pregnant": profile.get("is_pregnant", False),
            "trimester": profile.get("trimester"),
        }
    except Exception as e:
        error_msg = str(e)
        if "GROQ_API_KEY" in error_msg or "api_key" in error_msg.lower():
            st.error("❌ Groq API key not configured. Please set GROQ_API_KEY environment variable.")
        else:
            st.error(f"Error extracting profile: {error_msg}")
        return {"name": None, "age": None, "gender": None, "is_pregnant": False, "trimester": None}


def check_profile_complete(profile: Dict) -> bool:
    return (
        profile.get("age") is not None
        and profile.get("gender") in ["male", "female"]
        and (not profile.get("is_pregnant") or profile.get("trimester") in [1, 2, 3])
    )


def process_voice_transcript_for_profile(transcript: str, field_name: str, language: str) -> Optional[str]:
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
            max_tokens=50,
        )
        extracted = response.choices[0].message.content.strip().strip('"').strip("'")
        if extracted.lower() == "null" or not extracted:
            return None
        if field_name == "age":
            try:
                age_num = int(extracted)
                if 0 <= age_num <= 150:
                    return str(age_num)
            except Exception:
                return None
        if field_name == "gender":
            extracted_lower = extracted.lower()
            if any(x in extracted_lower for x in ["male", "مرد", "ਨਰ"]):
                return "male"
            if any(x in extracted_lower for x in ["female", "عورت", "ਮਹਿਲਾ"]):
                return "female"
        return extracted
    except Exception as e:
        st.error(f"Error processing voice transcript: {e}")
        return None


# --- Session State Defaults ---
def init_state():
    defaults = {
        "pdf_uploaded": False,
        "chunks": None,
        "user_profile": {"name": None, "age": None, "gender": None, "is_pregnant": False, "trimester": None},
        "profile_complete": False,
        "test_results": [],
        "analysis_complete": False,
        "selected_language": "English",
        "currently_playing_audio": None,
        "theme": "light",
        "control_dock": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# --- UI Helpers ---
def step_indicator(active_step: int):
    steps = ["Upload", "Profile", "Analysis", "Results"]
    st.markdown('<div class="progress-steps">' + "".join(
        [f'<div class="step-pill {"active" if idx==active_step else ""}">{i+1}. {label}</div>'
         for idx, (i, label) in enumerate(enumerate(steps))]
    ) + "</div>", unsafe_allow_html=True)


# --- Main App ---
def main():
    init_state()

    current_step = 0
    if st.session_state.pdf_uploaded:
        current_step = 1
    if st.session_state.profile_complete:
        current_step = 2
    if st.session_state.analysis_complete:
        current_step = 3

    with st.sidebar:
        st.markdown("### ⚙️ Control")
        if st.button("🔄 Reset / Analyze Another", use_container_width=True, key="sidebar_reset"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_state()
            st.rerun()

        st.markdown("### 🌐 Language")
        lang = st.selectbox("Display & Voice Language", ["English", "Urdu (اردو)", "Punjabi (پنجابی)"], key="sidebar_lang")
        st.session_state.selected_language = lang

        st.markdown("### 🎨 Theme")
        theme_choice = st.radio("Choose theme", ["light", "dark"], horizontal=True, key="sidebar_theme")
        st.session_state.theme = theme_choice

        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            st.success("✅ Groq key set")
        else:
            st.error("⚠️ GROQ_API_KEY missing in .env")

    # Apply theme CSS after user choice
    local_css(st.session_state.theme)

    # Control dock toggle (in-main alternative to sidebar)
    dock_col = st.columns([6, 2])
    with dock_col[1]:
        if st.button("☰ Controls Dock", use_container_width=True, key="dock_toggle"):
            st.session_state.control_dock = not st.session_state.control_dock

    if st.session_state.control_dock:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("##### Quick Controls")
        if st.button("🔄 Reset / Analyze Another", key="dock_reset"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_state()
            st.rerun()
        lang_dock = st.selectbox("Language", ["English", "Urdu (اردو)", "Punjabi (پنجابی)"], index=["English", "Urdu (اردو)", "Punjabi (پنجابی)"].index(st.session_state.selected_language), key="dock_lang")
        st.session_state.selected_language = lang_dock
        theme_dock = st.radio("Theme", ["light", "dark"], horizontal=True, index=0 if st.session_state.theme == "light" else 1, key="dock_theme")
        st.session_state.theme = theme_dock
        st.info("Sidebar can also be reopened via the Streamlit menu (☰) at the top.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Hero
    st.markdown('<div class="mesh-bg"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align:center; padding: 1.5rem 0 0.5rem 0;">
            <div style="display:inline-flex; align-items:center; gap:0.6rem; background:rgba(6,182,212,0.12); padding:0.4rem 0.9rem; border-radius:999px; font-weight:700; color:#0f172a; border:1px solid rgba(6,182,212,0.25);">
                🧬 Clinical Lab Experience
            </div>
            <h1 style="margin:0.5rem 0 0;">Ultra-Modern Lab Report Analyzer</h1>
            <p style="color:#475569; max-width:780px; margin:0 auto;">Upload, extract, and hear clinical-grade insights in a multilingual experience. No diagnoses—just clear significance, localized ranges, and empathetic explanations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    step_indicator(current_step)

    # --- Step 1: Upload ---
    if not st.session_state.pdf_uploaded:
        st.markdown("#### Step 1 · Upload Lab Report")
        upload_col = st.container()
        with upload_col:
            uploaded_file = st.file_uploader(
                "Drop your PDF here or click to browse",
                type=["pdf"],
                help="We only read; nothing is stored.",
            )
            if uploaded_file:
                tmp_path = None
                try:
                    with st.spinner("Extracting PDF content..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        chunks = extract_pdf_to_chunks(tmp_path)
                        st.session_state.chunks = chunks
                        st.session_state.pdf_uploaded = True
                        st.toast("✅ PDF processed", icon="✅")
                        st.rerun()
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
        return

    # --- Step 2: Profile ---
    if st.session_state.pdf_uploaded and not st.session_state.profile_complete:
        st.markdown("#### Step 2 · Patient Profile")
        profile_chunk = st.session_state.chunks.get("profile", "")
        with st.spinner("Extracting profile..."):
            extracted_profile = extract_profile_from_chunk(profile_chunk)
            st.session_state.user_profile.update(extracted_profile)

        profile = st.session_state.user_profile
        if check_profile_complete(profile):
            st.session_state.profile_complete = True
            st.toast("✅ Profile complete", icon="✅")
            st.rerun()

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            name = st.text_input("Patient Name (optional)", value=profile.get("name") or "")
        with col2:
            st.write("")
            if MIC_RECORDER_AVAILABLE:
                name_audio = mic_speech_to_text(start_prompt="🎙️", stop_prompt="🛑", key="name_voice")
                if name_audio:
                    transcript = speech_to_text(name_audio, st.session_state.selected_language)
                    extracted = process_voice_transcript_for_profile(transcript, "name", st.session_state.selected_language)
                    if extracted:
                        name = extracted
                        st.toast(f"Name set to {extracted}", icon="✅")

        c1, c2 = st.columns([3, 1])
        with c1:
            age = st.number_input("Age *", min_value=0, max_value=150, value=profile.get("age") or 0, step=1)
        with c2:
            st.write("")
            if MIC_RECORDER_AVAILABLE:
                age_audio = mic_speech_to_text(start_prompt="🎙️", stop_prompt="🛑", key="age_voice")
                if age_audio:
                    transcript = speech_to_text(age_audio, st.session_state.selected_language)
                    extracted = process_voice_transcript_for_profile(transcript, "age", st.session_state.selected_language)
                    if extracted:
                        age = int(extracted)
                        st.toast(f"Age set to {age}", icon="✅")

        c3, c4 = st.columns([3, 1])
        with c3:
            gender = st.selectbox("Gender *", options=["", "male", "female"],
                                  index=0 if not profile.get("gender") else (1 if profile["gender"] == "male" else 2))
        with c4:
            st.write("")
            if MIC_RECORDER_AVAILABLE:
                gender_audio = mic_speech_to_text(start_prompt="🎙️", stop_prompt="🛑", key="gender_voice")
                if gender_audio:
                    transcript = speech_to_text(gender_audio, st.session_state.selected_language)
                    extracted = process_voice_transcript_for_profile(transcript, "gender", st.session_state.selected_language)
                    if extracted in ["male", "female"]:
                        gender = extracted
                        st.toast(f"Gender set to {extracted}", icon="✅")

        preg_col, trim_col = st.columns(2)
        with preg_col:
            is_pregnant = st.checkbox("Pregnant", value=profile.get("is_pregnant", False))
        with trim_col:
            trimester = st.selectbox("Trimester", options=[None, 1, 2, 3],
                                     index=0 if not profile.get("trimester") else profile["trimester"])

        submitted = st.button("Continue to Analysis", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            if age <= 0:
                st.error("Enter a valid age.")
                return
            if not gender:
                st.error("Select gender.")
                return
            if is_pregnant and trimester is None:
                st.error("Select trimester.")
                return
            st.session_state.user_profile = {
                "name": name or None,
                "age": int(age),
                "gender": gender,
                "is_pregnant": is_pregnant,
                "trimester": trimester if is_pregnant else None,
            }
            st.session_state.profile_complete = True
            st.rerun()
        return

    # --- Step 3: Analysis ---
    if st.session_state.profile_complete and not st.session_state.analysis_complete:
        st.markdown("#### Step 3 · Lab Analysis")
        bloodwork_chunk = st.session_state.chunks.get("bloodwork", "")
        if not bloodwork_chunk or "No lab results" in bloodwork_chunk:
            st.error("No lab results found in PDF.")
            return

        with st.spinner("Extracting tests and computing..."):
            raw_tests = extract_tests_from_bloodwork(bloodwork_chunk)
            if not raw_tests:
                st.warning("No tests could be extracted.")
                return

            test_results = []
            for test in raw_tests:
                raw_name = test.get("raw_name", "")
                value = test.get("value")
                if not raw_name or value is None:
                    continue
                try:
                    norm_result = normalize_test(raw_name, st.session_state.user_profile)
                except Exception as e:
                    test_results.append({"raw_name": raw_name, "test_id": None, "test_info": None,
                                         "error": f"Normalization error: {e}", "warning": None})
                    continue

                if norm_result["status"] == "success":
                    test_id = norm_result["test_id"]
                    try:
                        profile = st.session_state.user_profile
                        test_info = lookup_test_info(
                            test_id=test_id,
                            found_value=float(value),
                            age=profile["age"],
                            gender=profile["gender"],
                            trimester=profile.get("trimester"),
                        )
                    except Exception as e:
                        test_results.append({"raw_name": raw_name, "test_id": test_id, "test_info": None,
                                             "error": f"Lookup error: {e}", "warning": norm_result.get("warning")})
                        continue
                    test_results.append({"raw_name": raw_name, "test_id": test_id, "test_info": test_info,
                                         "warning": norm_result.get("warning")})
                else:
                    test_results.append({"raw_name": raw_name, "test_id": None, "test_info": None,
                                         "error": norm_result.get("message"), "warning": norm_result.get("warning")})

        st.session_state.test_results = test_results
        st.session_state.analysis_complete = True
        st.toast("✅ Analysis ready", icon="✅")
        st.rerun()
        return

    # --- Step 4: Results ---
    if st.session_state.analysis_complete:
        st.markdown("#### Step 4 · Results")

        # Master summary card
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            master_col1, master_col2 = st.columns([4, 1])
            with master_col1:
                st.subheader("Clinical Summary")
                st.caption("Hear the synthesized overview with red flags.")
            with master_col2:
                if st.button("🔊 Read Summary", use_container_width=True):
                    summary_parts = []
                    red_flags = []
                    overall_assessment = []
                    for result in st.session_state.test_results:
                        if result.get("test_info"):
                            tinfo = result["test_info"]
                            tname = tinfo.get("display_name", result.get("raw_name"))
                            status = tinfo.get("status", "unknown")
                            value = tinfo.get("found_value")
                            units = tinfo.get("units", "")
                            analysis_text = generate_clinical_analysis(tinfo, st.session_state.selected_language)
                            import re
                            plain_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', analysis_text)
                            plain_text = re.sub(r'\*([^*]+)\*', r'\1', plain_text)
                            plain_text = re.sub(r'#+\s*', '', plain_text)
                            overall_assessment.append(f"{tname}: {value} {units} - {plain_text[:200]}")
                            if status in ["low", "high"]:
                                red_flags.append(f"{tname} is {status} at {value} {units}")
                    if red_flags:
                        summary_parts.append("Red Flags: " + ". ".join(red_flags))
                    if overall_assessment:
                        summary_parts.append("Overall: " + ". ".join(overall_assessment[:8]))
                    full_summary = ". ".join(summary_parts) if summary_parts else "No significant findings."
                    audio_path = speak_text(full_summary, st.session_state.selected_language, slow=False)
                    if audio_path:
                        play_audio(audio_path)
                        st.toast("🔊 Playing summary", icon="🔊")
                    else:
                        st.error("Could not generate audio.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### Test Insights")
        for result in st.session_state.test_results:
            if result.get("error"):
                st.markdown(
                    f'<div class="result-card warning"><div class="badge warn">Error</div><h4>{result.get("raw_name")}</h4><p>{result["error"]}</p></div>',
                    unsafe_allow_html=True,
                )
                continue

            if result.get("test_info"):
                tinfo = result["test_info"]
                status = tinfo.get("status", "unknown")
                status_icon = "✅" if status == "normal" else "⚠️"
                warn_class = "warning" if status in ["low", "high"] else ""
                badge = '<span class="badge">Normal</span>' if status == "normal" else '<span class="badge warn">Alert</span>'
                range_str = "N/A"
                if tinfo["min_value"] is not None and tinfo["max_value"] is not None:
                    range_str = f"{tinfo['min_value']} - {tinfo['max_value']} {tinfo['units']}"
                border_color = "#10B981" if status == "normal" else "#F43F5E"
                badge_bg = "var(--status-normal-glass)" if status == "normal" else "var(--status-critical-glass)"
                badge_color = "#0f172a" if status == "normal" else "#b91c1c"
                st.markdown(
                    f"""
                    <div class="result-card {warn_class}" style="border-left-color:{border_color};">
                        <span class="badge" style="background:{badge_bg}; color:{badge_color}; border:none;">{"Normal" if status=="normal" else "Alert"}</span>
                        <h4 style="margin-bottom:0.2rem;">{status_icon} {tinfo.get("display_name", result.get("raw_name"))}</h4>
                        <p style="margin:0; color:#0f172a;"><strong>Value:</strong> {tinfo.get("found_value")} {tinfo.get("units","")}</p>
                        <p style="margin:0; color:#0f172a;"><strong>Reference:</strong> {range_str}</p>
                        {"<p style='margin:0; color:#b91c1c;'>" + tinfo.get("fallback_message","") + "</p>" if tinfo.get("is_fallback") else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("Details & Voice"):
                    analysis_text = generate_clinical_analysis(tinfo, st.session_state.selected_language)
                    st.markdown(analysis_text)
                    if result.get("warning"):
                        st.warning(result["warning"])
                    if st.button(f"🔊 Hear {tinfo.get('display_name','this test')}", key=f"speak_{tinfo.get('test_id')}"):
                        import re
                        plain_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', analysis_text)
                        plain_text = re.sub(r'\*([^*]+)\*', r'\1', plain_text)
                        plain_text = re.sub(r'#+\s*', '', plain_text)
                        plain_text = re.sub(r'\n+', '. ', plain_text)
                        audio_path = speak_text(plain_text, st.session_state.selected_language, slow=False)
                        if audio_path:
                            play_audio(audio_path)
                            st.toast("🔊 Playing explanation...", icon="🔊")
                        else:
                            st.error("Audio generation failed.")

        st.info(
            "Important: Automated clinical significance only. No diagnosis or treatment advice. Please consult a qualified clinician."
        )


if __name__ == "__main__":
    main()
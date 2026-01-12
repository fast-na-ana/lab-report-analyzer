"""
Voice utilities for speech-to-text and text-to-speech functionality.
Supports multilingual voice input/output for the medical lab report analyzer.
"""

import os
import tempfile
from typing import Optional
from gtts import gTTS
import streamlit as st
import speech_recognition as sr


# Language code mapping for speech recognition and TTS
LANGUAGE_CODES = {
    "English": {
        "speech_to_text": "en-US",
        "gtts": "en"
    },
    "Urdu (اردو)": {
        "speech_to_text": "ur-PK",
        "gtts": "ur"
    },
    "Punjabi (پنجابی)": {
        "speech_to_text": "pa-PK",
        "gtts": "pa"
    }
}


def get_language_code(language: str, code_type: str = "gtts") -> str:
    """
    Get language code for speech recognition or TTS.
    
    Args:
        language: Language name (e.g., "English", "Urdu (اردو)")
        code_type: "gtts" or "speech_to_text"
        
    Returns:
        str: Language code, defaults to English if not found
    """
    lang_code = LANGUAGE_CODES.get(language, {}).get(code_type, "en")
    return lang_code


def speech_to_text(audio_bytes: bytes, language: str = "English") -> Optional[str]:
    """
    Convert speech audio to text using Google Speech Recognition.
    
    Args:
        audio_bytes: Audio file bytes (WAV format)
        language: Selected language for recognition
        
    Returns:
        str or None: Transcribed text or None if error
    """
    lang_code = get_language_code(language, "speech_to_text")
    
    try:
        # Save audio bytes to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_path) as source:
                audio = recognizer.record(source)
            
            # Recognize using Google Speech Recognition
            text = recognizer.recognize_google(audio, language=lang_code)
            return text
        except sr.UnknownValueError:
            st.error("Could not understand audio. Please try again.")
            return None
        except sr.RequestError as e:
            st.error(f"Speech recognition service error: {e}")
            return None
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
    except Exception as e:
        st.error(f"Error in speech recognition: {e}")
        return None


def speak_text(text: str, language: str = "English", slow: bool = False) -> Optional[str]:
    """
    Convert text to speech using gTTS and return audio file path.
    
    Args:
        text: Text to convert to speech
        language: Selected language for TTS
        slow: Whether to speak slowly
        
    Returns:
        str or None: Path to generated audio file or None on error
    """
    try:
        lang_code = get_language_code(language, "gtts")
        
        # Create gTTS object
        tts = gTTS(text=text, lang=lang_code, slow=slow)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
            tts.save(tmp_path)
        
        return tmp_path
        
    except Exception as e:
        st.error(f"Error generating speech: {e}")
        return None


def play_audio(audio_path: str):
    """
    Play audio file in Streamlit.
    
    Args:
        audio_path: Path to audio file
    """
    if audio_path and os.path.exists(audio_path):
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)

"""
Clinical Significance Analysis Engine (NO DIAGNOSIS)
Compares test values against reference ranges and reports clinical significance from KB
"""

import os
from groq import Groq
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_groq_client() -> Groq:
    """Get Groq client with API key from environment."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set. "
            "Please create a .env file in the project root with: GROQ_API_KEY=your-api-key-here"
        )
    return Groq(api_key=api_key)


def analyze_clinical_significance(test_info: Dict) -> str:
    """
    Analyze clinical significance of a single test result.
    DO NOT DIAGNOSE. Only report if value is abnormal and what KB says.
    Displays fallback messages when gender-appropriate fallback ranges are used.
    
    Args:
        test_info: Dict from lookup_test_info with test data, status, range, etc.
                  Must include is_fallback and fallback_message fields.
        
    Returns:
        str: Clinical significance analysis with citation, disclaimer, and fallback message if applicable
    """
    test_id = test_info.get("test_id", "Unknown")
    found_value = test_info.get("found_value")
    status = test_info.get("status", "unknown")
    min_val = test_info.get("min_value")
    max_val = test_info.get("max_value")
    units = test_info.get("units", "")
    clinical_sig = test_info.get("clinical_significance", "")
    citation = test_info.get("source_citation", "")
    display_name = test_info.get("display_name", test_id)
    is_fallback = test_info.get("is_fallback", False)
    fallback_message = test_info.get("fallback_message")
    
    # Build analysis
    analysis_parts = []
    
    # Value and status
    analysis_parts.append(f"**{display_name}**: {found_value} {units}")
    
    if status == "normal":
        analysis_parts.append(f"✅ **Within normal range** ({min_val} - {max_val} {units})")
        if clinical_sig:
            analysis_parts.append(f"\n*Clinical context*: {clinical_sig}")
    elif status == "low":
        analysis_parts.append(f"⚠️ **Below normal range** (Reference: {min_val} - {max_val} {units})")
        analysis_parts.append(f"\n*Clinical significance*: {clinical_sig}")
    elif status == "high":
        analysis_parts.append(f"⚠️ **Above normal range** (Reference: {min_val} - {max_val} {units})")
        analysis_parts.append(f"\n*Clinical significance*: {clinical_sig}")
    elif status == "range_unavailable":
        analysis_parts.append(f"⚠️ **Range unavailable** - Unable to compare value against reference ranges")
        if clinical_sig:
            analysis_parts.append(f"\n*Note*: {clinical_sig}")
    else:
        analysis_parts.append(f"❓ **Status: {status}**")
    
    # Add fallback message if applicable (MANDATORY OUTPUT FLAG)
    if is_fallback and fallback_message:
        analysis_parts.append(f"\n\n📌 **{fallback_message}**")
    
    # Add citation
    if citation:
        analysis_parts.append(f"\n*Source*: {citation}")
    
    # Add required disclaimer for abnormal values
    if status in ["low", "high"]:
        disclaimer = "\n\n⚠️ **Disclaimer**: This is an automated analysis of clinical significance based on provided literature and does not constitute a medical diagnosis."
        analysis_parts.append(disclaimer)
    
    return "\n".join(analysis_parts)


def generate_clinical_analysis(test_info: Dict, language: str = "English") -> str:
    """
    Generate clinical analysis using LLM in the selected language.
    Provides detailed, culturally-adapted analysis in English, Urdu, or Punjabi.
    
    Args:
        test_info: Dict from lookup_test_info with test data, status, range, etc.
                  Must include is_fallback and fallback_message fields.
        language: Selected language ("English", "Urdu (اردو)", or "Punjabi (پنجابی)")
        
    Returns:
        str: Clinical significance analysis in the selected language with citation and disclaimer
    """
    client = get_groq_client()
    
    # Extract test information
    test_id = test_info.get("test_id", "Unknown")
    found_value = test_info.get("found_value")
    status = test_info.get("status", "unknown")
    min_val = test_info.get("min_value")
    max_val = test_info.get("max_value")
    units = test_info.get("units", "")
    clinical_sig = test_info.get("clinical_significance", "")
    citation = test_info.get("source_citation", "")
    display_name = test_info.get("display_name", test_id)
    is_fallback = test_info.get("is_fallback", False)
    fallback_message = test_info.get("fallback_message")
    
    # Build system prompt with language specification
    language_name = language.split("(")[0].strip()  # Extract "Urdu" or "Punjabi" or keep "English"
    
    cultural_guidance = ""
    if language_name in ["Urdu", "Punjabi"]:
        cultural_guidance = """
        
Cultural Adaptation Guidelines:
- Use simple, empathetic terms that are culturally appropriate
- For glucose/diabetes: use terms like 'shukar' (Urdu: شکر) or 'meetha' (sweet) 
- For anemia: use 'khoon ki kami' (Urdu: خون کی کمی) meaning blood deficiency
- Use respectful, patient-friendly language suitable for Pakistani medical context
- Maintain professional medical terminology while being accessible"""
    
    system_prompt = f"""You are a helpful clinical assistant in Pakistan. The user has selected the language: {language}.

You MUST provide the entire analysis, explanation, and safety warnings in {language}.

Your task is to analyze lab test results and provide:
1. **Status**: Clear indication if the value is normal, low, or high
2. **Meaning**: What this result means in simple terms
3. **Next Steps**: What the patient should do (consult doctor, monitor, etc.)

IMPORTANT RULES:
- DO NOT provide medical diagnosis
- DO NOT prescribe treatments or medications
- Always recommend consulting a qualified healthcare provider
- Use reference ranges provided to explain if the value is normal/abnormal
- Be empathetic and clear in your explanations{cultural_guidance}

Provide your response in a structured format suitable for markdown display."""
    
    # Build user prompt with test data
    reference_range_info = f"{min_val} - {max_val} {units}" if (min_val is not None and max_val is not None) else "Not available"
    
    user_prompt = f"""Test Information:
- Test Name: {display_name}
- Test Value: {found_value} {units}
- Status: {status}
- Reference Range: {reference_range_info}
- Clinical Significance (from knowledge base): {clinical_sig if clinical_sig else "Not specified"}

{"⚠️ Note: " + fallback_message if (is_fallback and fallback_message) else ""}

Please provide a comprehensive clinical analysis in {language} following this structure:
1. **Status**: Is this value normal, low, or high?
2. **Meaning**: What does this result indicate?
3. **Next Steps**: What should the patient do?

Remember: Provide all text in {language}. Do not diagnose, only explain what the result means based on the reference range."""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        analysis_text = response.choices[0].message.content.strip()
        
        # Add citation and disclaimer
        analysis_parts = [analysis_text]
        
        # Add fallback message if applicable
        if is_fallback and fallback_message:
            analysis_parts.append(f"\n\n📌 **{fallback_message}**")
        
        # Add citation
        if citation:
            citation_label = "Source" if language_name == "English" else "ماخذ" if language_name == "Urdu" else "ماخذ"
            analysis_parts.append(f"\n\n*{citation_label}*: {citation}")
        
        # Add disclaimer for abnormal values
        if status in ["low", "high"]:
            if language_name == "English":
                disclaimer = "\n\n⚠️ **Disclaimer**: This is an automated analysis of clinical significance based on provided literature and does not constitute a medical diagnosis. Please consult with a qualified healthcare provider for proper medical evaluation."
            elif language_name == "Urdu":
                disclaimer = "\n\n⚠️ **انتباہ**: یہ ایک خودکار تجزیہ ہے جو فراہم کردہ ادبیات پر مبنی ہے اور یہ طبی تشخیص نہیں ہے۔ براہ کرم مناسب طبی تشخیص کے لیے ایک اہل صحت کے پیشہ ور سے مشورہ کریں۔"
            else:  # Punjabi
                disclaimer = "\n\n⚠️ **انتباہ**: ایہ اک خودکار تجزیہ اے جو فراہم کردہ ادبیات تے مبنی اے تے ایہ طبی تشخیص نئیں اے۔ براہ کرم مناسب طبی تشخیص لئی اک اہل صحت دے پیشہ ور توں مشورہ کرو۔"
            analysis_parts.append(disclaimer)
        
        return "\n".join(analysis_parts)
        
    except Exception as e:
        # Fallback to basic analysis if LLM fails
        return analyze_clinical_significance(test_info)


def generate_batch_analysis(test_results: List[Dict]) -> str:
    """
    Generate analysis for multiple test results.
    
    Args:
        test_results: List of test_info dicts from lookup_test_info
        
    Returns:
        str: Combined analysis with all tests
    """
    analyses = []
    
    for i, test_info in enumerate(test_results, 1):
        analysis = analyze_clinical_significance(test_info)
        analyses.append(f"### Test {i}")
        analyses.append(analysis)
        analyses.append("")  # Empty line between tests
    
    return "\n".join(analyses)

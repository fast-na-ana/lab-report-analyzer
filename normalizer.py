"""
Semantic Normalizer: Maps raw test names to KB test_id using Groq
Includes pregnancy-aware logic and gender-based mapping
"""

import json
import os
from groq import Groq
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from lookup import load_medical_kb, find_test_by_id

# Load environment variables from .env file
load_dotenv()


# Initialize Groq client
def get_groq_client() -> Groq:
    """Get Groq client with API key from environment or fallback."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set. "
            "Please create a .env file in the project root with: GROQ_API_KEY=your-api-key-here"
        )
    return Groq(api_key=api_key)


def get_all_test_ids() -> list:
    """
    Get all available test_ids from the KB for Groq to choose from.
    
    Returns:
        list: List of all test_id strings
    """
    kb = load_medical_kb()
    return [entry.get("test_id") for entry in kb if entry.get("test_id")]


def normalize_test(raw_name: str, user_profile: Dict) -> Dict:
    """
    Normalize a raw test name to a test_id from medical_kb.json using Groq.
    Handles gender-specific and pregnancy-aware mapping.
    
    Args:
        raw_name: Raw test name from the lab report (e.g., "HGB", "Hemoglobin")
        user_profile: {"name": str, "age": int, "gender": "male"|"female", 
                       "is_pregnant": bool, "trimester": 1|2|3|null}
        
    Returns:
        dict: {
            "status": "success"|"error",
            "test_id": str or None,
            "message": str or None,
            "warning": str or None
        }
    """
    client = get_groq_client()
    kb = load_medical_kb()
    all_test_ids = get_all_test_ids()
    
    gender = user_profile.get("gender", "").lower()
    is_pregnant = user_profile.get("is_pregnant", False)
    trimester = user_profile.get("trimester")
    
    # Step 1: Check if pregnancy drastically affects this substance
    if is_pregnant and trimester:
        pregnancy_check_prompt = f"""
You are a clinical data analyzer. Determine if the following lab test/substance is DRAMATICALLY affected by pregnancy.

Test name: {raw_name}

Answer with ONLY one word: "YES" if the substance is drastically affected by pregnancy (requiring trimester-specific ranges), or "NO" if the effect is mild or negligible.

Examples:
- Hemoglobin/HGB: YES (pregnancy causes significant hemodilution)
- Glucose: NO (minimal change)
- ALT/SGPT: YES (pregnancy can affect liver enzymes)
- MCV: NO (minimal change)

Answer:"""
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": pregnancy_check_prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            pregnancy_effect = response.choices[0].message.content.strip().upper()
            is_drastically_affected = pregnancy_effect.startswith("YES")
            
        except Exception as e:
            # On error, assume we should check for pregnancy data
            is_drastically_affected = True
    
    else:
        is_drastically_affected = False
    
    # Step 2: Map raw_name to test_id using Groq
    # Build context about available tests
    test_ids_json = json.dumps(all_test_ids[:100], indent=2)  # Limit to avoid token overflow
    
    # Include gender in prompt for proper gender-specific selection
    gender_context = ""
    if gender:
        gender_context = f"\nPatient gender: {gender}"
        if is_pregnant:
            gender_context += f" (pregnant, trimester {trimester})"
        gender_context += "\n"
    
    normalization_prompt = f"""
You are a medical lab test normalizer. Map the raw test name to the closest matching test_id from the knowledge base.

Raw test name: "{raw_name}"{gender_context}
Available test_ids in the knowledge base (first 100):
{test_ids_json}

Instructions:
1. Find the test_id that best matches "{raw_name}"
2. If patient gender is "male", prefer test_ids ending with "_male" if they exist
3. If patient gender is "female" and not pregnant, prefer test_ids ending with "_female" if they exist
4. If no gender-specific version exists, use the base test_id (e.g., "mcv", "wbc_count")
5. Return ONLY the test_id string, nothing else

Examples:
- "HGB" or "Hemoglobin" + male → "haemoglobin_male"
- "HGB" or "Hemoglobin" + female → "haemoglobin_female"  
- "MCV" → "mcv"
- "WBC" or "White Blood Cell" → "wbc_count"

Return the test_id:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": normalization_prompt}],
            temperature=0.1,
            max_tokens=50
        )
        
        suggested_test_id = response.choices[0].message.content.strip().strip('"').strip("'")
        
        # CRITICAL: Fix wrong gender-specific test_id if Groq selected the wrong one
        # If patient is female but Groq returned _male version, correct it
        if gender == "female" and suggested_test_id.endswith("_male") and not is_pregnant:
            base_id = suggested_test_id.replace("_male", "")
            female_version = f"{base_id}_female"
            if find_test_by_id(female_version):
                suggested_test_id = female_version
            else:
                # Fall back to base if female version doesn't exist
                suggested_test_id = base_id
        # If patient is male but Groq returned _female version, correct it
        elif gender == "male" and suggested_test_id.endswith("_female"):
            base_id = suggested_test_id.replace("_female", "")
            male_version = f"{base_id}_male"
            if find_test_by_id(male_version):
                suggested_test_id = male_version
            else:
                # Fall back to base if male version doesn't exist
                suggested_test_id = base_id
        
        # Validate that the test_id exists in KB
        test_entry = find_test_by_id(suggested_test_id)
        if not test_entry:
            # Try to find a similar one or base version
            # Remove gender suffix and try again
            base_id = suggested_test_id.replace("_male", "").replace("_female", "")
            test_entry = find_test_by_id(base_id)
            if test_entry:
                suggested_test_id = base_id
            else:
                return {
                    "status": "error",
                    "test_id": None,
                    "message": f"Could not find test_id '{suggested_test_id}' in knowledge base",
                    "warning": None
                }
        
    except Exception as e:
        return {
            "status": "error",
            "test_id": None,
            "message": f"Error during normalization: {str(e)}",
            "warning": None
        }
    
    # Step 3: Apply gender-specific mapping if needed (before pregnancy check)
    # Only do this if we don't already have a gender-specific suffix
    if not suggested_test_id.endswith("_male") and not suggested_test_id.endswith("_female"):
        if gender == "male":
            male_version = f"{suggested_test_id}_male"
            if find_test_by_id(male_version):
                suggested_test_id = male_version
        elif gender == "female" and not is_pregnant:
            # For non-pregnant females, try female-specific version
            female_version = f"{suggested_test_id}_female"
            if find_test_by_id(female_version):
                suggested_test_id = female_version
    
    # Step 4: Re-validate the final test_id exists
    final_test_entry = find_test_by_id(suggested_test_id)
    if not final_test_entry:
        return {
            "status": "error",
            "test_id": None,
            "message": f"Could not validate final test_id '{suggested_test_id}' in knowledge base",
            "warning": None
        }
    
    # Step 5: Pregnancy-specific validation (with final test_id)
    result = {
        "status": "success",
        "test_id": suggested_test_id,
        "message": None,
        "warning": None
    }
    
    if is_pregnant and trimester and is_drastically_affected:
        pak_ranges = final_test_entry.get("pakistan_reference_range", {})
        pregnancy_key = f"pregnancy_t{trimester}"
        
        if pregnancy_key not in pak_ranges:
            # Check if there's any pregnancy data at all
            has_any_pregnancy_data = any(
                k.startswith("pregnancy_") for k in pak_ranges.keys()
            )
            
            if not has_any_pregnancy_data:
                return {
                    "status": "error",
                    "test_id": None,
                    "message": f"Substance '{raw_name}' is drastically affected by pregnancy; updated trimester-specific data unavailable in knowledge base.",
                    "warning": None
                }
            else:
                # KB has pregnancy data but not for this trimester - use fallback with warning
                result["warning"] = f"Warning: General adult range may be used. Trimester {trimester} specific data not available for this test."
    
    return result


def extract_tests_from_bloodwork(bloodwork_chunk: str) -> list:
    """
    Extract individual test name-value pairs from bloodwork chunk using Groq.
    
    Args:
        bloodwork_chunk: The bloodwork section from chunked PDF
        
    Returns:
        list: List of dicts with "raw_name" and "value" keys
    """
    client = get_groq_client()
    
    extraction_prompt = f"""
Extract all lab test results from the following medical report bloodwork section.
Return ONLY a valid JSON array, no other text.

Each object should have:
- "raw_name": the test name as it appears (e.g., "HGB", "Hemoglobin", "WBC")
- "value": the numerical value (as float)

Example format:
[
    {{"raw_name": "HGB", "value": 12.5}},
    {{"raw_name": "WBC", "value": 7.2}},
    {{"raw_name": "MCV", "value": 88.0}}
]

Bloodwork section:
{bloodwork_chunk[:3000]}

Return JSON array only:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.1,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        # Try to extract JSON from response (might have markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        tests = json.loads(content)
        
        if not isinstance(tests, list):
            return []
        
        return tests
        
    except Exception as e:
        print(f"Error extracting tests: {e}")
        return []

"""
Lookup Module: Deterministic retrieval of reference ranges from medical_kb.json
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_medical_kb() -> Dict:
    """
    Load medical knowledge base from medical_kb.json with retry logic.
    Attempts to load the file up to 3 times with 1-second delays between attempts.
    
    Returns:
        dict: Medical knowledge base with test entries
        
    Raises:
        FileNotFoundError: If file is not found after 3 attempts
        IOError: If file is locked or unreadable after 3 attempts
    """
    kb_path = Path("medical_kb.json")
    max_attempts = 3
    delay_seconds = 1.0
    
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            if not kb_path.exists():
                if attempt < max_attempts:
                    time.sleep(delay_seconds)
                    continue
                raise FileNotFoundError(
                    f"medical_kb.json not found in current directory after {max_attempts} attempts"
                )
            
            # Try to open and read the file
            with open(kb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # The KB structure is: {"lab_report_analyzer_kb": [...]}
            if "lab_report_analyzer_kb" in data:
                return data["lab_report_analyzer_kb"]
            return data
            
        except (IOError, OSError, PermissionError) as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(delay_seconds)
                continue
            raise IOError(
                f"medical_kb.json is locked or unreadable after {max_attempts} attempts. "
                f"Last error: {str(e)}"
            ) from e
        except json.JSONDecodeError as e:
            # JSON parsing errors should not retry - file is corrupted
            raise ValueError(f"medical_kb.json contains invalid JSON: {str(e)}") from e
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(delay_seconds)
                continue
            raise RuntimeError(
                f"Failed to load medical_kb.json after {max_attempts} attempts. "
                f"Last error: {str(e)}"
            ) from e
    
    # Should never reach here, but just in case
    if last_error:
        raise last_error
    raise FileNotFoundError(f"medical_kb.json not found in current directory")


def find_test_by_id(test_id: str) -> Optional[Dict]:
    """
    Find a test entry by test_id in the KB.
    
    Args:
        test_id: The test_id to search for (e.g., "haemoglobin_male", "mcv")
        
    Returns:
        dict or None: Test entry from KB if found
    """
    kb = load_medical_kb()
    for entry in kb:
        if entry.get("test_id") == test_id:
            return entry
    return None


def get_reference_range(test_id: str, age: int, gender: str, trimester: Optional[int] = None) -> Tuple[Optional[float], Optional[float], str, Optional[str], bool, Optional[str], bool]:
    """
    Get reference range for a test based on patient profile with hierarchical gender-prioritizing fallback.
    
    Hierarchical Fallback Logic:
    1. Exact Match: Try to find (test_name, age_group, gender, pregnancy_status)
    2. Gender-Matched Adult Fallback: If age_group is 'child' or 'senior'/'elderly' and no exact match exists,
       attempt to retrieve the 'adult' range for the SAME gender
    3. Global Default: If step 2 fails, only then fall back to the "base" or "standard" value
    
    Constraints:
    - If a patient is 'female', NEVER default to a 'male' range
    - Pregnancy status takes precedence over generic 'adult female' range
    
    Args:
        test_id: The normalized test_id from KB
        age: Patient age in years
        gender: "male" or "female"
        trimester: Pregnancy trimester (1, 2, or 3) if applicable, else None
        
    Returns:
        tuple: (min_value, max_value, range_source, citation, is_fallback, fallback_message, no_gender_specific_range)
               no_gender_specific_range: True if no gender-matched range exists (generic range used)
               Returns (None, None, "not_found", None, False, None, False) if test not found
    """
    test_entry = find_test_by_id(test_id)
    
    if not test_entry:
        return None, None, "not_found", None, False, None, False
    
    citation = test_entry.get("source_citation", "")
    gender_lower = gender.lower() if gender else None
    
    # STEP 1: Exact Match - Determine requested age_group and pregnancy_status
    range_key = None
    requested_category = None
    age_group = None  # Track age group for fallback logic
    
    # Priority 1: Pregnancy-specific ranges (takes precedence)
    if trimester is not None and trimester in [1, 2, 3]:
        range_key = f"pregnancy_t{trimester}"
        requested_category = f"pregnancy trimester {trimester}"
        age_group = "pregnancy"  # Pregnancy is not considered an age group for fallback
    
    # Priority 2: Age-based ranges (if not pregnant)
    if range_key is None:
        if age < 1:
            range_key = "infant"
            requested_category = "infant"
            age_group = "infant"
        elif age < 18:
            if age >= 1 and age < 17:
                range_key = "child_1_17yr"
                requested_category = "child (1-17 years)"
                age_group = "child"
            else:
                range_key = "adult"
                requested_category = "adult"
                age_group = "adult"
        elif age >= 65:
            range_key = "elderly"
            requested_category = "elderly"
            age_group = "senior"  # Using 'senior' as per user requirement
        else:
            range_key = "adult"
            requested_category = "adult"
            age_group = "adult"
    
    # Get pakistan_reference_range (localized)
    pak_ranges = test_entry.get("pakistan_reference_range", {})
    
    # Try STEP 1: Exact Match
    if isinstance(pak_ranges, dict) and range_key in pak_ranges:
        range_data = pak_ranges[range_key]
        if isinstance(range_data, dict) and "min" in range_data and "max" in range_data:
            # Exact match found - check if current test_id is gender-specific
            is_gender_specific = test_id.endswith("_female") or test_id.endswith("_male")
            return range_data["min"], range_data["max"], "pakistan", citation, False, None, not is_gender_specific
    
    # STEP 2: Gender-Matched Adult Fallback
    # Only apply if age_group is 'child' or 'senior' (not for infant, adult, or pregnancy)
    if age_group in ["child", "senior"] and gender_lower:
        # Determine if current test_id is gender-specific
        is_current_gender_specific = test_id.endswith("_female") or test_id.endswith("_male")
        
        # Try adult range of current test_id first (if it's already gender-specific)
        if is_current_gender_specific:
            if "adult" in pak_ranges:
                range_data = pak_ranges["adult"]
                if isinstance(range_data, dict) and "min" in range_data and "max" in range_data:
                    gender_label = "Female" if test_id.endswith("_female") else "Male"
                    fallback_msg = (
                        f"Note: Specific {requested_category} data for this substance was not found. "
                        f"Analysis performed using standard {gender_label} adult reference ranges instead."
                    )
                    return range_data["min"], range_data["max"], "pakistan_adult_fallback", citation, True, fallback_msg, False
        
        # If current test_id is NOT gender-specific, try to find gender-specific version
        else:
            if gender_lower == "female":
                # NEVER default female to male - try female-specific version only
                female_test_id = f"{test_id}_female"
                female_test_entry = find_test_by_id(female_test_id)
                if female_test_entry:
                    female_pak_ranges = female_test_entry.get("pakistan_reference_range", {})
                    if isinstance(female_pak_ranges, dict) and "adult" in female_pak_ranges:
                        adult_range_data = female_pak_ranges["adult"]
                        if isinstance(adult_range_data, dict) and "min" in adult_range_data and "max" in adult_range_data:
                            fallback_msg = (
                                f"Note: Specific {requested_category} data for this substance was not found. "
                                f"Analysis performed using standard Female adult reference ranges instead."
                            )
                            return adult_range_data["min"], adult_range_data["max"], "pakistan_adult_fallback", citation, True, fallback_msg, False
            
            elif gender_lower == "male":
                male_test_id = f"{test_id}_male"
                male_test_entry = find_test_by_id(male_test_id)
                if male_test_entry:
                    male_pak_ranges = male_test_entry.get("pakistan_reference_range", {})
                    if isinstance(male_pak_ranges, dict) and "adult" in male_pak_ranges:
                        adult_range_data = male_pak_ranges["adult"]
                        if isinstance(adult_range_data, dict) and "min" in adult_range_data and "max" in adult_range_data:
                            fallback_msg = (
                                f"Note: Specific {requested_category} data for this substance was not found. "
                                f"Analysis performed using standard Male adult reference ranges instead."
                            )
                            return adult_range_data["min"], adult_range_data["max"], "pakistan_adult_fallback", citation, True, fallback_msg, False
        
        # If gender-matched adult fallback failed, continue to STEP 3
    
    # STEP 3: Global Default (base/standard value)
    # Try current test_id's adult range if available (may be generic/standard)
    # Safety check: NEVER use male range for female patient
    if "adult" in pak_ranges:
        # Safety check: Skip if patient is female and test_id is male-specific
        if not (gender_lower == "female" and test_id.endswith("_male")):
            range_data = pak_ranges["adult"]
            if isinstance(range_data, dict) and "min" in range_data and "max" in range_data:
                # Check if we used a gender-specific range or generic
                is_gender_specific = test_id.endswith("_female") or test_id.endswith("_male")
                no_gender_specific = not is_gender_specific and gender_lower is not None
                
                gender_label = "standard"
                if test_id.endswith("_female"):
                    gender_label = "Female"
                elif test_id.endswith("_male"):
                    gender_label = "Male"
                
                fallback_msg = (
                    f"Note: Specific {requested_category} data for this substance was not found. "
                    f"Analysis performed using standard {gender_label} reference ranges instead."
                ) if requested_category else (
                    f"Note: Analysis performed using standard {gender_label} reference ranges."
                )
                return range_data["min"], range_data["max"], "pakistan_adult_fallback", citation, True, fallback_msg, no_gender_specific
    
    # Fallback to global_reference_range (base/standard)
    global_range = test_entry.get("global_reference_range", {})
    if isinstance(global_range, dict) and "min" in global_range and "max" in global_range:
        # Global range is generic, so flag as no gender-specific range if gender is known
        no_gender_specific = gender_lower is not None
        fallback_msg = (
            f"Note: Pakistan-specific reference ranges not available. Using global reference ranges."
        )
        return global_range["min"], global_range["max"], "global", citation, True, fallback_msg, no_gender_specific
    
    # No range found
    return None, None, "no_range_available", citation, False, None, False


def lookup_test_info(test_id: str, found_value: float, age: int, gender: str, trimester: Optional[int] = None) -> Dict:
    """
    Lookup complete test information including reference range check with fallback flags.
    
    Args:
        test_id: Normalized test_id from KB
        found_value: The actual test value from the report
        age: Patient age
        gender: "male" or "female"
        trimester: Pregnancy trimester (1, 2, 3) or None
        
    Returns:
        dict: Complete test information with status, range, clinical data, and fallback flags:
            - test_id: str
            - found_value: float
            - status: str ("normal", "low", "high", "range_unavailable", "test_not_found")
            - min_value: float or None
            - max_value: float or None
            - units: str
            - range_source: str
            - clinical_significance: str
            - source_citation: str
            - display_name: str
            - is_fallback: bool (True if fallback range was used)
            - fallback_message: str or None (Message to display if fallback occurred)
            - no_gender_specific_range: bool (True if no gender-matched range exists, generic range used)
    """
    test_entry = find_test_by_id(test_id)
    
    if not test_entry:
        return {
            "test_id": test_id,
            "found_value": found_value,
            "status": "test_not_found",
            "min_value": None,
            "max_value": None,
            "units": None,
            "range_source": "not_found",
            "clinical_significance": None,
            "source_citation": None,
            "display_name": None,
            "is_fallback": False,
            "fallback_message": None,
            "no_gender_specific_range": False
        }
    
    # Get reference range with fallback flags (now returns 7 values)
    min_val, max_val, range_source, citation, is_fallback, fallback_message, no_gender_specific_range = get_reference_range(test_id, age, gender, trimester)
    
    # Determine status
    status = "normal"
    if min_val is not None and max_val is not None:
        if found_value < min_val:
            status = "low"
        elif found_value > max_val:
            status = "high"
    else:
        status = "range_unavailable"
    
    # Add warning to fallback_message if no gender-specific range was found
    if no_gender_specific_range and fallback_message:
        fallback_message += " Warning: No gender-specific range found - using generic range."
    elif no_gender_specific_range and not fallback_message:
        fallback_message = "Warning: No gender-specific range found - using generic range."
    
    return {
        "test_id": test_id,
        "found_value": found_value,
        "status": status,
        "min_value": min_val,
        "max_value": max_val,
        "units": test_entry.get("units", ""),
        "range_source": range_source,
        "clinical_significance": test_entry.get("clinical_significance", ""),
        "source_citation": citation or "",
        "display_name": test_entry.get("display_name", test_id),
        "is_fallback": is_fallback,
        "fallback_message": fallback_message,
        "no_gender_specific_range": no_gender_specific_range
    }

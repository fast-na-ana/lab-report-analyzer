"""
PDF Parser for Medical Lab Reports
Extracts PDF content and splits into Profile and Bloodwork chunks
"""

import re
import pymupdf4llm
from pathlib import Path
from typing import Dict, List, Tuple


def extract_pdf_to_markdown(pdf_path: str | Path) -> str:
    """
    Extract PDF to markdown using pymupdf4llm with medical document settings.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        str: Full markdown content of the PDF
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        md_text = pymupdf4llm.to_markdown(
            pdf_path,
            pages=None,               # all pages
            page_chunks=False,        # one big string
            margins=(20, 40, 20, 40), # crop headers/footers
            write_images=False,
            extract_words=False,
            show_progress=False
        )
        
        # Ensure we got a string back
        if not isinstance(md_text, str):
            raise TypeError(f"pymupdf4llm.to_markdown returned {type(md_text)}, expected str")
        
        # Sanitize the markdown text - remove any problematic characters
        # This is a safety measure to handle any edge cases
        if md_text:
            # Replace any null bytes or other problematic control characters
            md_text = md_text.replace('\x00', '')
            # Clean up any obvious malformed characters that might cause issues downstream
            # But preserve the structure for our simple string-based chunking
        
        return md_text
        
    except Exception as e:
        error_msg = str(e)
        # Check for regex-related errors (pymupdf4llm internally uses regex)
        if "re.error" in error_msg or "regex" in error_msg.lower() or "unterminated" in error_msg.lower() or "missing )" in error_msg.lower():
            # Provide detailed error message for regex issues
            raise RuntimeError(
                f"Regex parsing error detected in PDF extraction. "
                f"This may be due to special characters or malformed content in the PDF. "
                f"Original error: {error_msg}. "
                f"Please try a different PDF file or ensure the PDF is not corrupted."
            ) from e
        else:
            raise RuntimeError(
                f"Error extracting PDF to markdown: {error_msg}. "
                f"Please ensure the PDF is not corrupted and contains readable text."
            ) from e


def chunk_medical_report(markdown: str) -> Dict[str, str]:
    """
    Split medical report into exactly two chunks:
    - Chunk 1 (Profile): Patient identity, age, gender, pregnancy status, dates
    - Chunk 2 (Bloodwork): All lab tables, values, and units
    
    Args:
        markdown: Full markdown content from PDF
        
    Returns:
        dict: {"profile": str, "bloodwork": str}
    """
    # Ensure markdown is a valid string
    if not isinstance(markdown, str):
        raise TypeError(f"Expected string, got {type(markdown)}")
    
    if not markdown.strip():
        return {
            "profile": "No content detected in document.",
            "bloodwork": "No content detected in document."
        }
    
    # Use simple string keywords (no complex regex) for more robust matching
    profile_keywords_simple = [
        'patient name', 'patient id', 'patient information', 'patient details',
        'name:', 'age:', 'gender', 'sex', 'pregnant', 'pregnancy', 'trimester',
        'date of birth', 'dob', 'd.o.b', 'report date', 'collected', 'collection date'
    ]
    
    lab_keywords_simple = [
        'lab result', 'lab test', 'lab value', 'laboratory',
        'blood test', 'blood work', 'blood analysis',
        'hematology', 'biochemistry', 'serology',
        'rbc', 'wbc', 'hgb', 'hct', 'plt', 'mcv', 'mch', 'mchc',
        'hemoglobin', 'hematocrit', 'platelet',
        'mg/dl', 'g/dl', 'mmol/l', 'u/l',
        'reference range', 'normal range', 'test name', 'parameter', 'result', 'unit'
    ]
    
    try:
        lines = markdown.split('\n')
        profile_lines = []
        bloodwork_lines = []
        current_section = None
        split_point = None
        
        # First pass: Try to find a clear split point
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Simple string matching (no regex) to avoid regex errors
            is_profile_line = any(keyword in line_lower for keyword in profile_keywords_simple)
            is_lab_line = any(keyword in line_lower for keyword in lab_keywords_simple)
            
            # Detect table markers (simple string check)
            has_table = '```' in line or ('|' in line and line.count('|') >= 2)
            
            # If we find lab keywords or tables and haven't set a split point, this is likely where bloodwork starts
            if (is_lab_line or has_table) and split_point is None and i > len(lines) * 0.1:
                # Look back a few lines to see if there's profile info
                lookback_start = max(0, i - 5)
                lookback_context = ' '.join(lines[lookback_start:i]).lower()
                has_profile_context = any(keyword in lookback_context for keyword in profile_keywords_simple)
                
                if not has_profile_context or i > len(lines) * 0.3:
                    split_point = i
                    break
        
        # If we found a split point, use it
        if split_point is not None:
            profile_lines = lines[:split_point]
            bloodwork_lines = lines[split_point:]
        else:
            # Fallback: Use simple heuristic - first 30% is profile, rest is bloodwork
            split_point = max(1, int(len(lines) * 0.3))
            profile_lines = lines[:split_point]
            bloodwork_lines = lines[split_point:]
        
        # Clean up and join
        profile_chunk = '\n'.join(profile_lines).strip()
        bloodwork_chunk = '\n'.join(bloodwork_lines).strip()
        
        # Ensure we have both chunks
        if not profile_chunk:
            profile_chunk = "No profile information detected in document."
        if not bloodwork_chunk:
            bloodwork_chunk = "No lab results detected in document."
        
        return {
            "profile": profile_chunk,
            "bloodwork": bloodwork_chunk
        }
        
    except Exception as e:
        # If chunking fails completely, use simple 50/50 split
        try:
            lines = markdown.split('\n')
            split_point = len(lines) // 2
            return {
                "profile": '\n'.join(lines[:split_point]).strip() or "No profile information detected.",
                "bloodwork": '\n'.join(lines[split_point:]).strip() or "No lab results detected."
            }
        except Exception as fallback_error:
            # Last resort: return the entire document as profile, empty bloodwork
            return {
                "profile": markdown.strip() or "No content detected in document.",
                "bloodwork": "No lab results detected in document."
            }


def extract_pdf_to_chunks(pdf_path: str | Path) -> Dict[str, str]:
    """
    Main function: Extract PDF and return Profile and Bloodwork chunks.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        dict: {"profile": str, "bloodwork": str}
    """
    try:
        # Extract PDF to markdown
        markdown = extract_pdf_to_markdown(pdf_path)
        
        # Validate markdown output
        if not isinstance(markdown, str):
            raise ValueError(f"Expected string from PDF extraction, got {type(markdown)}")
        
        if not markdown.strip():
            raise ValueError("PDF extraction returned empty content. The PDF may be empty or corrupted.")
        
        # Chunk the markdown
        chunks = chunk_medical_report(markdown)
        
        return chunks
        
    except FileNotFoundError as e:
        raise FileNotFoundError(f"PDF file not found: {e}")
    except Exception as e:
        raise RuntimeError(f"Error processing PDF: {str(e)}. Please ensure the PDF is not corrupted and contains readable text.") from e

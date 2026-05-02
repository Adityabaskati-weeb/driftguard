"""bob_analyzer.py

IBM Bob Shell integration for DriftGuard.
Calls Bob in non-interactive mode to analyze code diffs for decay signals.
"""

import subprocess
import json
import re
import time
from typing import Dict, List, Optional
from pathlib import Path


def analyze_file_decay(file_data: Dict) -> Dict:
    """
    Analyze a single file's diff using IBM Bob Shell.
    
    Args:
        file_data: Dict with keys: file_path, language, total_commits, diff_text, 
                   last_modified, commit_hashes
    
    Returns:
        Dict with original file_data plus Bob's analysis:
        - documentation_drift_score: int (0-100)
        - test_drift_score: int (0-100)
        - complexity_growth_score: int (0-100)
        - naming_consistency_score: int (0-100)
        - decay_summary: str
        - top_risk: str
        - recommendation: str
    """
    # Build the analysis prompt
    prompt = _build_analysis_prompt(file_data)
    
    try:
        # Call Bob Shell in non-interactive mode
        result = subprocess.run(
            ['bob', '-p', prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"⚠️  Bob Shell error for {file_data['file_path']}: {result.stderr}")
            return _create_fallback_analysis(file_data, "Bob Shell execution failed")
        
        # Parse Bob's response
        analysis = _parse_bob_response(result.stdout)
        
        if analysis is None:
            print(f"⚠️  Failed to parse Bob response for {file_data['file_path']}")
            return _create_fallback_analysis(file_data, "Response parsing failed")
        
        # Merge with original file data
        result_data = {**file_data, **analysis}
        return result_data
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  Bob Shell timeout for {file_data['file_path']}")
        return _create_fallback_analysis(file_data, "Analysis timeout")
    
    except FileNotFoundError:
        print("❌ Bob Shell not found. Please install IBM Bob CLI.")
        print("   Visit: https://bob.ibm.com")
        return _create_fallback_analysis(file_data, "Bob Shell not installed")
    
    except Exception as e:
        print(f"⚠️  Unexpected error analyzing {file_data['file_path']}: {e}")
        return _create_fallback_analysis(file_data, f"Unexpected error: {str(e)}")


def _build_analysis_prompt(file_data: Dict) -> str:
    """Build the decay analysis prompt for Bob."""
    prompt = f"""You are analyzing a code diff for signs of technical decay. Analyze the following diff and return ONLY a JSON object with this exact structure — no explanation, no markdown code blocks, just the raw JSON:

{{
  "documentation_drift_score": <integer 0-100, where 0=severe drift, 100=no drift>,
  "test_drift_score": <integer 0-100>,
  "complexity_growth_score": <integer 0-100, where 0=severe complexity increase, 100=no growth>,
  "naming_consistency_score": <integer 0-100>,
  "decay_summary": "<2-3 sentence plain English explanation of the main decay signals>",
  "top_risk": "<single most concerning decay pattern observed>",
  "recommendation": "<one specific action to address the highest risk>"
}}

Scoring guide:
- documentation_drift_score: Did logic change without docstring/comment updates? 0=massive undocumented changes, 100=all changes documented
- test_drift_score: Were tests updated when implementation changed? 0=implementation changed, no tests touched, 100=tests updated or added
- complexity_growth_score: Did functions grow longer, add nesting, or gain parameters? 0=severe complexity increase, 100=complexity unchanged or reduced
- naming_consistency_score: Are new identifiers consistent with the existing naming conventions? 0=many inconsistencies, 100=perfectly consistent

File: {file_data['file_path']}
Language: {file_data['language']}
Commits in window: {file_data['total_commits']}

Diff:
{file_data['diff_text']}

Return ONLY the JSON object, nothing else."""
    
    return prompt


def _parse_bob_response(response: str) -> Optional[Dict]:
    """
    Parse Bob's response to extract the JSON analysis.
    Handles cases where Bob wraps JSON in markdown or adds explanation text.
    """
    # Try to find JSON in markdown code blocks first
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, response, re.DOTALL)
    
    if match:
        json_str = match.group(1)
    else:
        # Try to find raw JSON object
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_pattern, response, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            return None
    
    try:
        data = json.loads(json_str)
        
        # Validate and sanitize the response
        validated = _validate_analysis_response(data)
        return validated
        
    except json.JSONDecodeError:
        return None


def _validate_analysis_response(data: Dict) -> Dict:
    """
    Validate Bob's response has all required fields with correct types.
    Fill in defaults if needed.
    """
    required_fields = {
        'documentation_drift_score': 50,
        'test_drift_score': 50,
        'complexity_growth_score': 50,
        'naming_consistency_score': 50,
        'decay_summary': 'Analysis unavailable',
        'top_risk': 'Unable to determine',
        'recommendation': 'Manual review recommended'
    }
    
    validated = {}
    
    for field, default in required_fields.items():
        if field in data:
            value = data[field]
            
            # Ensure scores are integers in range 0-100
            if 'score' in field:
                try:
                    score = int(value)
                    validated[field] = max(0, min(100, score))
                except (ValueError, TypeError):
                    validated[field] = default
            else:
                # String fields
                validated[field] = str(value) if value else default
        else:
            validated[field] = default
    
    return validated


def _create_fallback_analysis(file_data: Dict, reason: str) -> Dict:
    """
    Create a fallback analysis when Bob Shell fails.
    Returns neutral scores with explanation.
    """
    return {
        **file_data,
        'documentation_drift_score': 50,
        'test_drift_score': 50,
        'complexity_growth_score': 50,
        'naming_consistency_score': 50,
        'decay_summary': f'Analysis unavailable: {reason}',
        'top_risk': 'Unable to analyze - manual review needed',
        'recommendation': 'Run analysis again or review manually'
    }


def batch_analyze(file_diffs: List[Dict], delay: float = 2.0) -> List[Dict]:
    """
    Analyze multiple files in batch with progress tracking.
    
    Args:
        file_diffs: List of file diff dicts from git_parser
        delay: Seconds to wait between Bob calls (to avoid rate limits)
    
    Returns:
        List of analysis results (file data + Bob analysis)
    """
    results = []
    total = len(file_diffs)
    
    print(f"\n🤖 Analyzing {total} files with IBM Bob...")
    print("=" * 60)
    
    for i, file_data in enumerate(file_diffs, 1):
        filename = Path(file_data['file_path']).name
        print(f"[{i}/{total}] Analyzing: {filename}...", end=' ', flush=True)
        
        analysis = analyze_file_decay(file_data)
        results.append(analysis)
        
        # Show quick status
        if 'documentation_drift_score' in analysis:
            avg_score = (
                analysis['documentation_drift_score'] +
                analysis['test_drift_score'] +
                analysis['complexity_growth_score'] +
                analysis['naming_consistency_score']
            ) / 4
            status = "✅" if avg_score >= 70 else "⚠️" if avg_score >= 50 else "🔴"
            print(f"{status} (score: {avg_score:.0f})")
        else:
            print("⚠️  (fallback)")
        
        # Rate limiting delay (except for last file)
        if i < total:
            time.sleep(delay)
    
    print("=" * 60)
    print(f"✅ Batch analysis complete: {total} files processed\n")
    
    return results


def test_bob_analyzer():
    """
    Test function to verify Bob Shell integration.
    Creates a sample diff and tests the analysis pipeline.
    """
    print("[TEST] Testing Bob Shell integration...")
    print("-" * 60)
    
    # Sample test data
    test_file = {
        'file_path': 'test/sample.py',
        'language': 'python',
        'total_commits': 3,
        'diff_text': '''@@ -10,6 +10,15 @@ def calculate_total(items):
-def calculate_total(items):
-    total = 0
-    for item in items:
-        total += item
-    return total
+def calculate_total(items, tax_rate=0):
+    # Calculate with tax
+    subtotal = 0
+    for item in items:
+        subtotal += item
+    if tax_rate > 0:
+        subtotal = subtotal * (1 + tax_rate)
+    return subtotal''',
        'last_modified': '2026-05-02T12:00:00Z',
        'commit_hashes': ['abc123', 'def456', 'ghi789']
    }
    
    print(f"Test file: {test_file['file_path']}")
    print(f"Language: {test_file['language']}")
    print(f"Commits: {test_file['total_commits']}")
    print("-" * 60)
    
    # Run analysis
    result = analyze_file_decay(test_file)
    
    print("\n[RESULT] Analysis output:")
    print(f"  Documentation drift: {result.get('documentation_drift_score', 'N/A')}/100")
    print(f"  Test drift: {result.get('test_drift_score', 'N/A')}/100")
    print(f"  Complexity growth: {result.get('complexity_growth_score', 'N/A')}/100")
    print(f"  Naming consistency: {result.get('naming_consistency_score', 'N/A')}/100")
    print(f"\n  Summary: {result.get('decay_summary', 'N/A')}")
    print(f"  Top risk: {result.get('top_risk', 'N/A')}")
    print(f"  Recommendation: {result.get('recommendation', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("[TEST] Complete")


if __name__ == '__main__':
    test_bob_analyzer()

# Made with Bob
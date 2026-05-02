"""bob_analyzer.py

Rule-based code decay analyzer for DriftGuard.
Analyzes file diffs using heuristics (no external APIs/LLMs).
"""

import re
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.models import FileDiff, AnalysisResult
from app.config import Config
from app.baseline_profile import load_baseline, format_baseline_summary
from app.language_prompts import get_language_prompt, get_focus_areas, get_complexity_indicators
from app.db import (
    compute_diff_hash,
    get_cached_analysis,
    save_cached_analysis,
    DEFAULT_DB_PATH
)
from app.rate_limiter import TokenBucketRateLimiter

# Initialize logger
logger = logging.getLogger("driftguard")

# Global baseline cache
_baseline_cache: Optional[Dict] = None

# Global rate limiter instance
_rate_limiter: Optional[TokenBucketRateLimiter] = None


def get_rate_limiter() -> TokenBucketRateLimiter:
    """Get or create the global rate limiter instance.
    
    Returns:
        TokenBucketRateLimiter instance configured from Config
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TokenBucketRateLimiter(
            tokens_per_minute=Config.BOB_RATE_LIMIT_PER_MINUTE,
            burst_capacity=Config.BOB_RATE_LIMIT_BURST
        )
    return _rate_limiter


def set_baseline(repo_path: str) -> None:
    """Load and cache baseline profile for the repository.
    
    Args:
        repo_path: path to repository root
    """
    global _baseline_cache
    _baseline_cache = load_baseline(repo_path)
    
    if _baseline_cache:
        print(f"\n[BASELINE] Loaded baseline profile:")
        print(format_baseline_summary(_baseline_cache))
    else:
        print("\n[BASELINE] No baseline profile found. Scores will use default thresholds.")


def get_baseline() -> Optional[Dict]:
    """Get cached baseline profile."""
    return _baseline_cache


def analyze_file_decay(file_data: Dict, use_cache: bool = True,
                       db_path: str = DEFAULT_DB_PATH) -> Dict:
    """
    Analyze a single file's decay using rule-based heuristics.
    
    Args:
        file_data: Dict with keys: file_path, diff_text, total_commits, language
        use_cache: whether to use cache (default: True, respects Config.CACHE_ENABLED)
        db_path: path to SQLite database file
        
    Returns:
        Dict with decay scores and analysis (AnalysisResult schema)
    """
    diff_text = file_data.get('diff_text', '')
    file_path = file_data.get('file_path', '')
    language = file_data.get('language', 'unknown')
    
    # Check cache if enabled
    if use_cache and Config.CACHE_ENABLED and diff_text:
        diff_hash = compute_diff_hash(diff_text)
        ttl = Config.CACHE_TTL_HOURS if Config.CACHE_TTL_HOURS > 0 else None
        
        cached_result = get_cached_analysis(file_path, diff_hash, ttl, db_path)
        if cached_result:
            # Cache hit - return cached result
            return cached_result
    
    # Cache miss or cache disabled - perform analysis
    # Get baseline for context-aware scoring
    baseline = get_baseline()
    
    # Calculate individual dimension scores
    doc_score = _calculate_documentation_drift_score(diff_text, language)
    test_score = _calculate_test_drift_score(file_path, diff_text)
    complexity_score = _calculate_complexity_growth_score(diff_text, language)
    naming_score = _calculate_naming_consistency_score(diff_text, language)
    
    # Determine top risk and recommendation
    scores = {
        'documentation': doc_score,
        'test_coverage': test_score,
        'complexity': complexity_score,
        'naming': naming_score
    }
    
    lowest_dimension = min(scores.keys(), key=lambda k: scores[k])
    lowest_score = scores[lowest_dimension]
    
    top_risk, recommendation = _generate_risk_and_recommendation(
        lowest_dimension, lowest_score, file_path, language
    )
    
    # Generate decay summary
    decay_summary = _generate_decay_summary(scores, file_path)
    
    # Build result dict matching AnalysisResult schema
    result: AnalysisResult = {
        'file_path': file_data.get('file_path', ''),
        'language': file_data.get('language', 'unknown'),
        'total_commits': file_data.get('total_commits', 0),
        'diff_text': diff_text,
        'last_modified': file_data.get('last_modified', ''),
        'commit_hashes': file_data.get('commit_hashes', []),
        'documentation_drift_score': doc_score,
        'test_drift_score': test_score,
        'complexity_growth_score': complexity_score,
        'naming_consistency_score': naming_score,
        'decay_summary': decay_summary,
        'top_risk': top_risk,
        'recommendation': recommendation,
    }
    
    # Save to cache if enabled
    if use_cache and Config.CACHE_ENABLED and diff_text:
        diff_hash = compute_diff_hash(diff_text)
        save_cached_analysis(file_path, diff_hash, language, result, db_path)
    
    return result


def _analyze_file_with_rate_limit(file_data: Dict, rate_limiter: TokenBucketRateLimiter,
                                   index: int, total: int) -> tuple:
    """
    Analyze a single file with rate limiting (thread-safe).
    
    Args:
        file_data: File data dict from git_parser
        rate_limiter: Shared rate limiter instance
        index: File index (for logging)
        total: Total number of files
        
    Returns:
        Tuple of (index, file_path, result or None, error or None)
    """
    file_path = file_data.get('file_path', 'unknown')
    
    try:
        # Acquire token (blocks if necessary) - thread-safe
        rate_limiter.acquire(tokens=1)
        
        # Perform analysis
        result = analyze_file_decay(file_data)
        
        # Calculate average score for logging
        avg_score = (
            result['documentation_drift_score'] +
            result['test_drift_score'] +
            result['complexity_growth_score'] +
            result['naming_consistency_score']
        ) / 4
        
        return (index, file_path, result, None, avg_score)
        
    except Exception as e:
        logger.error(f"Analysis failed for {file_path}: {e}")
        return (index, file_path, None, str(e), None)


def batch_analyze(file_diffs: List[Dict], max_workers: Optional[int] = None) -> List[Dict]:
    """
    Analyze multiple files in parallel with progress reporting and rate limiting.
    
    Uses ThreadPoolExecutor to parallelize file analysis while maintaining:
    - Thread-safe rate limiting across all workers
    - Deterministic output order (sorted by file_path)
    - Progress reporting
    
    Args:
        file_diffs: List of file_data dicts from git_parser
        max_workers: Number of parallel workers (default: Config.MAX_WORKERS)
        
    Returns:
        List of AnalysisResult dicts, sorted by file_path for deterministic output
    """
    if max_workers is None:
        max_workers = Config.MAX_WORKERS
    
    total = len(file_diffs)
    
    # Get rate limiter instance (thread-safe)
    rate_limiter = get_rate_limiter()
    
    print(f"\n[ANALYZER] Analyzing {total} files with {max_workers} parallel workers...")
    print(f"[ANALYZER] Rate limit: {Config.BOB_RATE_LIMIT_PER_MINUTE} calls/min, burst: {Config.BOB_RATE_LIMIT_BURST}")
    print("-" * 60)
    
    # Store results with their original index for deterministic ordering
    results_map = {}
    completed = 0
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {
            executor.submit(_analyze_file_with_rate_limit, file_data, rate_limiter, i, total): i
            for i, file_data in enumerate(file_diffs)
        }
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_index):
            index, file_path, result, error, avg_score = future.result()
            completed += 1
            
            if result is not None:
                results_map[index] = result
                print(f"[{completed}/{total}] OK {file_path} (avg: {avg_score:.1f}/100)")
            else:
                print(f"[{completed}/{total}] FAIL {file_path} - ERROR: {error}")
    
    print("-" * 60)
    
    # Sort results by file_path for deterministic output
    results = [results_map[i] for i in sorted(results_map.keys())]
    results.sort(key=lambda x: x.get('file_path', ''))
    
    print(f"[ANALYZER] Completed: {len(results)}/{total} files analyzed")
    print(f"[ANALYZER] Results sorted by file_path for deterministic output\n")
    
    return results


# ============================================================================
# DIMENSION SCORING FUNCTIONS
# ============================================================================

def _calculate_documentation_drift_score(diff_text: str, language: str) -> int:
    """
    Score: 0-100 (higher = better documentation practices)
    
    Rule: If added 50+ lines with 0 comments/docstrings → 20, else 70+
    Uses baseline docstring coverage to adjust expectations.
    Language-specific patterns applied based on language_prompts.
    """
    lines = diff_text.split('\n')
    added_lines = [line for line in lines if line.startswith('+') and not line.startswith('+++')]
    
    # Count added code lines (exclude empty lines)
    added_code_lines = [line for line in added_lines if line.strip() and len(line.strip()) > 1]
    added_count = len(added_code_lines)
    
    if added_count == 0:
        return 100  # No changes, perfect score
    
    # Get baseline for context
    baseline = get_baseline()
    baseline_doc_coverage = baseline.get('docstring_coverage_pct', 50.0) if baseline else 50.0
    
    # Count added comments/docstrings with language-specific patterns
    comment_patterns = {
        'python': [r'^\+\s*#', r'^\+\s*"""', r"^\+\s*'''"],
        'javascript': [r'^\+\s*//', r'^\+\s*/\*', r'^\+\s*\*'],
        'typescript': [r'^\+\s*//', r'^\+\s*/\*', r'^\+\s*\*'],
        'java': [r'^\+\s*//', r'^\+\s*/\*', r'^\+\s*\*'],
        'go': [r'^\+\s*//', r'^\+\s*/\*', r'^\+\s*\*'],
        'ruby': [r'^\+\s*#', r'^\+\s*=begin'],
    }
    
    patterns = comment_patterns.get(language, [r'^\+\s*#', r'^\+\s*//'])
    comment_count = 0
    
    for line in added_lines:
        for pattern in patterns:
            if re.search(pattern, line):
                comment_count += 1
                break
    
    # Calculate documentation ratio
    doc_ratio = comment_count / added_count if added_count > 0 else 0
    
    # Apply scoring rules with baseline adjustment
    threshold = Config.RULE_DOC_DRIFT_THRESHOLD_ADDED_LINES
    
    # Adjust expectations based on baseline
    # If repo has low baseline coverage, be more lenient
    if baseline_doc_coverage < 30:
        leniency = 10
    elif baseline_doc_coverage < 50:
        leniency = 5
    else:
        leniency = 0
    
    if added_count >= threshold and comment_count == 0:
        return max(20, 20 + leniency)  # Large change with no documentation
    elif added_count >= threshold and doc_ratio < 0.05:
        return max(40, 40 + leniency)  # Large change with minimal documentation
    elif doc_ratio < 0.1:
        return max(60, 60 + leniency)  # Some documentation but below 10%
    elif doc_ratio < 0.2:
        return 75  # Decent documentation (10-20%)
    else:
        return 90  # Good documentation (20%+)


def _calculate_test_drift_score(file_path: str, diff_text: str) -> int:
    """
    Score: 0-100 (higher = better test coverage)
    
    Rule: If implementation changed but no test touched → 30, else 60+
    """
    is_test_file = _is_test_file(file_path)
    
    # If this is a test file, give high score
    if is_test_file:
        return 85
    
    # Check if diff mentions test-related changes
    test_keywords = ['test', 'spec', 'mock', 'assert', 'expect', 'describe', 'it(']
    has_test_mentions = any(keyword in diff_text.lower() for keyword in test_keywords)
    
    # Count lines changed
    lines = diff_text.split('\n')
    added_lines = len([l for l in lines if l.startswith('+') and not l.startswith('+++')])
    deleted_lines = len([l for l in lines if l.startswith('-') and not l.startswith('---')])
    total_changes = added_lines + deleted_lines
    
    # Scoring logic
    if total_changes == 0:
        return 100  # No changes
    
    if total_changes > 50 and not has_test_mentions:
        return 30  # Large implementation change with no test mentions
    elif total_changes > 20 and not has_test_mentions:
        return 50  # Medium change with no test mentions
    elif has_test_mentions:
        return 75  # Test-related changes detected
    else:
        return 65  # Small change, acceptable


def _calculate_complexity_growth_score(diff_text: str, language: str) -> int:
    """
    Score: 0-100 (higher = better complexity management)
    
    Rule: Count indentation/nesting increases. High increase → 40, else 70+
    Uses language-specific thresholds from Config.LANGUAGE_THRESHOLDS.
    """
    lines = diff_text.split('\n')
    added_lines = [line for line in lines if line.startswith('+') and not line.startswith('+++')]
    
    if not added_lines:
        return 100  # No changes
    
    # Get language-specific thresholds
    lang_thresholds = Config.LANGUAGE_THRESHOLDS.get(language, Config.LANGUAGE_THRESHOLDS.get('python', {}))
    max_function_lines = lang_thresholds.get('max_function_lines', 50)
    max_nesting_depth = lang_thresholds.get('max_nesting_depth', 4)
    complexity_threshold = lang_thresholds.get('complexity_threshold', 150)
    
    # Measure nesting depth increases
    max_nesting = 0
    avg_nesting = 0
    nesting_samples = []
    
    for line in added_lines:
        if not line.strip():
            continue
        
        # Count leading whitespace (indentation)
        stripped = line.lstrip('+')
        if not stripped.strip():
            continue
            
        indent = len(stripped) - len(stripped.lstrip())
        
        # Estimate nesting level (4 spaces or 1 tab = 1 level)
        if '\t' in stripped[:indent]:
            nesting_level = stripped[:indent].count('\t')
        else:
            nesting_level = indent // 4
        
        nesting_samples.append(nesting_level)
        max_nesting = max(max_nesting, nesting_level)
    
    if nesting_samples:
        avg_nesting = sum(nesting_samples) / len(nesting_samples)
    
    # Check for long functions (heuristic: many consecutive added lines)
    consecutive_adds = 0
    max_consecutive = 0
    
    for line in lines:
        if line.startswith('+') and not line.startswith('+++'):
            consecutive_adds += 1
            max_consecutive = max(max_consecutive, consecutive_adds)
        else:
            consecutive_adds = 0
    
    # Scoring based on language-specific complexity indicators
    if max_nesting > max_nesting_depth + 2:  # Very deep nesting
        return 30
    elif max_nesting > max_nesting_depth:  # Deep nesting
        return 50
    elif max_consecutive > max_function_lines * 2:  # Very long function addition
        return 45
    elif max_consecutive > max_function_lines:  # Long function addition
        return 60
    elif avg_nesting > max_nesting_depth - 1:  # Moderate average nesting
        return 70
    else:
        return 85  # Good complexity management


def _calculate_naming_consistency_score(diff_text: str, language: str) -> int:
    """
    Score: 0-100 (higher = better naming consistency)
    
    Rule: Look for snake_case vs camelCase inconsistencies → 50-80 based on violations
    Uses language-specific naming conventions from language_prompts.
    """
    lines = diff_text.split('\n')
    added_lines = [line for line in lines if line.startswith('+') and not line.startswith('+++')]
    
    if not added_lines:
        return 100  # No changes
    
    # Extract identifiers from added lines
    # Pattern: variable/function names (alphanumeric + underscore)
    identifier_pattern = r'\b([a-z_][a-z0-9_]*)\b'
    identifiers = []
    
    for line in added_lines:
        # Skip comments and strings
        if '#' in line or '//' in line or '/*' in line or '"' in line or "'" in line:
            continue
        
        matches = re.findall(identifier_pattern, line.lower())
        identifiers.extend(matches)
    
    if not identifiers:
        return 100  # No identifiers found
    
    # Analyze naming patterns
    snake_case_count = sum(1 for name in identifiers if '_' in name and name.islower())
    camel_case_count = sum(1 for name in identifiers if '_' not in name and any(c.isupper() for c in name))
    
    # Get expected style from baseline or language defaults
    baseline = get_baseline()
    if baseline and baseline.get('dominant_naming_style'):
        style = baseline['dominant_naming_style']
    else:
        # Language-specific conventions from language_prompts
        expected_style = {
            'python': 'snake_case',
            'javascript': 'camelCase',
            'typescript': 'camelCase',
            'java': 'camelCase',
            'go': 'camelCase',
            'ruby': 'snake_case',
        }
        style = expected_style.get(language, 'snake_case')
    
    # Calculate consistency
    total_styled = snake_case_count + camel_case_count
    if total_styled == 0:
        return 80  # No clear style detected
    
    if style == 'snake_case':
        consistency_ratio = snake_case_count / total_styled
    else:
        consistency_ratio = camel_case_count / total_styled
    
    # Check for magic numbers (numbers in code that should be constants)
    magic_number_pattern = r'\b\d{2,}\b'  # Numbers with 2+ digits
    magic_numbers = re.findall(magic_number_pattern, '\n'.join(added_lines))
    magic_count = len([n for n in magic_numbers if int(n) not in [0, 1, 10, 100, 1000]])
    
    # Scoring
    if consistency_ratio < 0.5:
        score = 50  # Highly inconsistent
    elif consistency_ratio < 0.7:
        score = 65  # Somewhat inconsistent
    elif consistency_ratio < 0.85:
        score = 75  # Mostly consistent
    else:
        score = 85  # Very consistent
    
    # Penalize for magic numbers
    if magic_count > 5:
        score -= 15
    elif magic_count > 2:
        score -= 10
    
    return max(50, min(100, score))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file based on path/name."""
    test_indicators = ['test', 'spec', '__tests__', 'tests/']
    return any(indicator in file_path.lower() for indicator in test_indicators)


def _generate_risk_and_recommendation(dimension: str, score: int, file_path: str, language: str = 'unknown') -> tuple:
    """Generate top risk and recommendation based on lowest scoring dimension.
    
    Args:
        dimension: The dimension with the lowest score
        score: The score value
        file_path: Path to the file
        language: Programming language for context-specific recommendations
    """
    # Get language-specific focus areas for better recommendations
    focus_areas = get_focus_areas(language)
    
    risk_templates = {
        'documentation': (
            f"Documentation drift detected in {file_path}",
            "Add inline comments and docstrings to explain complex logic"
        ),
        'test_coverage': (
            f"Test coverage gap in {file_path}",
            "Write unit tests for new functionality or update existing tests"
        ),
        'complexity': (
            f"Complexity growth in {file_path}",
            "Refactor deeply nested code and break down long functions"
        ),
        'naming': (
            f"Naming inconsistency in {file_path}",
            "Standardize variable/function names to match project conventions"
        ),
    }
    
    if score < 40:
        severity = "CRITICAL"
    elif score < 60:
        severity = "HIGH"
    else:
        severity = "MODERATE"
    
    risk, rec = risk_templates.get(dimension, ("Unknown risk", "Review code changes"))
    return f"[{severity}] {risk}", rec


def _generate_decay_summary(scores: Dict[str, int], file_path: str) -> str:
    """Generate 2-3 sentence summary of decay analysis."""
    avg_score = sum(scores.values()) / len(scores)
    lowest_dim = min(scores.keys(), key=lambda k: scores[k])
    lowest_score = scores[lowest_dim]
    
    if avg_score >= 75:
        health = "healthy"
    elif avg_score >= 60:
        health = "showing minor decay"
    elif avg_score >= 40:
        health = "showing significant decay"
    else:
        health = "in critical condition"
    
    summary = f"File {file_path} is {health} with an average decay score of {avg_score:.1f}/100. "
    summary += f"The weakest dimension is {lowest_dim.replace('_', ' ')} (score: {lowest_score}/100). "
    
    if lowest_score < 50:
        summary += "Immediate attention required to prevent further degradation."
    elif lowest_score < 70:
        summary += "Consider addressing this area in the next refactoring cycle."
    else:
        summary += "Continue monitoring for future changes."
    
    return summary


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_bob_analyzer():
    """Test the analyzer with sample data."""
    print("\n[TEST] Testing bob_analyzer with sample data...")
    print("-" * 60)
    
    # Sample file data
    sample_diff = """
@@ -10,5 +10,25 @@ def calculate_total(items):
-def old_function():
-    pass
+def new_complex_function(data):
+    result = []
+    for item in data:
+        if item > 0:
+            for subitem in item.values():
+                if subitem:
+                    result.append(subitem * 100)
+    return result
+
+def anotherFunction(x):
+    return x * 42
"""
    
    sample_file = {
        'file_path': 'app/sample.py',
        'language': 'python',
        'total_commits': 3,
        'diff_text': sample_diff,
        'last_modified': '2026-05-02T10:00:00Z',
        'commit_hashes': ['abc123', 'def456', 'ghi789']
    }
    
    # Analyze single file
    result = analyze_file_decay(sample_file)
    
    print(f"\nFile: {result['file_path']}")
    print(f"Language: {result['language']}")
    print(f"Total commits: {result['total_commits']}")
    print(f"\nDecay Scores:")
    print(f"  Documentation drift: {result['documentation_drift_score']}/100")
    print(f"  Test drift: {result['test_drift_score']}/100")
    print(f"  Complexity growth: {result['complexity_growth_score']}/100")
    print(f"  Naming consistency: {result['naming_consistency_score']}/100")
    print(f"\nTop Risk: {result['top_risk']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"\nSummary: {result['decay_summary']}")
    
    print("\n" + "-" * 60)
    print("[TEST] Analyzer test complete!")


if __name__ == '__main__':
    test_bob_analyzer()

# Made with Bob

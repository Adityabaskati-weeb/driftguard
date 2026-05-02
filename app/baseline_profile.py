"""baseline_profile.py

Repository baseline profiling for DriftGuard.
Scans repository to establish baseline metrics for relative scoring.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter


def build_baseline(repo_path: str) -> Dict:
    """Scan repository and compute baseline profile metrics.
    
    Analyzes Python files (initially) to compute:
    - Average function length (lines)
    - Docstring coverage percentage
    - Test file ratio (test files / total files)
    - Dominant naming style (snake_case vs camelCase)
    
    Args:
        repo_path: path to repository root
    
    Returns:
        Dict with baseline metrics
    """
    repo = Path(repo_path)
    baseline_dir = repo / ".driftguard"
    baseline_dir.mkdir(exist_ok=True)
    
    # Collect Python files
    python_files = list(repo.rglob("*.py"))
    
    # Filter out virtual environments and common ignore patterns
    python_files = [
        f for f in python_files
        if not any(part in f.parts for part in [
            'venv', 'env', '.venv', 'virtualenv',
            'node_modules', '.git', '__pycache__',
            'site-packages', 'dist', 'build'
        ])
    ]
    
    if not python_files:
        # Return default baseline if no Python files found
        baseline = {
            'language': 'python',
            'total_files': 0,
            'avg_function_length': 10.0,
            'docstring_coverage_pct': 0.0,
            'test_file_ratio': 0.0,
            'dominant_naming_style': 'snake_case',
            'total_functions': 0,
            'total_classes': 0,
            'files_analyzed': 0
        }
        _save_baseline(baseline, repo_path)
        return baseline
    
    # Analyze files
    total_functions = 0
    total_function_lines = 0
    functions_with_docstrings = 0
    total_classes = 0
    classes_with_docstrings = 0
    test_files = 0
    naming_styles = Counter()
    files_analyzed = 0
    
    for py_file in python_files:
        try:
            # Check if test file
            if _is_test_file(str(py_file)):
                test_files += 1
            
            # Parse AST
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            files_analyzed += 1
            
            # Analyze functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    
                    # Calculate function length
                    if (hasattr(node, 'end_lineno') and hasattr(node, 'lineno') and
                        node.end_lineno is not None and node.lineno is not None):
                        func_length = node.end_lineno - node.lineno + 1
                        total_function_lines += func_length
                    
                    # Check for docstring
                    if ast.get_docstring(node):
                        functions_with_docstrings += 1
                    
                    # Analyze naming style
                    naming_styles[_detect_naming_style(node.name)] += 1
                
                elif isinstance(node, ast.ClassDef):
                    total_classes += 1
                    
                    # Check for docstring
                    if ast.get_docstring(node):
                        classes_with_docstrings += 1
                    
                    # Analyze naming style
                    naming_styles[_detect_naming_style(node.name)] += 1
        
        except (SyntaxError, UnicodeDecodeError, Exception):
            # Skip files that can't be parsed
            continue
    
    # Calculate metrics
    avg_function_length = (
        total_function_lines / total_functions
        if total_functions > 0 else 10.0
    )
    
    total_documented = functions_with_docstrings + classes_with_docstrings
    total_definitions = total_functions + total_classes
    docstring_coverage_pct = (
        (total_documented / total_definitions * 100)
        if total_definitions > 0 else 0.0
    )
    
    test_file_ratio = (
        test_files / len(python_files)
        if python_files else 0.0
    )
    
    # Determine dominant naming style
    if naming_styles:
        dominant_style = naming_styles.most_common(1)[0][0]
    else:
        dominant_style = 'snake_case'
    
    baseline = {
        'language': 'python',
        'total_files': len(python_files),
        'avg_function_length': round(avg_function_length, 1),
        'docstring_coverage_pct': round(docstring_coverage_pct, 1),
        'test_file_ratio': round(test_file_ratio, 3),
        'dominant_naming_style': dominant_style,
        'total_functions': total_functions,
        'total_classes': total_classes,
        'files_analyzed': files_analyzed,
        'test_files': test_files
    }
    
    # Save to .driftguard/baseline.json
    _save_baseline(baseline, repo_path)
    
    return baseline


def load_baseline(repo_path: str) -> Optional[Dict]:
    """Load baseline profile from .driftguard/baseline.json.
    
    Args:
        repo_path: path to repository root
    
    Returns:
        Dict with baseline metrics or None if not found
    """
    baseline_file = Path(repo_path) / ".driftguard" / "baseline.json"
    
    if not baseline_file.exists():
        return None
    
    try:
        with open(baseline_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_baseline(baseline: Dict, repo_path: str) -> None:
    """Save baseline profile to .driftguard/baseline.json."""
    baseline_dir = Path(repo_path) / ".driftguard"
    baseline_dir.mkdir(exist_ok=True)
    
    baseline_file = baseline_dir / "baseline.json"
    
    with open(baseline_file, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2)


def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file based on path/name."""
    test_indicators = ['test_', '_test.py', 'tests/', '/test/', 'spec_', '_spec.py']
    return any(indicator in file_path.lower() for indicator in test_indicators)


def _detect_naming_style(name: str) -> str:
    """Detect naming style of an identifier.
    
    Returns:
        'snake_case', 'camelCase', 'PascalCase', or 'unknown'
    """
    if not name or name.startswith('_'):
        # Strip leading underscores for analysis
        name = name.lstrip('_')
    
    if not name:
        return 'unknown'
    
    has_underscore = '_' in name
    has_uppercase = any(c.isupper() for c in name)
    starts_uppercase = name[0].isupper()
    
    if has_underscore and not has_uppercase:
        return 'snake_case'
    elif has_uppercase and not has_underscore:
        if starts_uppercase:
            return 'PascalCase'
        else:
            return 'camelCase'
    else:
        return 'unknown'


def format_baseline_summary(baseline: Dict) -> str:
    """Format baseline profile as a human-readable summary.
    
    Args:
        baseline: baseline dict from load_baseline()
    
    Returns:
        Multi-line string summary
    """
    if not baseline:
        return "No baseline profile available."
    
    summary = f"""Repository Baseline Profile:
- Language: {baseline.get('language', 'unknown')}
- Total Files: {baseline.get('total_files', 0)}
- Files Analyzed: {baseline.get('files_analyzed', 0)}
- Total Functions: {baseline.get('total_functions', 0)}
- Total Classes: {baseline.get('total_classes', 0)}
- Avg Function Length: {baseline.get('avg_function_length', 0)} lines
- Docstring Coverage: {baseline.get('docstring_coverage_pct', 0)}%
- Test File Ratio: {baseline.get('test_file_ratio', 0):.1%}
- Dominant Naming Style: {baseline.get('dominant_naming_style', 'unknown')}
"""
    return summary


# Made with Bob
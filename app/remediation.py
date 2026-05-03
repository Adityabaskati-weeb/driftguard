"""remediation.py

Generate actionable remediation suggestions for files with decay issues.
Uses Bob Shell to analyze files and suggest specific fixes.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional
import sqlite3


def sanitize_filename(file_path: str) -> str:
    """Convert file path to safe filename for remediation output.
    
    Args:
        file_path: Original file path (e.g., "app/main.py")
        
    Returns:
        Sanitized filename (e.g., "app_main_py")
    """
    # Replace path separators and special characters
    sanitized = file_path.replace('/', '_').replace('\\', '_').replace('.', '_')
    # Remove any remaining special characters
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', sanitized)
    return sanitized


def generate_remediation(file_path: str, file_content: str, analysis: dict, db_conn: sqlite3.Connection) -> str:
    """Generate remediation suggestions using Bob Shell.
    
    Args:
        file_path: Path to the file being analyzed
        file_content: Full content of the file
        analysis: Analysis dict with scores and decay information
        db_conn: Database connection (for future use)
        
    Returns:
        Path to the generated remediation markdown file
    """
    # Extract scores and information
    health_score = analysis.get('health_score', 0)
    doc_score = analysis.get('documentation_drift_score', 0)
    test_score = analysis.get('test_drift_score', 0)
    complexity_score = analysis.get('complexity_growth_score', 0)
    naming_score = analysis.get('naming_consistency_score', 0)
    decay_summary = analysis.get('decay_summary', 'No summary available')
    language = analysis.get('language', 'unknown')
    
    # Build decay issues summary
    decay_issues = []
    if doc_score < 70:
        decay_issues.append(f"- Documentation drift (score: {doc_score}/100)")
    if test_score < 70:
        decay_issues.append(f"- Test coverage gaps (score: {test_score}/100)")
    if complexity_score < 70:
        decay_issues.append(f"- Complexity growth (score: {complexity_score}/100)")
    if naming_score < 70:
        decay_issues.append(f"- Naming inconsistency (score: {naming_score}/100)")
    
    decay_issues_text = "\n".join(decay_issues) if decay_issues else "- No major issues detected"
    
    # Construct prompt for Bob
    prompt = f"""File: {file_path}
Current health score: {health_score}/100
Language: {language}

Decay issues:
{decay_issues_text}

Here is the file content:
```
{file_content}
```

Please generate fixes in Markdown format:

## 1. Docstring Fixes
For every function/class missing a docstring, write the docstring to add. Use the repo's baseline docstring style.

## 2. Test Stubs
For every function without corresponding test coverage, write a pytest test stub (function signature + TODO body).

## 3. Refactor Suggestion
For the most complex function (highest nesting/line count), suggest a specific refactoring approach with code example.

## 4. Priority Ranking
Rank fixes by impact: which docstring/test/refactor would improve the score most?"""
    
    # Call Bob Shell
    try:
        # Use subprocess to call Bob Shell
        result = subprocess.run(
            ['bob', 'shell', '--prompt', prompt],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        if result.returncode == 0:
            remediation_content = result.stdout
        else:
            # If Bob fails, generate a basic remediation
            remediation_content = _generate_fallback_remediation(
                file_path, health_score, doc_score, test_score, 
                complexity_score, naming_score, decay_summary
            )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        # Bob not available or timeout - use fallback
        remediation_content = _generate_fallback_remediation(
            file_path, health_score, doc_score, test_score, 
            complexity_score, naming_score, decay_summary
        )
    
    # Save to remediation directory
    remediation_dir = Path("remediation")
    remediation_dir.mkdir(exist_ok=True)
    
    sanitized_name = sanitize_filename(file_path)
    output_path = remediation_dir / f"{sanitized_name}_remediation.md"
    
    # Write remediation file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Remediation Plan: {file_path}\n\n")
        f.write(f"**Generated:** {_get_timestamp()}\n\n")
        f.write(f"**Health Score:** {health_score}/100\n\n")
        f.write(f"**Language:** {language}\n\n")
        f.write("---\n\n")
        f.write(remediation_content)
    
    return str(output_path)


def _generate_fallback_remediation(file_path: str, health_score: int, 
                                   doc_score: int, test_score: int,
                                   complexity_score: int, naming_score: int,
                                   decay_summary: str) -> str:
    """Generate basic remediation when Bob is not available.
    
    Args:
        file_path: Path to the file
        health_score: Overall health score
        doc_score: Documentation score
        test_score: Test coverage score
        complexity_score: Complexity score
        naming_score: Naming consistency score
        decay_summary: Decay summary text
        
    Returns:
        Markdown formatted remediation content
    """
    content = f"""## Summary

{decay_summary}

## Recommended Actions

"""
    
    # Add specific recommendations based on scores
    if doc_score < 70:
        content += """### 1. Documentation Improvements

**Priority: HIGH**

- Add docstrings to all public functions and classes
- Include parameter descriptions and return types
- Document complex logic with inline comments
- Follow PEP 257 docstring conventions (for Python)

**Example:**
```python
def calculate_total(items: list) -> float:
    \"\"\"Calculate the total sum of items with tax.
    
    Args:
        items: List of item prices
        
    Returns:
        Total sum including 10% tax
    \"\"\"
    return sum(items) * 1.1
```

"""
    
    if test_score < 70:
        content += """### 2. Test Coverage

**Priority: HIGH**

- Write unit tests for all public functions
- Aim for at least 80% code coverage
- Include edge cases and error conditions
- Use pytest fixtures for common test data

**Example Test Stub:**
```python
def test_calculate_total():
    \"\"\"Test calculate_total function.\"\"\"
    # TODO: Implement test cases
    # - Test with empty list
    # - Test with single item
    # - Test with multiple items
    # - Test with negative values
    pass
```

"""
    
    if complexity_score < 70:
        content += """### 3. Complexity Reduction

**Priority: MEDIUM**

- Break down long functions (>50 lines) into smaller ones
- Reduce nesting depth (max 4 levels)
- Extract complex conditions into named variables
- Consider using early returns to reduce nesting

**Refactoring Pattern:**
```python
# Before: Deeply nested
def process_data(data):
    if data:
        for item in data:
            if item.valid:
                if item.value > 0:
                    # process...
                    pass

# After: Early returns and extraction
def process_data(data):
    if not data:
        return
    
    for item in data:
        if not item.valid or item.value <= 0:
            continue
        process_valid_item(item)

def process_valid_item(item):
    # Extracted logic
    pass
```

"""
    
    if naming_score < 70:
        content += """### 4. Naming Consistency

**Priority: LOW**

- Use consistent naming convention (snake_case for Python)
- Replace magic numbers with named constants
- Use descriptive variable names (avoid single letters except in loops)
- Follow language-specific conventions

**Example:**
```python
# Before
def calc(x, y):
    return x * 100 + y * 50

# After
PRICE_PER_UNIT = 100
SHIPPING_COST = 50

def calculate_order_total(units: int, shipments: int) -> int:
    return units * PRICE_PER_UNIT + shipments * SHIPPING_COST
```

"""
    
    # Add priority ranking
    content += """## Priority Ranking

Based on the current scores, here's the recommended order of fixes:

"""
    
    priorities = []
    if doc_score < 70:
        priorities.append(f"1. **Documentation** (score: {doc_score}/100) - Highest impact on maintainability")
    if test_score < 70:
        priorities.append(f"2. **Test Coverage** (score: {test_score}/100) - Critical for reliability")
    if complexity_score < 70:
        priorities.append(f"3. **Complexity** (score: {complexity_score}/100) - Improves readability")
    if naming_score < 70:
        priorities.append(f"4. **Naming** (score: {naming_score}/100) - Enhances code clarity")
    
    if priorities:
        content += "\n".join(priorities)
    else:
        content += "No critical issues found. Continue monitoring for future changes.\n"
    
    content += "\n\n---\n\n"
    content += "**Note:** This is an automated remediation plan. Review and adapt suggestions based on your project's specific needs.\n"
    
    return content


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def generate_remediations_for_files(scored_files: list, repo_path: str, db_conn: sqlite3.Connection) -> int:
    """Generate remediation files for CRITICAL and AT_RISK files.
    
    Args:
        scored_files: List of scored file dicts
        repo_path: Path to the repository
        db_conn: Database connection
        
    Returns:
        Number of remediation files generated
    """
    count = 0
    
    # Filter for CRITICAL and AT_RISK files
    problematic_files = [
        f for f in scored_files 
        if f.get('status') in ['CRITICAL', 'AT_RISK']
    ]
    
    if not problematic_files:
        print("\n[+] No CRITICAL or AT_RISK files found. No remediation needed.")
        return 0
    
    print(f"\n[*] Generating remediation for {len(problematic_files)} files...")
    print("-" * 60)
    
    for file_data in problematic_files:
        file_path = file_data.get('file_path', '')
        status = file_data.get('status', 'UNKNOWN')
        health_score = file_data.get('health_score', 0)
        
        print(f"[{status}] {file_path} (score: {health_score}/100)")
        
        # Read file content
        full_path = Path(repo_path) / file_path
        try:
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            else:
                print(f"  [!] File not found: {full_path}")
                continue
        except Exception as e:
            print(f"  [!] Error reading file: {e}")
            continue
        
        # Generate remediation
        try:
            output_path = generate_remediation(file_path, file_content, file_data, db_conn)
            print(f"  [+] Remediation saved: {output_path}")
            count += 1
        except Exception as e:
            print(f"  [ERROR] Error generating remediation: {e}")
    
    print("-" * 60)
    return count

# Made with Bob

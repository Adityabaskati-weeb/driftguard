"""Git parser module for DriftGuard.

Extracts file diffs from a Git repository over a specified time window.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict

try:
    from git import Repo, GitCommandError, InvalidGitRepositoryError
except ImportError:
    raise ImportError("GitPython is required. Install with: pip install gitpython")


# Supported file extensions
SUPPORTED_EXTENSIONS = {'.py', '.js', '.ts', '.java'}

# Language mapping
EXTENSION_TO_LANGUAGE = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.java': 'java',
}

# Maximum lines for diff_text
MAX_DIFF_LINES = 150
TRUNCATE_HEAD_LINES = 75
TRUNCATE_TAIL_LINES = 75


def get_file_diffs(repo_path: str, days: int) -> List[Dict]:
    """
    Extract file diffs from a Git repository over the last N days.
    
    Args:
        repo_path: Path to the git repository (absolute or relative)
        days: Number of days to look back in history
        
    Returns:
        List of dictionaries, each containing:
        - file_path: Relative path to the file
        - language: Programming language (inferred from extension)
        - total_commits: Number of commits that modified this file
        - diff_text: Concatenated unified diff (max 150 lines)
        - last_modified: ISO timestamp of most recent commit
        - commit_hashes: List of commit hashes that touched this file
        
    Returns empty list if no files were modified in the time window.
    
    Raises:
        InvalidGitRepositoryError: If repo_path is not a valid git repository
        GitCommandError: If git operations fail
    """
    # Resolve repository path
    repo_path = os.path.abspath(repo_path)
    
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        raise InvalidGitRepositoryError(f"Not a valid git repository: {repo_path}")
    
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Collect file changes grouped by file path
    file_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'commits': [],
        'diffs': [],
        'last_modified': None,
    })
    
    # Iterate through commits in the time window
    try:
        commits = list(repo.iter_commits('HEAD', since=cutoff_date))
    except GitCommandError as e:
        # Handle empty repository or other git errors
        print(f"Warning: Git command error: {e}")
        return []
    
    if not commits:
        return []
    
    for commit in commits:
        commit_date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        
        # Get parent commit for diff (handle initial commit case)
        if commit.parents:
            parent = commit.parents[0]
            try:
                diffs = parent.diff(commit, create_patch=True)
            except GitCommandError:
                continue
        else:
            # Initial commit - compare against empty tree
            try:
                diffs = commit.diff(None, create_patch=True)
            except GitCommandError:
                continue
        
        # Process each changed file
        for diff in diffs:
            # Get file path (handle renames)
            if diff.b_path:
                file_path = diff.b_path
            elif diff.a_path:
                file_path = diff.a_path
            else:
                continue
            
            # Filter by extension
            ext = Path(file_path).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            
            # Skip binary files (with error handling for missing blobs)
            try:
                if diff.b_blob and diff.b_blob.size > 1024 * 1024:  # Skip files > 1MB
                    continue
            except (ValueError, AttributeError):
                # Blob might be missing or corrupted, skip it
                continue
            
            try:
                # Get diff text
                if diff.diff:
                    if isinstance(diff.diff, bytes):
                        diff_text = diff.diff.decode('utf-8', errors='ignore')
                    else:
                        diff_text = str(diff.diff)
                else:
                    diff_text = ""
            except (AttributeError, UnicodeDecodeError, ValueError):
                # Skip if we can't decode the diff or blob is missing
                continue
            
            # Skip if diff is empty or binary
            if not diff_text or diff_text.startswith('Binary files'):
                continue
            
            # Store file data
            file_data[file_path]['commits'].append(commit.hexsha)
            file_data[file_path]['diffs'].append(diff_text)
            
            # Update last modified timestamp
            if (file_data[file_path]['last_modified'] is None or 
                commit_date > file_data[file_path]['last_modified']):
                file_data[file_path]['last_modified'] = commit_date
    
    # Build result list
    results = []
    for file_path, data in file_data.items():
        # Get language from extension
        ext = Path(file_path).suffix.lower()
        language = EXTENSION_TO_LANGUAGE.get(ext, 'unknown')
        
        # Concatenate all diffs
        full_diff = '\n\n'.join(data['diffs'])
        
        # Truncate if necessary
        diff_lines = full_diff.split('\n')
        if len(diff_lines) > MAX_DIFF_LINES:
            truncated_diff = (
                '\n'.join(diff_lines[:TRUNCATE_HEAD_LINES]) +
                '\n\n... [truncated] ...\n\n' +
                '\n'.join(diff_lines[-TRUNCATE_TAIL_LINES:])
            )
        else:
            truncated_diff = full_diff
        
        # Build result dict
        result = {
            'file_path': file_path,
            'language': language,
            'total_commits': len(data['commits']),
            'diff_text': truncated_diff,
            'last_modified': data['last_modified'].isoformat() if data['last_modified'] else None,
            'commit_hashes': data['commits'],
        }
        results.append(result)
    
    # Sort by last_modified (most recent first)
    results.sort(key=lambda x: x['last_modified'] or '', reverse=True)
    
    return results


def test_git_parser():
    """
    Test function that runs git_parser on the current directory.
    Prints the first result for verification.
    """
    print("[TEST] Testing git_parser on current directory...")
    print(f"Current directory: {os.getcwd()}")
    print("-" * 60)
    
    try:
        # Run parser on current directory, last 30 days
        results = get_file_diffs('.', days=30)
        
        print(f"[OK] Found {len(results)} files modified in the last 30 days")
        print("-" * 60)
        
        if results:
            print("\n[RESULT] First result:")
            first = results[0]
            print(f"  File: {first['file_path']}")
            print(f"  Language: {first['language']}")
            print(f"  Total commits: {first['total_commits']}")
            print(f"  Last modified: {first['last_modified']}")
            print(f"  Commit hashes: {', '.join(first['commit_hashes'][:3])}{'...' if len(first['commit_hashes']) > 3 else ''}")
            print(f"  Diff length: {len(first['diff_text'])} characters")
            print(f"  Diff lines: {len(first['diff_text'].split(chr(10)))} lines")
            print("\n  First 10 lines of diff:")
            diff_lines = first['diff_text'].split('\n')[:10]
            for line in diff_lines:
                print(f"    {line}")
        else:
            print("[WARN] No files found in the time window")
            print("   Try increasing --days or check if this is a git repository")
        
    except InvalidGitRepositoryError as e:
        print(f"[ERROR] {e}")
        print("   Make sure you're running this in a git repository")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_git_parser()

# Made with Bob

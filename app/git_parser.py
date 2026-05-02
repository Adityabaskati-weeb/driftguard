"""Git parser module for DriftGuard.

Extracts file diffs from a Git repository over a specified time window.
Supports local repositories, GitHub URLs, and generic git URLs.
"""

import os
import re
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

try:
    from git import Repo, GitCommandError, InvalidGitRepositoryError
except ImportError:
    raise ImportError("GitPython is required. Install with: pip install gitpython")

try:
    import requests
except ImportError:
    raise ImportError("requests is required. Install with: pip install requests")


# Supported file extensions
SUPPORTED_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.html', '.css'}

# Language mapping
EXTENSION_TO_LANGUAGE = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rb': 'ruby',
    '.html': 'html',
    '.css': 'css',
}

# Maximum lines for diff_text
MAX_DIFF_LINES = 150
TRUNCATE_HEAD_LINES = 75
TRUNCATE_TAIL_LINES = 75


def _parse_github_url(url: str) -> Optional[Tuple[str, str]]:
    """Parse GitHub URL to extract owner and repo name.
    
    Args:
        url: GitHub URL (e.g., https://github.com/facebook/react)
        
    Returns:
        Tuple of (owner, repo) or None if not a valid GitHub URL
    """
    # Match patterns like:
    # - https://github.com/owner/repo
    # - https://github.com/owner/repo.git
    # - http://github.com/owner/repo
    pattern = r'https?://github\.com/([^/]+)/([^/\.]+?)(?:\.git)?/?$'
    match = re.match(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None


def _fetch_github_commits(owner: str, repo: str, since_date: datetime, 
                          github_token: Optional[str] = None) -> List[Dict]:
    """Fetch commits from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        since_date: Only fetch commits after this date
        github_token: Optional GitHub token for authentication
        
    Returns:
        List of commit dictionaries from GitHub API
        
    Raises:
        requests.HTTPError: For API errors (401, 403, 404, etc.)
    """
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    all_commits = []
    page = 1
    per_page = 100
    
    while True:
        url = f'https://api.github.com/repos/{owner}/{repo}/commits'
        params = {
            'since': since_date.isoformat(),
            'per_page': per_page,
            'page': page
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        # Handle errors
        if response.status_code == 401:
            raise requests.HTTPError(
                "401 Unauthorized: Private repository requires GITHUB_TOKEN"
            )
        elif response.status_code == 404:
            raise requests.HTTPError(
                f"404 Not Found: Repository {owner}/{repo} does not exist"
            )
        elif response.status_code == 403:
            # Check if it's rate limit
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers.get('X-RateLimit-Remaining', '0')
                if remaining == '0':
                    reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                    raise requests.HTTPError(
                        f"403 Rate Limit Exceeded. Resets at: {reset_time}. "
                        "Use GITHUB_TOKEN for higher limits."
                    )
            raise requests.HTTPError(f"403 Forbidden: {response.text}")
        
        response.raise_for_status()
        
        commits = response.json()
        if not commits:
            break
        
        all_commits.extend(commits)
        
        # Check if there are more pages
        if len(commits) < per_page:
            break
        
        page += 1
    
    return all_commits


def _fetch_github_commit_diff(owner: str, repo: str, base_sha: str, head_sha: str,
                               github_token: Optional[str] = None) -> Dict:
    """Fetch diff between two commits from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        base_sha: Base commit SHA
        head_sha: Head commit SHA
        github_token: Optional GitHub token for authentication
        
    Returns:
        Comparison data from GitHub API
        
    Raises:
        requests.HTTPError: For API errors
    """
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    url = f'https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}'
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    return response.json()


def _convert_github_diff_to_format(files_data: List[Dict], commit_sha: str, 
                                    commit_date: datetime) -> Dict[str, Dict]:
    """Convert GitHub API diff format to internal format.
    
    Args:
        files_data: List of file change dicts from GitHub API
        commit_sha: Commit SHA
        commit_date: Commit timestamp
        
    Returns:
        Dictionary mapping file paths to their change data
    """
    file_changes = {}
    
    for file_info in files_data:
        filename = file_info.get('filename', '')
        
        # Filter by extension
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        
        # Skip large files
        if file_info.get('changes', 0) > 1000:  # Skip files with >1000 changes
            continue
        
        # Get patch (unified diff)
        patch = file_info.get('patch', '')
        if not patch:
            continue
        
        # Initialize file data if not exists
        if filename not in file_changes:
            file_changes[filename] = {
                'commits': [],
                'diffs': [],
                'last_modified': None,
            }
        
        # Add commit and diff
        file_changes[filename]['commits'].append(commit_sha)
        file_changes[filename]['diffs'].append(patch)
        
        # Update last modified
        if (file_changes[filename]['last_modified'] is None or 
            commit_date > file_changes[filename]['last_modified']):
            file_changes[filename]['last_modified'] = commit_date
    
    return file_changes


def _fetch_github_repo_diffs(owner: str, repo: str, days: int,
                              github_token: Optional[str] = None) -> List[Dict]:
    """Fetch file diffs from GitHub repository via API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        days: Number of days to look back
        github_token: Optional GitHub token for authentication
        
    Returns:
        List of file diff dictionaries in same format as get_file_diffs()
    """
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Fetch commits
    print(f"Fetching commits from GitHub API for {owner}/{repo}...")
    commits = _fetch_github_commits(owner, repo, cutoff_date, github_token)
    
    if not commits:
        return []
    
    print(f"Found {len(commits)} commits, fetching diffs...")
    
    # Collect file changes
    file_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'commits': [],
        'diffs': [],
        'last_modified': None,
    })
    
    # Process commits in reverse order (oldest first) to get proper parent relationships
    for i, commit_info in enumerate(reversed(commits)):
        commit_sha = commit_info['sha']
        commit_date_str = commit_info['commit']['committer']['date']
        commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
        
        # Get parent SHA (if exists)
        parents = commit_info.get('parents', [])
        if not parents:
            # Initial commit - skip for now (could fetch full tree if needed)
            continue
        
        parent_sha = parents[0]['sha']
        
        # Fetch diff between parent and this commit
        try:
            comparison = _fetch_github_commit_diff(owner, repo, parent_sha, 
                                                   commit_sha, github_token)
            files_changed = comparison.get('files', [])
            
            # Convert to internal format
            changes = _convert_github_diff_to_format(files_changed, commit_sha, commit_date)
            
            # Merge into file_data
            for file_path, data in changes.items():
                file_data[file_path]['commits'].extend(data['commits'])
                file_data[file_path]['diffs'].extend(data['diffs'])
                if (file_data[file_path]['last_modified'] is None or
                    data['last_modified'] > file_data[file_path]['last_modified']):
                    file_data[file_path]['last_modified'] = data['last_modified']
        
        except requests.HTTPError as e:
            print(f"Warning: Failed to fetch diff for commit {commit_sha[:7]}: {e}")
            continue
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(commits)} commits...")
    
    # Build result list (same format as get_file_diffs)
    results = []
    for file_path, data in file_data.items():
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
    
    print(f"Completed: {len(results)} files with changes")
    return results


def resolve_repo(repo_input: str, github_token: Optional[str] = None) -> Tuple[Any, bool]:
    """Resolve repository input to either local path or remote data.
    
    Args:
        repo_input: Local path, GitHub URL, or other git URL
        github_token: Optional GitHub token for API authentication
        
    Returns:
        Tuple of (data, is_remote):
        - If local path: (path_string, False)
        - If GitHub URL: (list_of_diffs, True)
        - If other git URL: (path_to_temp_clone, False)
        
    Raises:
        ValueError: If repo_input is invalid
        requests.HTTPError: For GitHub API errors
    """
    # Check if it's a GitHub URL
    github_info = _parse_github_url(repo_input)
    if github_info:
        owner, repo = github_info
        print(f"Detected GitHub repository: {owner}/{repo}")
        
        # Use environment variable if token not provided
        if not github_token:
            github_token = os.environ.get('GITHUB_TOKEN')
        
        # Fetch diffs via API
        try:
            # We need days parameter - will be passed separately
            # For now, return a callable that takes days
            return (owner, repo, github_token), True
        except requests.HTTPError as e:
            raise ValueError(f"GitHub API error: {e}")
    
    # Check if it's another https URL
    if repo_input.startswith('https://') or repo_input.startswith('http://'):
        print(f"Detected remote git repository: {repo_input}")
        print("Cloning to temporary directory...")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='driftguard_')
        
        try:
            # Clone repository
            Repo.clone_from(repo_input, temp_dir, depth=1)
            print(f"Cloned to: {temp_dir}")
            return temp_dir, False
        except Exception as e:
            # Clean up on error
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError(f"Failed to clone repository: {e}")
    
    # Treat as local path
    repo_path = os.path.abspath(repo_input)
    if not os.path.exists(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")
    
    return repo_path, False


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


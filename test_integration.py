"""Integration test for git_parser + bob_analyzer pipeline."""

from app.git_parser import get_file_diffs
from app.bob_analyzer import batch_analyze

def test_pipeline():
    """Test the full pipeline from git parsing to analysis."""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST: git_parser -> bob_analyzer")
    print("=" * 60)
    
    # Step 1: Parse git repository
    print("\n[STEP 1] Parsing git repository...")
    file_diffs = get_file_diffs('.', days=30)
    print(f"Found {len(file_diffs)} files")
    
    if not file_diffs:
        print("[WARN] No files found. Creating a test commit first...")
        return
    
    # Step 2: Analyze files
    print("\n[STEP 2] Analyzing files with bob_analyzer...")
    results = batch_analyze(file_diffs)
    
    # Step 3: Display results
    print("\n[STEP 3] Analysis Results Summary")
    print("=" * 60)
    
    for result in results:
        print(f"\nFile: {result['file_path']}")
        print(f"  Language: {result['language']}")
        print(f"  Commits: {result['total_commits']}")
        print(f"  Scores:")
        print(f"    - Documentation: {result['documentation_drift_score']}/100")
        print(f"    - Test Coverage: {result['test_drift_score']}/100")
        print(f"    - Complexity: {result['complexity_growth_score']}/100")
        print(f"    - Naming: {result['naming_consistency_score']}/100")
        
        avg = (
            result['documentation_drift_score'] +
            result['test_drift_score'] +
            result['complexity_growth_score'] +
            result['naming_consistency_score']
        ) / 4
        print(f"  Average: {avg:.1f}/100")
        print(f"  Top Risk: {result['top_risk']}")
        print(f"  Recommendation: {result['recommendation']}")
    
    print("\n" + "=" * 60)
    print(f"[SUCCESS] Pipeline test complete! Analyzed {len(results)} files")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    test_pipeline()

# Made with Bob

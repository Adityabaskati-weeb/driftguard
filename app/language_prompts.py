"""language_prompts.py

Language-specific analysis templates for DriftGuard.
Each language has tailored decay detection patterns.
"""

LANGUAGE_PROMPTS = {
    "python": {
        "description": "Python code analysis focusing on PEP 8 compliance and Pythonic patterns",
        "focus_areas": [
            "Missing docstrings for functions, classes, and modules",
            "Type hint drift (inconsistent use of type annotations)",
            "Import organization and unused imports",
            "List comprehension vs loop complexity",
            "Exception handling patterns (bare except, missing error types)"
        ],
        "complexity_indicators": [
            "Deeply nested loops and conditionals",
            "Long functions (>50 lines)",
            "High cyclomatic complexity",
            "Multiple return statements"
        ],
        "naming_conventions": "snake_case for functions/variables, PascalCase for classes"
    },
    
    "javascript": {
        "description": "JavaScript code analysis for modern ES6+ patterns and consistency",
        "focus_areas": [
            "Callback hell growth (nested callbacks)",
            "Inconsistent Promise vs async/await usage",
            "Missing JSDoc for exported functions",
            "Unused dependencies in package.json",
            "var vs let/const inconsistency"
        ],
        "complexity_indicators": [
            "Deeply nested callbacks",
            "Long promise chains",
            "Complex ternary operators",
            "Large switch statements"
        ],
        "naming_conventions": "camelCase for functions/variables, PascalCase for classes/constructors"
    },
    
    "typescript": {
        "description": "TypeScript code analysis for type safety and consistency",
        "focus_areas": [
            "Missing type annotations on function parameters and return types",
            "Type-casting abuse (excessive use of 'any' or 'as' assertions)",
            "Breaking type changes in git history",
            "Unused generic type parameters",
            "Interface vs type alias inconsistency"
        ],
        "complexity_indicators": [
            "Complex union/intersection types",
            "Deeply nested generic types",
            "Large type definitions",
            "Conditional types overuse"
        ],
        "naming_conventions": "camelCase for functions/variables, PascalCase for classes/interfaces/types"
    },
    
    "java": {
        "description": "Java code analysis for enterprise patterns and maintainability",
        "focus_areas": [
            "God Class smell (high line count and method count per class)",
            "Missing Javadoc on public APIs",
            "Test class drift (missing @Test method pairing with implementation)",
            "Exception handling patterns (catching generic Exception)",
            "Unused imports and dead code"
        ],
        "complexity_indicators": [
            "Classes exceeding 300 lines",
            "Methods exceeding 50 lines",
            "High number of method parameters (>5)",
            "Deep inheritance hierarchies"
        ],
        "naming_conventions": "camelCase for methods/variables, PascalCase for classes, UPPER_SNAKE_CASE for constants"
    },
    
    "go": {
        "description": "Go code analysis for idiomatic patterns and simplicity",
        "focus_areas": [
            "Error handling pattern drift (missing nil checks)",
            "Inconsistent defer usage for cleanup",
            "Exported vs unexported naming violations (capitalization)",
            "Interface compliance drift",
            "Missing error wrapping with context"
        ],
        "complexity_indicators": [
            "Long functions (>50 lines)",
            "Multiple return values (>3)",
            "Deep nesting in goroutines",
            "Complex select statements"
        ],
        "naming_conventions": "camelCase for unexported, PascalCase for exported, short variable names in small scopes"
    },
    
    "ruby": {
        "description": "Ruby code analysis for Rails conventions and Ruby idioms",
        "focus_areas": [
            "Missing RDoc/YARD documentation",
            "Inconsistent use of blocks vs lambdas",
            "Rails convention violations",
            "Missing test coverage for controllers/models",
            "Monkey patching without proper namespacing"
        ],
        "complexity_indicators": [
            "Long methods (>25 lines)",
            "Deep nesting in blocks",
            "Complex meta-programming",
            "Large class definitions"
        ],
        "naming_conventions": "snake_case for methods/variables, PascalCase for classes/modules, UPPER_SNAKE_CASE for constants"
    }
}


def get_language_prompt(language: str) -> dict:
    """Get language-specific analysis prompt.
    
    Args:
        language: Programming language name (lowercase)
        
    Returns:
        Dictionary with language-specific analysis guidelines
    """
    return LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["python"])


def get_focus_areas(language: str) -> list:
    """Get focus areas for a specific language.
    
    Args:
        language: Programming language name (lowercase)
        
    Returns:
        List of focus areas for decay detection
    """
    prompt = get_language_prompt(language)
    return prompt.get("focus_areas", [])


def get_complexity_indicators(language: str) -> list:
    """Get complexity indicators for a specific language.
    
    Args:
        language: Programming language name (lowercase)
        
    Returns:
        List of complexity indicators
    """
    prompt = get_language_prompt(language)
    return prompt.get("complexity_indicators", [])


def get_naming_conventions(language: str) -> str:
    """Get naming conventions for a specific language.
    
    Args:
        language: Programming language name (lowercase)
        
    Returns:
        String describing naming conventions
    """
    prompt = get_language_prompt(language)
    return prompt.get("naming_conventions", "Follow language-specific conventions")


# Made with Bob
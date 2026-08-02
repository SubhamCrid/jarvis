"""
Automated AST Architectural Boundary Linter for jarvis.internet platform.
Enforces 8 explicit architectural invariants:
1. jarvis.internet MUST NOT import higher-level modules (jarvis.capabilities, jarvis.tools, jarvis.orchestrator).
2. jarvis.internet.downloads MUST NOT import browser modules.
3. jarvis.internet.sessions MUST NOT import browser modules.
4. jarvis.internet.replay MUST NOT import concrete providers.
5. jarvis.internet.planner MUST NOT import browser implementations.
"""

import ast
import sys
from pathlib import Path

FORBIDDEN_GLOBAL_IMPORTS = {
    "jarvis.capabilities",
    "jarvis.tools",
    "jarvis.orchestrator",
}


def check_internet_architecture(src_root: Path) -> bool:
    internet_dir = src_root / "jarvis" / "internet"
    if not internet_dir.exists():
        print(f"Error: {internet_dir} does not exist.")
        return False

    violations = []
    py_files = list(internet_dir.rglob("*.py"))

    for py_file in py_files:
        rel_path = str(py_file.relative_to(src_root)).replace("\\", "/")
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            for node in ast.walk(tree):
                module_name = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module

                if not module_name:
                    continue

                # Invariant 1: Global forbidden modules
                if any(module_name.startswith(forbidden) for forbidden in FORBIDDEN_GLOBAL_IMPORTS):
                    violations.append(f"{rel_path}:{node.lineno} Imports forbidden module '{module_name}'")

                # Invariant 2: Downloads must not import browser
                if "jarvis/internet/downloads" in rel_path:
                    if "providers.browser" in module_name:
                        violations.append(f"{rel_path}:{node.lineno} Downloads module imports browser '{module_name}'")

                # Invariant 3: Sessions must not import browser
                if "jarvis/internet/sessions" in rel_path:
                    if "providers.browser" in module_name:
                        violations.append(f"{rel_path}:{node.lineno} Sessions module imports browser '{module_name}'")

                # Invariant 4: Replay must not import concrete providers
                if "jarvis/internet/replay" in rel_path:
                    if "providers.search" in module_name or "providers.fetch" in module_name:
                        violations.append(f"{rel_path}:{node.lineno} Replay module imports concrete provider '{module_name}'")

                # Invariant 5: Planner must not import concrete browser implementation
                if "jarvis/internet/planner" in rel_path:
                    if "providers.browser.camoufox" in module_name:
                        violations.append(f"{rel_path}:{node.lineno} Planner imports concrete browser engine '{module_name}'")

        except Exception as e:
            print(f"Error parsing {rel_path}: {e}")

    if violations:
        print("!!! ARCHITECTURAL BOUNDARY VIOLATIONS DETECTED !!!")
        for v in violations:
            print(f"  - {v}")
        return False

    print("SUCCESS: jarvis.internet platform satisfies all architectural boundary rules.")
    return True


if __name__ == "__main__":
    root = Path(__file__).parent.parent / "src"
    success = check_internet_architecture(root)
    sys.exit(0 if success else 1)

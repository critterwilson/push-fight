"""
Pytest configuration and shared fixtures for the Push Fight test suite.

This conftest.py serves as the central configuration point for all pytest-based
tests in the project. Its primary responsibility is ensuring that the project
root is on sys.path so that imports like `from app.engine.game_state import ...`
resolve correctly regardless of the working directory from which pytest is invoked.

No shared fixtures are defined here currently — individual test modules define
their own fixtures as needed. If cross-module fixtures are required in the future
(e.g., a pre-configured GameState or a temporary saves directory), they should
be added to this file so every test module can access them automatically.
"""

import sys
from pathlib import Path

# Add project root to sys.path so that `app.*` imports work even when pytest is
# executed from a subdirectory or by a CI runner whose CWD differs from the repo root.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

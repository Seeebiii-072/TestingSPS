"""Root conftest.py — ensures the project root is on sys.path for all tests."""
import sys
import os

# Add the project root to sys.path so that 'email_worker' is importable
# as a top-level package regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(__file__))

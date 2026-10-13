"""Point every test at a throwaway SQLite database *before* any app module is
imported, so the suite can never touch backend/interdec.db."""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="interdec-test-")
os.environ["INTERDEC_DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ.setdefault("INTERDEC_SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""Runner for all offline unit tests (AI pipeline, Database repository, and FastAPI endpoints)."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_all_unit_tests() -> bool:
    print("=" * 70)
    print("RUNNING ALL OFFLINE UNIT TESTS (AI, DATABASE, FASTAPI)")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT / "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 70)
    print(f"TOTAL TESTS RUN : {result.testsRun}")
    print(f"PASSED          : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"FAILED          : {len(result.failures)}")
    print(f"ERRORS          : {len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_unit_tests()
    sys.exit(0 if success else 1)

import os


SQL_BASE = os.path.join(os.path.dirname(__file__), "..", "aml", "sql")

EXPECTED_FILES = [
    ("oracle", "structuring.sql"),
    ("oracle", "velocity.sql"),
    ("oracle", "dormancy.sql"),
    ("oracle", "cash_intensive.sql"),
    ("postgres", "structuring.sql"),
    ("postgres", "velocity.sql"),
    ("postgres", "dormancy.sql"),
    ("postgres", "cash_intensive.sql"),
]


def test_sql_files_exist():
    for folder, filename in EXPECTED_FILES:
        path = os.path.join(SQL_BASE, folder, filename)
        assert os.path.exists(path), f"Missing: {folder}/{filename}"


def test_sql_files_not_empty():
    for folder, filename in EXPECTED_FILES:
        path = os.path.join(SQL_BASE, folder, filename)
        assert os.path.getsize(path) > 0, f"Empty file: {folder}/{filename}"


def test_sql_files_contain_fincen_reference():
    for folder, filename in EXPECTED_FILES:
        path = os.path.join(SQL_BASE, folder, filename)
        with open(path, "r") as f:
            content = f.read()
        assert "Reference" in content or "reference" in content, \
            f"Missing regulatory reference in {folder}/{filename}"


def test_sql_files_contain_select():
    for folder, filename in EXPECTED_FILES:
        path = os.path.join(SQL_BASE, folder, filename)
        with open(path, "r") as f:
            content = f.read()
        assert "SELECT" in content.upper(), \
            f"No SELECT statement found in {folder}/{filename}"
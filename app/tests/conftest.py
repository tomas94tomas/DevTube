import os
import tempfile
import shutil
import pytest

# Import your Flask app and models
from app.main import app as flask_app
from app import models

@pytest.fixture(scope="session")
def _tmpdir():
    d = tempfile.mkdtemp(prefix="devtube-tests-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)

@pytest.fixture(autouse=True)
def _temp_db(_tmpdir):
    """
    Point the app to a disposable SQLite file for each test session.
    """
    tmp_db = os.path.join(_tmpdir, "videos.db")
    models.DB_PATH = tmp_db
    models.init_db()
    yield
    # nothing else needed; the file lives under _tmpdir which gets cleaned

@pytest.fixture()
def client():
    """
    Flask test client.
    """
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c

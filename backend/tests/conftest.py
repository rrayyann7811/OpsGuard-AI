import pytest
from sqlalchemy import create_engine
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_database():
    engine = create_engine("sqlite:///:memory:")
    with patch("app.main.engine", engine):
        yield
    engine.dispose()

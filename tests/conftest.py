import os

import pytest


@pytest.fixture
def postgres_dsn():
    return os.environ["POSTGRES_DSN"]

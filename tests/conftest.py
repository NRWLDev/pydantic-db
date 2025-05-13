import os

import pytest


@pytest.fixture
def postgres_dsn():
    return os.environ["POSTGRES_DSN"]


@pytest.fixture
def mysql_dsn():
    return os.environ["MYSQL_DSN"]

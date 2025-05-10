from datetime import UTC, datetime

from pydantic_db import Model


class ModelA(Model):
    id: int
    a: str


class ModelB(Model):
    id: int
    b: str


class ModelC(Model):
    _eq_excluded_fields = {"updated"}

    id: int
    c: str
    updated: datetime


def test_unrelated_models_not_equal():
    a = ModelA(id=1, a="b")
    b = ModelB(id=1, b="b")
    assert a != b


def test_different_data_models_not_equal():
    a = ModelA(id=1, a="a")
    b = ModelA(id=1, a="b")
    assert a != b


def test_equivalent_models_equal():
    a = ModelA(id=1, a="a")
    b = ModelA(id=1, a="a")
    assert a == b


def test_equivalent_models_equal_ignored_field():
    a = ModelC(id=1, c="c", updated=datetime(2025, 1, 1, tzinfo=UTC))
    b = ModelC(id=1, c="c", updated=datetime(2025, 1, 2, tzinfo=UTC))
    assert a == b


async def test_from_result():
    r = {"id": 1, "a": "b"}
    model = ModelA.from_result(r)

    assert model == ModelA(id=1, a="b")


async def test_from_results():
    results = [{"id": 1, "a": "b"}]
    models = ModelA.from_results(results)

    assert models == [
        ModelA(id=1, a="b"),
    ]

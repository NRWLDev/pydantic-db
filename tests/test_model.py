from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pydantic_db import Model, NestedModel


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


class ModelD(NestedModel):
    _skip_prefix_fields = {"b": "id"}

    id: int
    d: str
    a: ModelA
    b: ModelB | None


class ModelE(NestedModel):
    id: int | float  # union not containing model to trigger test branches
    e: str
    d: ModelD  # Nested NestedModel


def test_unrelated_models_not_equal():
    m1 = ModelA(id=1, a="x")
    m2 = ModelB(id=1, b="x")
    assert m1 != m2


def test_different_data_models_not_equal():
    m1 = ModelA(id=1, a="y")
    m2 = ModelA(id=1, a="x")
    assert m1 != m2


def test_equivalent_models_equal():
    m1 = ModelA(id=1, a="y")
    m2 = ModelA(id=1, a="y")
    assert m1 == m2


def test_equivalent_models_equal_ignored_field():
    m1 = ModelC(id=1, c="x", updated=datetime(2025, 1, 1, tzinfo=UTC))
    m2 = ModelC(id=1, c="x", updated=datetime(2025, 1, 2, tzinfo=UTC))
    assert m1 == m2


class TestModel:
    def test_from_result(self):
        r = {"id": 1, "a": "x"}
        model = ModelA.from_result(r)

        assert model == ModelA(id=1, a="x")

    def test_from_results(self):
        results = [{"id": 1, "a": "x"}]
        models = ModelA.from_results(results)

        assert models == [
            ModelA(id=1, a="x"),
        ]


class TestNestedModel:
    @pytest.mark.parametrize(
        ("model", "expected_fields"),
        [
            (ModelD, {"a": ModelA, "b": ModelB}),
            (ModelE, {"d": ModelD}),
        ],
    )
    def test_model_fields(self, model, expected_fields):
        assert model._pdb_model_fields() == expected_fields

    def test_from_result(self):
        r = {"id": 1, "d": "x", "a__id": 2, "a__a": "y", "b__id": 3, "b__b": "z"}
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=ModelB(id=3, b="z"),
        )

    def test_from_result_skips_optional(self):
        r = {"id": 1, "d": "x", "a__id": 2, "a__a": "y", "b__id": None, "b__b": None}
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=None,
        )

    def test_multi_layer_nesting(self):
        r = {"id": 0, "e": "w", "d__id": 1, "d__d": "x", "d__a__id": 2, "d__a__a": "y", "d__b__id": 3, "d__b__b": "z"}
        model = ModelE.from_result(r)

        assert model == ModelE(
            id=0,
            e="w",
            d=ModelD(
                id=1,
                d="x",
                a=ModelA(id=2, a="y"),
                b=ModelB(id=3, b="z"),
            ),
        )

    def test_from_results(self):
        results = [{"id": 1, "d": "x", "a__id": 2, "a__a": "y", "b__id": 3, "b__b": "z"}]
        models = ModelD.from_results(results)

        assert models == [
            ModelD(
                id=1,
                d="x",
                a=ModelA(id=2, a="y"),
                b=ModelB(id=3, b="z"),
            ),
        ]

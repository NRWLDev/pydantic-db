from __future__ import annotations

import typing
from datetime import datetime, timezone

import pytest

from tests.model import ModelA, ModelB, ModelC, ModelD, ModelE, ModelF


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
    m1 = ModelC(id=1, c="x", updated=datetime(2025, 1, 1, tzinfo=timezone.utc))
    m2 = ModelC(id=1, c="x", updated=datetime(2025, 1, 2, tzinfo=timezone.utc))
    assert m1 == m2


def test_hash():
    m1 = ModelA(id=1, a="y")
    m2 = ModelA(id=1, a="x")
    m3 = ModelA(id=2, a="x")

    assert hash(m1) == hash(m2)
    assert hash(m1) != hash(m3)


class TestModel:
    def test_model_fields(self):
        assert ModelA._pdb_model_fields() == {}

    def test_as_columns(self):
        columns = ModelA.as_columns()

        assert columns == [("id",), ("a",)]

    def test_as_typed_columns(self):
        columns = ModelA.as_typed_columns()

        assert columns == {("id",): int, ("a",): str}

    def test_from_result(self):
        r = {"id": 1, "a": "x"}
        model = ModelA.from_result(r)

        assert model == ModelA(id=1, a="x")

    def test_from_result_with_prefix(self):
        r = {"xxxid": 1, "xxxa": "x"}
        model = ModelA.from_result(r, prefix="xxx")

        assert model == ModelA(id=1, a="x")

    def test_from_results(self):
        results = [{"id": 1, "a": "x"}]
        models = ModelA.from_results(results)

        assert models == [
            ModelA(id=1, a="x"),
        ]

    def test_from_results_with_prefix(self):
        results = [{"xxxid": 1, "xxxa": "x"}]
        models = ModelA.from_results(results, prefix="xxx")

        assert models == [
            ModelA(id=1, a="x"),
        ]


class TestNestedModel:
    @pytest.mark.parametrize(
        ("model", "expected_fields"),
        [
            (ModelD, {"a": (ModelA, False, False), "b": (ModelB, True, False)}),
            (ModelE, {"d": (ModelD, False, False)}),
            (ModelF, {"models": (ModelA, True, True)}),
        ],
    )
    def test_model_fields(self, model, expected_fields):
        assert model._pdb_model_fields() == expected_fields

    def test_as_columns(self):
        columns = ModelD.as_columns()

        assert columns == [("id",), ("d",), ("a", "id"), ("a", "a"), ("b", "id"), ("b", "b")]

    def test_as_typed_columns(self):
        columns = ModelE.as_typed_columns()

        assert columns == {
            ("id",): typing.Union[int, float],
            ("e",): str,
            ("d", "id"): int,
            ("d", "d"): str,
            ("d", "a", "id"): int,
            ("d", "a", "a"): str,
            ("d", "b", "id"): int,
            ("d", "b", "b"): str,
        }

    def test_as_typed_columns_with_base_table(self):
        columns = ModelE.as_typed_columns("base_table")

        assert columns == {
            ("base_table", "id"): typing.Union[int, float],
            ("base_table", "e"): str,
            ("base_table", "d", "id"): int,
            ("base_table", "d", "d"): str,
            ("base_table", "d", "a", "id"): int,
            ("base_table", "d", "a", "a"): str,
            ("base_table", "d", "b", "id"): int,
            ("base_table", "d", "b", "b"): str,
        }

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

    def test_from_result_with_list_field(self):
        r = {"id": 1, "models__id": 2, "models__a": "y"}
        model = ModelF.from_result(r)

        assert model == ModelF(
            id=1,
            models=[ModelA(id=2, a="y")],
        )

    @pytest.mark.parametrize(
        ("result"),
        [
            {"id": 1, "models__id": None, "models__a": None},
            {"id": 1},
        ],
    )
    def test_from_result_with_list_field_missing_optional(self, result):
        model = ModelF.from_result(result)

        assert model == ModelF(
            id=1,
            models=[],
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

    def test_from_results_list_field(self):
        results = [
            {"id": 1, "models__id": 1, "models__a": "x"},
            {"id": 1, "models__id": 2, "models__a": "y"},
        ]
        models = ModelF.from_results(results)

        assert models == [
            ModelF(
                id=1,
                models=[
                    ModelA(id=1, a="x"),
                    ModelA(id=2, a="y"),
                ],
            ),
        ]

    @pytest.mark.parametrize(
        ("model", "expected_fields"),
        [
            (ModelD, sorted(["id", "d", "a", "a__id", "a__a", "b", "b__id", "b__b"])),
            (ModelE, sorted(["id", "e", "d", "d__id", "d__d", "d__a__a", "d__b__b"])),
        ],
    )
    def test_sortable_fields(self, model, expected_fields):
        assert model.sortable_fields() == expected_fields

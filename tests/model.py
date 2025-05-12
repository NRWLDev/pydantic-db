from __future__ import annotations

from datetime import datetime

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


class ModelD(Model):
    _skip_prefix_fields = {"b": "id"}

    id: int
    d: str
    a: ModelA
    b: ModelB | None


class ModelE(Model):
    id: int | float  # union not containing model to trigger test branches
    e: str
    d: ModelD  # Nested NestedModel

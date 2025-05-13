import asyncpg
import pytest

from tests.model import ModelA, ModelB, ModelD, ModelE


@pytest.fixture(autouse=True)
async def db_session(postgres_dsn):
    conn = await asyncpg.connect(postgres_dsn)
    tr = conn.transaction()
    await tr.start()
    try:
        yield conn
    finally:
        await tr.rollback()
        await conn.close()


class TestModel:
    async def test_from_result(self, db_session):
        r = await db_session.fetchrow("select 1 as id, 'x' as a")
        model = ModelA.from_result(r)

        assert model == ModelA(id=1, a="x")

    async def test_from_results(self, db_session):
        results = await db_session.fetch("select 1 as id, 'x' as a")
        models = ModelA.from_results(results)

        assert models == [
            ModelA(id=1, a="x"),
        ]


class TestNestedModel:
    async def test_from_result(self, db_session):
        r = await db_session.fetchrow("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            3 as b__id,
            'z' as b__b
        """)
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=ModelB(id=3, b="z"),
        )

    async def test_from_result_skips_optional(self, db_session):
        r = await db_session.fetchrow("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            null as b__id,
            null as b__b
        """)
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=None,
        )

    async def test_multi_layer_nesting(self, db_session):
        r = await db_session.fetchrow("""
        select
            0 as id,
            'w' as e,
            1 as d__id,
            'x' as d__d,
            2 as d__a__id,
            'y' as d__a__a,
            3 as d__b__id,
            'z' as d__b__b
        """)
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

    async def test_from_results(self, db_session):
        results = await db_session.fetch("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            3 as b__id,
            'z' as b__b
        """)
        models = ModelD.from_results(results)

        assert models == [
            ModelD(
                id=1,
                d="x",
                a=ModelA(id=2, a="y"),
                b=ModelB(id=3, b="z"),
            ),
        ]

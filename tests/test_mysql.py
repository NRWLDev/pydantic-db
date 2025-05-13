import dsnparse
import mysql.connector
import pytest

from tests.model import ModelA, ModelB, ModelD, ModelE


@pytest.fixture
def cursor(mysql_dsn):
    r = dsnparse.parse(mysql_dsn)
    db = mysql.connector.connect(
        username=r.username,
        password=r.password,
        host=r.host,
        port=r.port,
        database=r.paths[0],
    )
    yield db.cursor(dictionary=True)
    db.close()


class TestModel:
    def test_from_result(self, cursor):
        cursor.execute("select 1 as id, 'x' as a")
        r = cursor.fetchone()
        model = ModelA.from_result(r)

        assert model == ModelA(id=1, a="x")

    def test_from_results(self, cursor):
        cursor.execute("select 1 as id, 'x' as a")
        results = cursor.fetchall()
        models = ModelA.from_results(results)

        assert models == [
            ModelA(id=1, a="x"),
        ]


class TestNestedModel:
    def test_from_result(self, cursor):
        cursor.execute("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            3 as b__id,
            'z' as b__b
        """)
        r = cursor.fetchone()
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=ModelB(id=3, b="z"),
        )

    def test_from_result_skips_optional(self, cursor):
        cursor.execute("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            null as b__id,
            null as b__b
        """)
        r = cursor.fetchone()
        model = ModelD.from_result(r)

        assert model == ModelD(
            id=1,
            d="x",
            a=ModelA(id=2, a="y"),
            b=None,
        )

    def test_multi_layer_nesting(self, cursor):
        cursor.execute("""
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
        r = cursor.fetchone()
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

    def test_from_results(self, cursor):
        cursor.execute("""
        select
            1 as id,
            'x' as d,
            2 as a__id,
            'y' as a__a,
            3 as b__id,
            'z' as b__b
        """)
        results = cursor.fetchall()
        models = ModelD.from_results(results)

        assert models == [
            ModelD(
                id=1,
                d="x",
                a=ModelA(id=2, a="y"),
                b=ModelB(id=3, b="z"),
            ),
        ]

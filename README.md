pydantic-db aims to be a database framework agnostic modeling library.
Providing functionality to convert database result object(s) into pydantic
model(s). The aim is not to provide an ORM, but to target users who prefer raw
sql interactions over obfuscated ORM object built queries layers.

For those who prefer libraries like pypika to build their queries, this library
can still provide a nice layer between raw query results and database models.

So long as the database framework you are using returns result objects that can
be converted to a dictionary, pydantic-db will ineract cleanly with your
results.

# Usage

All examples assumes the existence of underlying tables and data, they are not
intended to run as is.

## from_result

To convert a single result object into a model, use `Model.from_result`.

```python
import sqlite3

from pydantic_db import Model


class User(Model):
    id: int
    name: str


db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row

stmt = "SELECT * FROM my_user LIMIT 1"
cursor.execute(stmt)
r = cursor.fetchone()

user = User.from_result(r)
```

## from_results

To convert a list of result objects into models, use `Model.from_results`.

```python
import sqlite3

from pydantic_db import Model


class User(Model):
    id: int
    name: str


db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row

stmt = "SELECT * FROM my_user"
cursor.execute(stmt)
results = cursor.fetchall()

users = User.from_results(results)
```

## Nested models

For more complicated queries returning a nested object, models can be nested. To
parse them automatically prefix query fields with `name__` format prefixes.

Say we have a Vehicle table with a reference to an owner (User).
```python
import sqlite3

from pydantic_db import Model


class User(Model):
    id: int
    name: str


class Vehicle(Model):
    id: int
    name: str
    owner: User

db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row

stmt = """
SELECT
    v.id,
    v.name,
    u.id AS owner__id,
    u.name AS owner__name
FROM my_vehicle v
JOIN my_user u ON v.owner_id = u.id
"""
cursor.execute(stmt)
results = cursor.fetchall()

vehicles = Vehicle.from_results(results)
```

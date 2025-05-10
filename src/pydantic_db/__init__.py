from __future__ import annotations

import typing

import pydantic

DictConvertible = typing.Union[typing.Mapping[str, typing.Any], typing.Iterable[tuple[str, typing.Any]]]


class Model(pydantic.BaseModel):
    _eq_excluded_fields: typing.ClassVar[set[str]] = set()

    def __eq__(self, other: object) -> bool:
        """Equality method to support testing."""
        if type(self) is type(other):
            return all(
                getattr(self, field) == getattr(other, field)
                for field in type(self).model_fields
                if field not in self._eq_excluded_fields
            )
        return False

    @classmethod
    def _parse_result(cls: type[typing.Self], result: DictConvertible) -> dict:
        return dict(result)

    @classmethod
    def from_result(cls: type[typing.Self], result: DictConvertible) -> typing.Self:
        data = cls._parse_result(result)
        return cls(**data)

    @classmethod
    def from_results(cls: type[typing.Self], results: list[DictConvertible]) -> list[typing.Self]:
        return [cls.from_result(r) for r in results]


class NestedModel(Model):
    _skip_prefix_fields: typing.ClassVar[dict[str, str] | None] = None

    @classmethod
    def _parse_result(cls: type[typing.Self], result: DictConvertible) -> dict:
        data = super()._parse_result(result)
        skip_prefix_map = cls._skip_prefix_fields or {}
        prefixes = {k.split("__")[0] for k in data if "__" in k}

        for prefix in prefixes:
            skip_field = skip_prefix_map.get(prefix)
            if skip_field and data[f"{prefix}__{skip_field}"] is None:
                data[prefix] = None
            else:
                data[prefix] = {
                    **{k.replace(f"{prefix}__", ""): v for k, v in data.items() if k.startswith(f"{prefix}__")},
                }

        return data

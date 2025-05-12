from __future__ import annotations

import types
import typing

import pydantic

DictConvertible = typing.Union[typing.Mapping[str, typing.Any], typing.Iterable[tuple[str, typing.Any]]]

try:
    UnionType = types.UnionType
except AttributeError:
    UnionType = typing._UnionGenericAlias  # noqa: SLF001


class Model(pydantic.BaseModel):
    _eq_excluded_fields: typing.ClassVar[set[str]] = set()
    _skip_prefix_fields: typing.ClassVar[dict[str, str] | None] = None

    @classmethod
    def _pdb_model_fields(cls: type[typing.Self]) -> dict[str, Model]:
        ret = {}
        for k, f in cls.model_fields.items():
            if type(f.annotation) is UnionType:
                for arg in typing.get_args(f.annotation):
                    if isinstance(arg, type) and issubclass(arg, Model):
                        ret[k] = arg
                        break
            elif isinstance(f.annotation, type) and issubclass(f.annotation, Model):
                ret[k] = f.annotation
        return ret

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
    def _parse_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> dict:
        # Strip prefixes away
        data = {k.replace(f"{prefix}", ""): v for k, v in dict(result).items() if k.startswith(prefix)}

        skip_prefix_map = cls._skip_prefix_fields or {}
        model_fields = cls._pdb_model_fields()

        for model_prefix in model_fields:
            skip_field = skip_prefix_map.get(model_prefix)
            if skip_field and data.get(f"{model_prefix}__{skip_field}") is None:
                data[model_prefix] = None
            else:
                # Unions
                data[model_prefix] = model_fields[model_prefix].from_result(
                    {
                        k.replace(f"{model_prefix}__", ""): v
                        for k, v in data.items()
                        if k.startswith(f"{model_prefix}__")
                    },
                )

        return data

    @classmethod
    def from_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> typing.Self:
        data = cls._parse_result(result, prefix=prefix)
        return cls(**data)

    @classmethod
    def from_results(cls: type[typing.Self], results: list[DictConvertible], *, prefix: str = "") -> list[typing.Self]:
        return [cls.from_result(r, prefix=prefix) for r in results]

    @classmethod
    def as_columns(cls, base_table: str | None = None) -> list[tuple[str, ...]]:
        return list(cls.as_typed_columns(base_table=base_table).keys())

    @classmethod
    def as_typed_columns(cls, base_table: str | None = None) -> dict[tuple[str, ...], type[typing.Any] | None]:
        columns: dict[tuple[str, ...], type[typing.Any] | None] = {}
        model_fields = cls._pdb_model_fields()

        for field, field_data in cls.model_fields.items():
            if field in model_fields:
                for column, annotation in model_fields[field].as_typed_columns().items():
                    columns[(field, *column)] = annotation

            elif base_table is None:
                columns[(field,)] = field_data.annotation
            else:
                columns[(base_table, field)] = field_data.annotation

        return columns

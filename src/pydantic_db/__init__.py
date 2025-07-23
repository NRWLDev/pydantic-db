from __future__ import annotations

import types
import typing

import pydantic

DictConvertible = typing.Union[typing.Mapping[str, typing.Any], typing.Iterable[tuple[str, typing.Any]]]

try:
    UnionType = types.UnionType
except AttributeError:
    UnionType = typing._UnionGenericAlias  # noqa: SLF001


class ModelConfig(typing.NamedTuple):
    model: Model
    optional: bool
    is_list: bool


class Model(pydantic.BaseModel):
    _eq_excluded_fields: typing.ClassVar[set[str]] = set()
    _skip_prefix_fields: typing.ClassVar[dict[str, str] | None] = None
    _skip_sortable_fields: typing.ClassVar[set[str] | None] = None
    _hash_fields: typing.ClassVar[set[str]] = {"id"}

    def __hash__(self) -> int:
        return hash("".join([str(getattr(self, field)) for field in self._hash_fields]))

    @classmethod
    def _pdb_model_fields(cls: type[typing.Self]) -> dict[str, ModelConfig]:
        ret = {}
        for k, f in cls.model_fields.items():
            if type(f.annotation) is UnionType:
                args = typing.get_args(f.annotation)
                for arg in args:
                    if isinstance(arg, type) and issubclass(arg, Model):
                        ret[k] = ModelConfig(arg, optional=type(None) in args, is_list=False)
                        break
            elif type(f.annotation) is typing.GenericAlias and f.annotation.__origin__ is list:
                args = typing.get_args(f.annotation)
                ret[k] = ModelConfig(args[0], optional=True, is_list=True)
            elif isinstance(f.annotation, type) and issubclass(f.annotation, Model):
                ret[k] = ModelConfig(f.annotation, optional=False, is_list=False)

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

        for model_prefix, config in model_fields.items():
            skip_field = skip_prefix_map.get(model_prefix, "id")
            if config.optional and data.get(f"{model_prefix}__{skip_field}") is None:
                data[model_prefix] = None if not config.is_list else []
            else:
                # Unions
                data[model_prefix] = config.model.from_result(
                    {
                        k.replace(f"{model_prefix}__", ""): v
                        for k, v in data.items()
                        if k.startswith(f"{model_prefix}__")
                    },
                )
                if config.is_list:
                    data[model_prefix] = [data[model_prefix]]

        return data

    @classmethod
    def from_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> typing.Self:
        data = cls._parse_result(result, prefix=prefix)
        return cls(**data)

    @classmethod
    def from_results(
        cls: type[typing.Self],
        results: typing.Sequence[DictConvertible],
        *,
        prefix: str = "",
    ) -> list[typing.Self]:
        model_fields = cls._pdb_model_fields()
        list_fields = [model_prefix for model_prefix, config in model_fields.items() if config.is_list]
        results = [cls.from_result(r, prefix=prefix) for r in results]
        results_ = {}
        if list_fields:
            for r in results:
                k = hash(r)
                if k not in results_:
                    results_[k] = r
                else:
                    for f in list_fields:
                        new = getattr(r, f)
                        existing = getattr(results_[k], f)
                        if new and new[0] not in existing:
                            getattr(results_[k], f).append(new[0])

            results = list(results_.values())

        return results

    @classmethod
    def as_columns(cls, base_table: str | None = None) -> list[tuple[str, ...]]:
        return list(cls.as_typed_columns(base_table=base_table).keys())

    @classmethod
    def as_typed_columns(cls, base_table: str | None = None) -> dict[tuple[str, ...], type[typing.Any] | None]:
        columns: dict[tuple[str, ...], type[typing.Any] | None] = {}
        model_fields = cls._pdb_model_fields()

        for field, field_data in cls.model_fields.items():
            if field in model_fields:
                for column, annotation in model_fields[field].model.as_typed_columns().items():
                    if base_table is None:
                        columns[(field, *column)] = annotation
                    else:
                        columns[(base_table, field, *column)] = annotation

            elif base_table is None:
                columns[(field,)] = field_data.annotation
            else:
                columns[(base_table, field)] = field_data.annotation

        return columns

    @classmethod
    def sortable_fields(cls, *, top_level: bool = True) -> list[str]:
        fields = set()
        model_fields = cls._pdb_model_fields()
        skipped_fields = cls._skip_sortable_fields or set()

        for field in cls.model_fields:
            if field in skipped_fields:
                continue

            if field in model_fields:
                if top_level:
                    fields.add(field)

                for column in model_fields[field].model.sortable_fields(top_level=False):
                    sortable_field = f"{field}__{column}"
                    if sortable_field in skipped_fields:
                        continue

                    fields.add(sortable_field)
            else:
                fields.add(field)

        return sorted(fields)

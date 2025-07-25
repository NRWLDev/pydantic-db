from __future__ import annotations

import types
import typing
from collections import defaultdict

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
    _cached_model_fields: typing.ClassVar[dict[str, ModelConfig] | None] = None

    def __hash__(self) -> int:
        return hash("".join([str(getattr(self, field)) for field in self._hash_fields]))

    @classmethod
    def _dict_hash(cls, data: dict) -> int:
        return hash("".join([str(data[field]) for field in cls._hash_fields]))

    @classmethod
    def _process_list(
        cls,
        annotation: typing.GenericAlias[list],
        args: list[typing.Any] | None = None,
    ) -> ModelConfig | None:
        ret = None
        args_ = typing.get_args(annotation)
        args = args or args_
        for arg in args_:
            if isinstance(arg, type) and issubclass(arg, Model):
                ret = ModelConfig(arg, optional=type(None) in args, is_list=True)
                break

        return ret

    @classmethod
    def _process_union(cls, annotation: UnionType) -> ModelConfig | None:
        ret = None
        args = typing.get_args(annotation)
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, Model):
                ret = ModelConfig(arg, optional=type(None) in args, is_list=False)
                break
            if type(arg) is typing.GenericAlias and arg.__origin__ is list:
                ret = cls._process_list(arg, args)
                if ret:
                    break

        return ret

    @classmethod
    def _pdb_model_fields(cls: type[typing.Self]) -> dict[str, ModelConfig]:
        if cls._cached_model_fields is None:
            ret = {}
            for k, f in cls.model_fields.items():
                if type(f.annotation) is UnionType:
                    mc = cls._process_union(f.annotation)
                    if mc:
                        ret[k] = mc
                        break
                elif type(f.annotation) is typing.GenericAlias and f.annotation.__origin__ is list:
                    mc = cls._process_list(f.annotation)
                    if mc:
                        ret[k] = mc
                        break
                elif isinstance(f.annotation, type) and issubclass(f.annotation, Model):
                    ret[k] = ModelConfig(f.annotation, optional=False, is_list=False)

            cls._cached_model_fields = ret

        return cls._cached_model_fields

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
            if (config.optional or config.is_list) and data.get(f"{model_prefix}__{skip_field}") is None:
                data[model_prefix] = None
            else:
                data[model_prefix] = {
                    k.replace(f"{model_prefix}__", ""): v for k, v in data.items() if k.startswith(f"{model_prefix}__")
                }

        return data

    @classmethod
    def one(cls: type[typing.Self], data: DictConvertible | list[DictConvertible], *, prefix: str = "") -> typing.Self:
        if isinstance(data, list):
            results = cls.from_results(data, prefix=prefix)
            result = results[0]
        else:
            result = cls.from_result(data, prefix=prefix)

        return result

    @classmethod
    def all(cls: type[typing.Self], data: list[DictConvertible], *, prefix: str = "") -> typing.Self:
        return cls.from_results(data, prefix=prefix)

    @classmethod
    def from_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> typing.Self:
        data = cls._parse_result(result, prefix=prefix)
        model_fields = cls._pdb_model_fields()
        for model_prefix, config in model_fields.items():
            if data[model_prefix]:
                value = config.model.from_result(data[model_prefix])
                data[model_prefix] = [value] if config.is_list else value

        return cls(**data)

    @classmethod
    def _flatten_data(cls: type[typing.Self], data: list[dict], list_fields: dict[str, bool]) -> list[dict]:
        child_data = defaultdict(lambda: defaultdict(list))
        for row in data:
            hash_ = cls._dict_hash(row)
            for list_field in list_fields:
                v = row.get(list_field)
                if v and v not in child_data[hash_][list_field]:
                    child_data[hash_][list_field].append(v)

        # Ensure uniqueness at top level
        ret, seen = [], set()
        for row in data:
            hash_ = cls._dict_hash(row)
            if hash_ not in seen:
                for list_field, optional in list_fields.items():
                    if list_field in child_data[hash_] or not optional:
                        row[list_field] = child_data[hash_][list_field]
                ret.append(row)
            seen.add(hash_)

        return ret

    @classmethod
    def from_results(
        cls: type[typing.Self],
        results: typing.Sequence[DictConvertible],
        *,
        prefix: str = "",
    ) -> list[typing.Self]:
        model_fields = cls._pdb_model_fields()
        list_fields = {model_prefix: config.optional for model_prefix, config in model_fields.items() if config.is_list}
        data = [cls._parse_result(r, prefix=prefix) for r in results]
        if list_fields:
            data = cls._flatten_data(data, list_fields)

        results = []
        for row in data:
            for model_prefix, config in model_fields.items():
                if row[model_prefix]:
                    if config.is_list:
                        row[model_prefix] = config.model.from_results(row[model_prefix])
                    else:
                        row[model_prefix] = config.model.from_result(row[model_prefix])
            results.append(cls(**row))

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

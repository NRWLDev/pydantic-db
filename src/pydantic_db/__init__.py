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
    """Simple configuration to track details extracted from annotations."""

    model: Model
    optional: bool
    is_list: bool


class Model(pydantic.BaseModel):
    """Base model class.

    Handles model equality checks, hashing (for uniqueness checks, and storing
    in dict/sets), and processing database result(s).
    """

    _eq_excluded_fields: typing.ClassVar[set[str]] = set()
    _skip_prefix_fields: typing.ClassVar[dict[str, str] | None] = None
    _skip_sortable_fields: typing.ClassVar[set[str] | None] = None
    _hash_fields: typing.ClassVar[set[str]] = {"id"}
    _cached_model_fields: typing.ClassVar[dict[str, ModelConfig] | None] = None

    def __hash__(self) -> int:
        """Generate a unique hash for a model.

        By default will hash the `id` field of a model, to override this
        behaviour define the unique set of fields to hash with the class var
        `_hash_fields`.
        """
        return hash("".join([str(getattr(self, field)) for field in self._hash_fields]))

    @classmethod
    def _dict_hash(cls, data: dict) -> int:
        """Generate a unique hash for a dict representation of a model.

        See __hash__ for details.
        """
        return hash("".join([str(data[field]) for field in cls._hash_fields]))

    @classmethod
    def _process_list(
        cls,
        annotation: typing.GenericAlias[list],
        args: list[typing.Any] | None = None,
    ) -> ModelConfig | None:
        """Parse a list annotation to determine if it is a Model field."""
        ret = None
        args_ = typing.get_args(annotation)
        args = args or args_
        for arg in args_:
            # Check the args for `list[...]` for a Model subclass.
            if isinstance(arg, type) and issubclass(arg, Model):
                ret = ModelConfig(arg, optional=type(None) in args, is_list=True)
                break

        return ret

    @classmethod
    def _process_union(cls, annotation: UnionType) -> ModelConfig | None:
        """Parse a union annotation to determine if it is a Model field."""
        ret = None
        args = typing.get_args(annotation)
        for arg in args:
            # Check the args for `X | Y | ...` for a Model subclass.
            if isinstance(arg, type) and issubclass(arg, Model):
                ret = ModelConfig(arg, optional=type(None) in args, is_list=False)
                break

            # For optional lists, process the internal type annotation
            if type(arg) is typing.GenericAlias and arg.__origin__ is list:
                ret = cls._process_list(arg, args)
                if ret:
                    break

        return ret

    @classmethod
    def _pdb_model_fields(cls: type[typing.Self]) -> dict[str, ModelConfig]:
        """Extract model fields along with configuration details.

        Determine if a field refers to a Model, if it is optional and if it is
        list based (in need of flattening to maintain top level uniqueness.
        """
        if cls._cached_model_fields is None:
            ret = {}
            type_hints = typing.get_type_hints(cls)
            for field in cls.model_fields:
                annotation = type_hints[field]
                if type(annotation) is UnionType or type(annotation) is typing._UnionGenericAlias:  # noqa: SLF001
                    mc = cls._process_union(annotation)
                    if mc:
                        ret[field] = mc
                elif type(annotation) is typing.GenericAlias and annotation.__origin__ is list:
                    mc = cls._process_list(annotation)
                    if mc:
                        ret[field] = mc
                elif isinstance(annotation, type) and issubclass(annotation, Model):
                    ret[field] = ModelConfig(annotation, optional=False, is_list=False)

            cls._cached_model_fields = ret

        return cls._cached_model_fields

    def __eq__(self, other: object) -> bool:
        """Check model equality.

        By default equality checks all fields of a model are equal. To override
        this behaviour set the class var `_eq_excluded_fields` to define fields
        that can be ignored when checking equality.
        """
        if type(self) is type(other):
            return all(
                getattr(self, field) == getattr(other, field)
                for field in type(self).model_fields
                if field not in self._eq_excluded_fields
            )
        return False

    @classmethod
    def _parse_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> dict:
        """Convert a database result representation to a dict.

        Additionally parse any `model_prefix__*` fields to a `model_prefix`
        dictionary containing child fields.
        """
        # Strip prefixes away
        data = {k.replace(f"{prefix}", ""): v for k, v in dict(result).items() if k.startswith(prefix)}

        skip_prefix_map = cls._skip_prefix_fields or {}
        model_fields = cls._pdb_model_fields()

        for model_prefix, config in model_fields.items():
            skip_field = skip_prefix_map.get(model_prefix, "id")
            if data.get(model_prefix):
                continue
            if (config.optional or config.is_list) and data.get(f"{model_prefix}__{skip_field}") is None:
                data[model_prefix] = None
            else:
                data[model_prefix] = {
                    k.replace(f"{model_prefix}__", ""): v for k, v in data.items() if k.startswith(f"{model_prefix}__")
                }

        return data

    @classmethod
    def one(cls: type[typing.Self], data: DictConvertible | list[DictConvertible], *, prefix: str = "") -> typing.Self:
        """Helper function to process a database result or result set into a single model instance.

        When dealing with list based children, a result set will contain a copy
        of the parent for every child. This results in a request for a single
        object returning more then one row and can not be processed directly by
        `Model.from_result`. `Model.one` will process a single result or a
        result set to flatten any child lists into a single field and return
        the final unique parent object.
        """
        if isinstance(data, list):
            results = cls.from_results(data, prefix=prefix)
            result = results[0]
        else:
            result = cls.from_result(data, prefix=prefix)

        return result

    @classmethod
    def all(cls: type[typing.Self], data: list[DictConvertible], *, prefix: str = "") -> typing.Self:
        """Helper function to process a database result set into multiple model instances."""
        return cls.from_results(data, prefix=prefix)

    @classmethod
    def from_result(cls: type[typing.Self], result: DictConvertible, *, prefix: str = "") -> typing.Self:
        """Process a single database result object into a Model instance.

        If the model contains lists of child Models, use `Model.one(results)`,
        to convert multiple rows to a single instance.
        """
        data = cls._parse_result(result, prefix=prefix)
        model_fields = cls._pdb_model_fields()
        for model_prefix, config in model_fields.items():
            if data[model_prefix]:
                value = config.model.from_result(data[model_prefix])
                data[model_prefix] = [value] if config.is_list else value

        return cls(**data)

    @classmethod
    def _flatten_data(cls: type[typing.Self], data: list[dict], list_fields: dict[str, bool]) -> list[dict]:
        """Flatten child list fields and maintain uniqueness (and order) of parent objects."""
        child_data = defaultdict(lambda: defaultdict(list))
        # Extract all child objects for each parent object
        for row in data:
            hash_ = cls._dict_hash(row)
            for list_field in list_fields:
                v = row.get(list_field)
                if isinstance(v, list):
                    child_data[hash_][list_field] = v
                elif v and v not in child_data[hash_][list_field]:
                    child_data[hash_][list_field].append(v)

        # Populate each unique top level object, with the extracted child fields.
        ret, seen = [], set()
        for row in data:
            hash_ = cls._dict_hash(row)
            if hash_ not in seen:
                for list_field, optional in list_fields.items():
                    if list_field in child_data[hash_] or not optional:
                        """
                        If there is child data, or the field is not nullable,
                        populate with the child data or the default list if the
                        key does not exist in the underlying result set.
                        """
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
        """Convert a result set to a list of model instances.

        If the model contains `list[Model]` fields, flatten the data to ensure
        uniqueness and ordering of parent objects.
        """
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
                        # If the flattened data is a list, pass to the child model to process (including nested models/lists)
                        row[model_prefix] = config.model.from_results(row[model_prefix])
                    else:
                        row[model_prefix] = config.model.from_result(row[model_prefix])
            results.append(cls(**row))

        return results

    @classmethod
    def as_columns(cls, base_table: str | None = None) -> list[tuple[str, ...]]:
        """Extract nested field name tuples."""
        return list(cls.as_typed_columns(base_table=base_table).keys())

    @classmethod
    def as_typed_columns(
        cls,
        base_table: str | None = None,
        seen: set[type[Model]] | None = None,
    ) -> dict[tuple[str, ...], type[typing.Any] | None]:
        """Extract nested field name tuples and the associated field type annotation."""
        # Prevent nested circular dependencies upon seeing an ancestor
        seen = seen or set()
        seen.add(cls)
        columns: dict[tuple[str, ...], type[typing.Any] | None] = {}
        model_fields = cls._pdb_model_fields()

        for field, field_data in cls.model_fields.items():
            if field in model_fields and model_fields[field].model not in seen:
                for column, annotation in model_fields[field].model.as_typed_columns(seen=seen).items():
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
    def sortable_fields(cls, *, seen: set[type[Model]] | None = None, recurse: bool = True) -> list[str]:
        """Extract `__` separated string representations of all model fields.

        Extract all fields and sub fields of nested models to validate user
        provided sorting against available query fields.

        To exclude fields override the class var `_skip_sortable_fields`.
        """
        # Prevent nested circular dependencies upon seeing an ancestor
        fields = set()
        seen = seen or set()
        seen.add(cls)
        model_fields = cls._pdb_model_fields()
        skipped_fields = cls._skip_sortable_fields or set()

        for field in cls.model_fields:
            if field in skipped_fields:
                continue

            if field not in model_fields:
                fields.add(field)
            elif field in model_fields and recurse:
                for column in model_fields[field].model.sortable_fields(
                    seen=seen,
                    recurse=model_fields[field].model not in seen,
                ):
                    sortable_field = f"{field}__{column}"
                    if sortable_field in skipped_fields:
                        continue

                    fields.add(sortable_field)

        return sorted(fields)

import typing

import pydantic

DictConvertible = typing.Union[typing.Mapping[str, typing.Any], typing.Iterable[tuple[str, typing.Any]]]


class Model(pydantic.BaseModel):
    _eq_excluded_fields = set()

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

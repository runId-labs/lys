"""
Unit tests for find_fields_at_max_length (string fields cut by a schema maxLength).
"""
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from lys.apps.ai.utils.schema_limits import find_fields_at_max_length


class _Item(BaseModel):
    label: str = Field(..., json_schema_extra={"maxLength": 5})


class _Response(BaseModel):
    title: str = Field(..., json_schema_extra={"maxLength": 10})
    body: str = Field(..., max_length=20)
    note: Optional[Annotated[str, Field(json_schema_extra={"maxLength": 8})]] = None
    items: List[_Item] = Field(default_factory=list)
    free: str = ""


class _Cat(BaseModel):
    kind: Literal["cat"] = "cat"
    name: str = Field("", json_schema_extra={"maxLength": 6})


class _Dog(BaseModel):
    kind: Literal["dog"] = "dog"
    bio: str = Field("", json_schema_extra={"maxLength": 4})


class _Zoo(BaseModel):
    tags: Dict[str, Annotated[str, Field(max_length=5)]] = Field(default_factory=dict)
    pet: Union[_Cat, _Dog] = Field(default_factory=_Cat, discriminator="kind")


class _A(BaseModel):
    kind: Literal["a"] = "a"
    text: str = Field("", max_length=5)


class _B(BaseModel):
    kind: Literal["b"] = "b"
    text: str = Field("", max_length=50)


class _SharedField(BaseModel):
    item: Union[_A, _B]


class _SharedFieldDiscriminated(BaseModel):
    item: Union[_A, _B] = Field(discriminator="kind")


class TestFindFieldsAtMaxLength:

    def test_no_field_at_limit(self):
        response = _Response(title="short", body="short body")
        assert find_fields_at_max_length(response) == []

    def test_json_schema_extra_bound_reached(self):
        response = _Response(title="x" * 10, body="ok")
        assert find_fields_at_max_length(response) == ["title"]

    def test_max_length_bound_reached(self):
        response = _Response(title="ok", body="y" * 20)
        assert find_fields_at_max_length(response) == ["body"]

    def test_optional_string_branch_bound_reached(self):
        response = _Response(title="ok", body="ok", note="z" * 8)
        assert find_fields_at_max_length(response) == ["note"]

    def test_optional_none_is_ignored(self):
        response = _Response(title="ok", body="ok", note=None)
        assert find_fields_at_max_length(response) == []

    def test_nested_list_items_are_walked(self):
        response = _Response(title="ok", body="ok", items=[_Item(label="ok"), _Item(label="abcde")])
        assert find_fields_at_max_length(response) == ["items[1].label"]

    def test_unbounded_field_is_never_reported(self):
        response = _Response(title="ok", body="ok", free="w" * 10_000)
        assert find_fields_at_max_length(response) == []

    def test_one_below_limit_is_not_reported(self):
        response = _Response(title="x" * 9, body="ok")
        assert find_fields_at_max_length(response) == []

    def test_dict_values_are_walked(self):
        zoo = _Zoo(tags={"a": "ok", "b": "abcde"})
        assert find_fields_at_max_length(zoo) == ["tags.b"]

    def test_discriminated_union_branch_is_walked(self):
        assert find_fields_at_max_length(_Zoo(pet=_Dog(bio="abcd"))) == ["pet.bio"]
        assert find_fields_at_max_length(_Zoo(pet=_Cat(name="abcdef"))) == ["pet.name"]

    def test_discriminated_union_below_limit(self):
        assert find_fields_at_max_length(_Zoo(pet=_Dog(bio="abc"))) == []

    def test_union_branches_sharing_a_field_use_the_matching_bound(self):
        for model in (_SharedField, _SharedFieldDiscriminated):
            assert find_fields_at_max_length(model(item=_B(text="0123456789"))) == []
            assert find_fields_at_max_length(model(item=_B(text="x" * 50))) == ["item.text"]
            assert find_fields_at_max_length(model(item=_A(text="abcde"))) == ["item.text"]

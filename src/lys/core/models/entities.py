from typing import Dict

from pydantic import BaseModel


class EntityModel(BaseModel):
    __hash__ = object.__hash__
    id: None = None

    @classmethod
    def validate(cls, data: Dict):
        cls(**data)
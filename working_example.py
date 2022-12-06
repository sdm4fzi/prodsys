from pydantic import BaseModel, parse_obj_as
from typing import Union, Literal
from enum import Enum

class TypeEnum(str, Enum):
    aa = "a"
    bb = "b"


class InfoA(BaseModel):
    a: str
    type: Literal[TypeEnum.aa]


class InfoB(BaseModel):
    b: str
    type: Literal[TypeEnum.bb]



class FunctionA(BaseModel):
    info: InfoA
    # type: Literal["a"]



class FunctionB(BaseModel):
    info: InfoB
    # type: Literal["b"]


d = [
        {"type": "a", "a": "a string"},
        {"type": "b", "b": "b string"},
        {"type": "a", "a": "a2 string"},
]

InfoUnion = Union[InfoA, InfoB]
FunctionUnion = Union[FunctionA, FunctionB]

function_dict = {
    TypeEnum.aa: "haha",
    TypeEnum.bb: "hbhb",
}

info_models = []
for item in d:
    info_model = parse_obj_as(InfoUnion, item)
    print(info_model)
    # function_model = parse_obj_as(FunctionUnion, {"type": info_model.type, "info": info_model})
    function_model = parse_obj_as(FunctionUnion, {"info": info_model})
    print(function_model)
    print(type(info_model))
    print(type(function_model))

    print(function_dict[info_model.type])
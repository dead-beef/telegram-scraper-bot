from typing import Dict, Optional, Any, TypeVar, Union, Iterable

T = TypeVar('T')
JsonObject = Dict[str, Any]
Number = Union[int, float]
Arguments = Optional[Iterable[str]]
Cookies = Dict[str, Dict[str, str]]

class CommandError(Exception):
    pass

from urllib.parse import urlparse, ParseResult
from typing import Dict, Optional, Type, NamedTuple

class Link(NamedTuple):
    type: str
    id: str

    LINK_TO_URL = {
        'hb': 'http://httpbin.org/{0}',
        'vk': 'https://vk.com/{0}',
        'ig': 'https://instagram.com/{0}'
    }

    NETLOC_TO_TYPE = {
        'httpbin.org': 'hb',
        'vk.com': 'vk',
        'instagram.com': 'ig'
    }

    def __eq__(self, link) -> bool:
        return (
            isinstance(link, Link) and
            self.type == link.type and
            self.id == link.id or
            isinstance(link, dict) and
            self.type == link.get('type') and
            self.id == link.get('id')
        )

    def to_json(self) -> Dict[str, str]:
        return {
            'type': self.type,
            'id': self.id
        }

    def to_url(self) -> str:
        try:
            return self.LINK_TO_URL[self.type].format(self.id)
        except KeyError:
            raise ValueError(f'unknown link type: {repr(self.type)}')

    @classmethod
    def from_json(cls: Type, json: Dict[str, str]):
        try:
            return cls(json['type'], json['id'])
        except KeyError:
            raise ValueError(f'invalid link json: {repr(json)}')

    @classmethod
    def from_url(cls: Type, url: str):
        type_: Optional[str] = None
        id_: Optional[str] = None
        parsed_url: ParseResult = urlparse(url)

        try:
            type_ = cls.NETLOC_TO_TYPE[parsed_url.netloc] # pylint:disable=no-member
            id_ = parsed_url.path[1:]
        except KeyError:
            pass

        if type_ is None or id_ is None:
            raise ValueError(f'unknown link type: {repr(parsed_url)}')

        return cls(type_, id_)

from typing import Optional, List

import yarl

from .link import Link

class Post:
    def __init__(self,
                 link: Link,
                 id_: int,
                 url: str,
                 title: str,
                 text: str = '',
                 image_urls: Optional[List[str]] = None):
        self.id: int = id_
        self.url: str = url
        self.title: str = title
        self.text: str = text
        self.image_urls: List[str] = image_urls or []
        self.link: Link = link

    def to_html(self) -> str:
        return (
            f'<a href="{str(yarl.URL(self.url))}">{self.title}</a>\n{self.text}'
        )

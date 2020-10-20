import html
import time
from typing import List

from ..link import Link
from ..post import Post
from .loader import Loader


async def parse_hb(loader: Loader,
                   link: Link,
                   content: str,
                   last_post_id: int) -> List[Post]:
    return [Post(
        link, int(time.time()), link.to_url(),
        html.escape(repr(link)), f'<code>{html.escape(content)}</code>',
        ['https://via.placeholder.com/64', 'https://via.placeholder.com/128']
    )]

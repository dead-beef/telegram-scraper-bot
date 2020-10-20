import re
import html
from typing import List, Optional

import bs4
import yarl

from ..link import Link
from ..post import Post
from .loader import Loader


Element = bs4.BeautifulSoup


def parse_image(loader: Loader, img: Element) -> Optional[str]:
    style = img['style']
    match = re.search(r'url\(([^)]+)\)', style)
    if match is None:
        loader.logger.warning('no image url found in style %r', style)
        return None
    return match.group(1)

def parse_post(loader: Loader, link: Link, post: Element) -> Post:
    post_id: int = -1
    url: str = ''
    title: str = ''
    text: str = ''
    images: List[str] = []

    base_url = yarl.URL(link.to_url() + '/')

    post_full_id: str = post['id']
    if post_full_id.startswith('post-'):
        post_full_id = post_full_id[5:]
    parts: List[str] = post_full_id.split('_')
    if len(parts) != 2:
        raise ValueError('invalid post id: %r' % post_full_id)
    post_id = int(parts[1])

    link: Optional[Element] = post.find('a', class_='post_link')
    if link is not None:
        url = str(base_url.join(yarl.URL(link['href'])))
    else:
        loader.logger.warning('no link found in post %r', post)

    title_: Optional[Element] = post.find('a', class_='author')
    if title_ is not None:
        title = title_.string
        if title is None:
            title = post_full_id
            loader.logger.warning('no title found in post %r', post)
    else:
        title = post_full_id
        loader.logger.warning('no title found in post %r', post)

    text_: Optional[Element] = post.find(class_='wall_post_text')
    if text is not None:
        expand: Optional[Element] = text_.find(class_='wall_post_more')
        if expand is not None:
            expand.decompose()
        text = '\n'.join(text_.stripped_strings)

    images_ = post.find_all(class_='image_cover')
    images = [
        url for url in (parse_image(loader, img) for img in images_) if url
    ]

    if not (text or images):
        loader.logger.error('empty post: %r', post)

    return Post(
        link, post_id, url, html.escape(title), html.escape(text), images
    )

async def parse_vk(loader: Loader, link: Link,
                   content: str, last_post_id: int) -> List[Post]:
    page: Element = bs4.BeautifulSoup(content, 'html.parser')
    posts: List[Element] = page.find_all(class_='post')
    if not posts:
        loader.logger.error('no posts found in %r', page)
    return [parse_post(loader, link, post) for post in reversed(posts)]

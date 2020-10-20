import html
import time
from typing import List
from datetime import datetime
from itertools import takewhile

try:
    import instaloader
except ImportError:
    instaloader = None

from ..link import Link
from ..post import Post
from .loader import Loader

def get_instaloader(loader: Loader) -> instaloader.Instaloader:
    if instaloader is None:
        raise RuntimeError(f'instaloader is not installed')
    ret: instaloader.Instaloader = instaloader.Instaloader()
    if loader.proxy is not None:
        ret.context._session.proxies.update({ # pylint:disable=protected-access
            'http': loader.proxy,
            'https': loader.proxy,
        })
    return ret

def load_ig_sync(
        loader: Loader,
        link: Link,
        last_post_id: int
) -> List[instaloader.Post]:
    if last_post_id <= 0:
        last_post_id = int(time.time()) - 172800 #604800
    last_post_date: datetime = datetime.utcfromtimestamp(last_post_id)

    iloader: instaloader.Instaloader = get_instaloader(loader)

    profile: instaloader.Profile
    try:
        id_ = int(link.id)
    except ValueError:
        profile = instaloader.Profile.from_username(iloader.context, link.id)
    else:
        profile = instaloader.Profile.from_id(iloader.context, id_)

    posts: List[instaloader.Post] = list(takewhile(
        lambda post: post.date_utc > last_post_date,
        profile.get_posts()
    ))
    posts.reverse()

    for post in posts:
        try:
            post.sidecar_nodes = list(post.get_sidecar_nodes())
        except instaloader.InstaloaderException as ex:
            loader.logger.error('get_sidecar_nodes: %r', ex, exc_info=ex)
            post.sidecar_nodes = []

    return posts

async def load_ig(loader: Loader,
                  link: Link,
                  last_post_id: int) -> List[instaloader.Post]:
    return await loader.run_in_executor(
        load_ig_sync, loader, link, last_post_id
    )

def parse_post(link: Link, post: instaloader.Post) -> Post:
    post_id: int = int(post.date_utc.timestamp())
    url: str = f'https://instagram.com/p/{post.shortcode}/'
    title: str = url
    text: str = post.caption or ''
    images: List[str] = []

    if post.typename == 'GraphSidecar':
        for _, sidecar_node in post.sidecar_nodes:
            images.append(sidecar_node.display_url)
    elif post.typename == 'GraphImage':
        images.append(post.url)
    elif post.typename == 'GraphVideo':
        pass

    return Post(
        link, post_id, url, html.escape(title), html.escape(text), images
    )

async def parse_ig(loader: Loader,
                   link: Link,
                   content: List[instaloader.Post],
                   last_post_id: int) -> List[Post]:
    return [parse_post(link, post) for post in content]

import random
import asyncio
import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Optional, Dict, List, Type, Any, Coroutine, Callable

import yarl
import aiohttp
try:
    import aiohttp_socks
except ImportError:
    aiohttp_socks = None

from ..link import Link
from ..post import Post
from ..util import Number, Cookies

class Loader:
    def __init__(self,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 proxy: Optional[str] = None,
                 user_agent: Optional[str] = None,
                 min_delay: Number = 0.5,
                 max_delay: Number = 1,
                 max_connections: int = 10,
                 max_connections_per_host: int = 1,
                 max_workers: int = 1,
                 cookies: Optional[Cookies] = None):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self.executor: Executor = ThreadPoolExecutor(max_workers=max_workers)
        self.min_delay: Number = min_delay
        self.max_delay: Number = max_delay

        self.headers: Dict[str, str] = {}
        if user_agent is not None:
            self.headers['User-Agent'] = user_agent

        self.cookie_jar: aiohttp.CookieJar = aiohttp.CookieJar(unsafe=True)
        if cookies is not None:
            for url, url_cookies in cookies.items():
                self.cookie_jar.update_cookies(
                    url_cookies,
                    yarl.URL(url) if url else None
                )

        self.proxy: Optional[str] = proxy
        self.connector_class: Type = aiohttp.TCPConnector
        self.connector_kwargs: Dict[str, Any] = dict(
            loop=self.loop,
            limit=max_connections,
            limit_per_host=max_connections_per_host
        )
        if proxy:
            if aiohttp_socks is None:
                raise ValueError('install aiohttp_socks for proxy support')
            (proxy_type, host, port,
             username, password) = aiohttp_socks.utils.parse_proxy_url(proxy)
            self.connector_class = aiohttp_socks.ProxyConnector
            self.connector_kwargs.update(
                proxy_type=proxy_type, host=host, port=port,
                username=username, password=password
            )
        self.connector: aiohttp.BaseConnector = self.connector_class(
            **self.connector_kwargs
        )

        self.session: aiohttp.ClientSession = aiohttp.ClientSession(
            connector=self.connector,
            cookie_jar=self.cookie_jar,
            headers=self.headers,
            raise_for_status=True
        )

    async def close(self) -> None:
        self.logger.info('closing %s', self.__class__.__name__)
        await self.session.close()
        self.executor.shutdown()
        # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
        await asyncio.sleep(0.25)

    async def wait(self) -> None:
        delay: float = random.random() * (self.max_delay - self.min_delay)
        delay += self.min_delay
        await asyncio.sleep(delay)

    async def run_in_executor(self, func: Callable, *args):
        return await self.loop.run_in_executor(self.executor, func, *args)

    async def load(self,
                   link: Link,
                   last_post_id: int = 0) -> List[Post]:
        try:
            func: str = 'load_' + link.type
            do_load: Coroutine = getattr(self, func)
        except AttributeError:
            do_load = self.load_default

        await self.wait()
        content: Any = await do_load(link, last_post_id)
        return await self.parse(link, content, last_post_id)

    async def parse(self,
                    link: Link,
                    content: str,
                    last_post_id: int) -> List[Post]:
        try:
            func: str = 'parse_' + link.type
            parse: Coroutine = getattr(self, func)
            if not asyncio.iscoroutinefunction(parse):
                raise AttributeError('%r is not an async function' % func)
        except AttributeError as ex:
            self.logger.error(
                'no parse function for link type: %r',
                link, exc_info=ex
            )
            return []
        else:
            return await parse(link, content, last_post_id)

    async def load_default(self, link: Link, last_post_id: int) -> str:
        url: str = link.to_url()
        async with self.session.get(url) as response:
            return await response.text()

    @classmethod
    def add_loader(cls: Type, link_type: str, load: Coroutine) -> None:
        func = f'load_{link_type}'
        setattr(cls, func, load)

    @classmethod
    def add_parser(cls: Type, link_type: str, parse: Coroutine) -> None:
        func = f'parse_{link_type}'
        setattr(cls, func, parse)

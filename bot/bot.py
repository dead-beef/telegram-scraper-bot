import asyncio
import logging
from typing import Optional, List, Dict

import aiogram

from .config import BotConfig
from .commands import BotCommands
from .link import Link
from .post import Post
from .loader import Loader

class Bot:
    LOG_FORMAT: str = '[%(asctime).19s] [%(name)s] [%(levelname)s] %(message)s'

    def __init__(self,
                 config_path: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()

        self.started_polling: bool = False
        self.updating_links: bool = False
        self.started_updating_links: bool = False
        self.stopped_updating_links: Optional[asyncio.Future] = None
        self._update_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None

        self.config: BotConfig = BotConfig(config_path)
        self.proxy = self.config['proxy'] or None
        self.loader: Loader = Loader(
            loop=self.loop,
            proxy=self.proxy,
            **self.config['loader']
        )

        self.bot: aiogram.Bot = aiogram.Bot(
            token=self.config['token'],
            proxy=self.proxy or None,
            loop=self.loop,
            connections_limit=self.config['connections_limit']
        )
        self.dispatcher: aiogram.Dispatcher = aiogram.Dispatcher(
            self.bot, loop=self.loop
        )
        self.commands: BotCommands = BotCommands(self.config, self.dispatcher)

    async def init(self) -> None:
        self.logger.info('initializing bot')
        bot_user: aiogram.types.User = await self.bot.get_me()
        username: str = bot_user.mention[1:]
        self.logger.info('username = %r', username)
        self.commands.username = username

    async def run(self) -> None:
        try:
            await self.init()
            self.logger.info('running bot')
            bot_user: aiogram.types.User = await self.bot.get_me()
            self.commands.username = bot_user.mention[1:]
            await self.process_bot_updates()
            await self.process_link_updates()
        finally:
            self.save()

    async def start(self) -> None:
        try:
            await self.init()
            self.logger.info('starting bot')
            self.started_polling = True
            self._poll_task = asyncio.create_task(
                self.dispatcher.start_polling()
            )
            self._update_task = asyncio.create_task(self.start_updating_links())
            await asyncio.gather(self._poll_task, self._update_task)
        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.info('cancelled')
        except Exception as ex:
            self.logger.error('%r', ex, exc_info=ex)
            raise
        finally:
            self.save()

    async def start_updating_links(self):
        if self.updating_links:
            return
        self.logger.info('start updating links')
        self.started_updating_links = True
        self.updating_links = True
        self.stopped_updating_links = self.loop.create_future()
        try:
            while self.updating_links:
                try:
                    await self.process_link_updates()
                    await asyncio.sleep(self.config['link_update_interval'])
                except (KeyboardInterrupt, asyncio.CancelledError):
                    self.logger.info('start_updating_links cancelled')
                    raise
                except Exception as ex:
                    self.logger.error(
                        'error updating links: %r',
                        repr(ex), exc_info=ex
                    )
        finally:
            self.logger.info('stopped updating links')
            self.updating_links = False
            self.stopped_updating_links.set_result(None)
            self._update_task = None

    def stop_updating_links(self):
        self.logger.info('stop updating links')
        self.updating_links = False
        if self._update_task is not None:
            self.logger.info('cancel link update task')
            self._update_task.cancel()

    async def process_bot_updates(self) -> None:
        offset: Optional[int] = self.config['last_update_id']
        if offset < 0:
            offset = None
        else:
            offset += 1
        timeout: int = self.config['update_timeout']
        self.logger.info(
            'getting updates (offset=%r timeout=%r)',
            offset, timeout
        )
        updates: List[aiogram.types.Update] = await self.bot.get_updates(
            offset=offset, timeout=timeout
        )
        if updates:
            self.logger.info('processing %d updates', len(updates))
            aiogram.Bot.set_current(self.bot)
            await self.dispatcher.process_updates(updates)
            self.config['last_update_id'] = updates[-1].update_id
        else:
            self.logger.info('no updates')

    async def process_link_updates(self) -> None:
        self.logger.info('processing link updates')
        updates: Dict[int, List[Post]] = await self.process_links()
        self.logger.debug('got link updates %r', updates)

        self.logger.info('creating new posts')
        results: List[Optional[Exception]] = await asyncio.gather(
            *(self.create_posts(chat_id, posts)
              for chat_id, posts in updates.items()),
            return_exceptions=True
        )
        for chat_id, res in zip(updates.keys(), results):
            if isinstance(res, (KeyboardInterrupt, asyncio.CancelledError)):
                raise res
            if isinstance(res, Exception):
                self.logger.error(
                    'error creating new posts in chat %r: %r',
                    chat_id, res, exc_info=res
                )
        self.logger.info('processed link updates')

    async def process_links(self) -> Dict[int, List[Post]]:
        self.logger.info('processing links')
        links: Dict[Link, str] = self.config.get_links()
        results: List[Optional[Exception]] = await asyncio.gather(
            *(self.loader.load(link, last_post_id)
              for link, last_post_id in links.items()),
            return_exceptions=True
        )
        self.logger.info('processed links %r', results)

        posts: Dict[Link, List[Post]] = {}
        for link, res in zip(links.keys(), results):
            self.logger.debug('link result %r %r', link, res)
            if isinstance(res, Exception):
                self.logger.error(
                    'error processing link %r: %r',
                    link, res, exc_info=res
                )
            elif res:
                posts[link] = res
            else:
                self.config.set_link_update_time(link)

        return self.config.get_chat_posts(posts)

    async def create_post(self, chat_id: int, post: Post) -> None:
        self.logger.info('creating post in %r: %r', chat_id, post)
        msg: aiogram.types.Message = await self.bot.send_message(
            chat_id, post.to_html(),
            parse_mode=aiogram.types.ParseMode.HTML,
            disable_web_page_preview=True
        )
        if post.image_urls:
            for url in post.image_urls:
                try:
                    await self.bot.send_photo(
                        chat_id, url,
                        reply_to_message_id=msg.message_id
                    )
                except Exception as ex:
                    self.logger.error(
                        'error sending image %r: %r',
                        url, ex, exc_info=ex
                    )
        self.config.update_last_post_id(chat_id, post)

    async def create_posts(self, chat_id: int, posts: List[Post]) -> None:
        for post in posts:
            await self.create_post(chat_id, post)

    def save(self) -> None:
        self.logger.info('saving bot state')
        self.config.save()

    async def stop(self) -> None:
        self.logger.info('stopping bot')
        stop = []
        if self.started_polling:
            self.logger.info('stop polling')
            self.dispatcher.stop_polling()
            self._poll_task.cancel()
            stop.append(self.dispatcher.wait_closed())
        if self.started_updating_links:
            self.logger.info('stop updating links')
            self.stop_updating_links()
            stop.append(self.stopped_updating_links)
        if stop:
            await asyncio.gather(*stop)
        await asyncio.gather(self.bot.close(), self.loader.close())

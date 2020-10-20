import re
import html
import json
import asyncio
import logging
from functools import wraps
from typing import Optional, List, Tuple, Coroutine

import aiogram
from aiogram.dispatcher.handler import SkipHandler

from .config import BotConfig
from .link import Link
from .util import CommandError, JsonObject

class BotCommands:
    HELP: str = '''
commands:
    /start, /help - bot help
    /chatinfo - show chat info

admin commands:
    /watch &lt;url&gt; - add link to current chat
    /unwatch &lt;url&gt; - remove link from current chat
    /unwatch - remove all links from current chat
    /admin [user_id or reply] - add admin
    /admin [user_id or reply] false - remove admin

admin commands in private chat:
    /watch &lt;chat_id&gt; &lt;url&gt; - add link to chat by id
    /unwatch &lt;chat_id&gt; &lt;url&gt; - remove link from chat by id
    /unwatch &lt;chat_id&gt;- remove all links from chat by id
'''

    def __init__(self,
                 config: BotConfig,
                 dispatcher: aiogram.Dispatcher,
                 username: str = ''):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.config: BotConfig = config
        self.username: str = username
        self.dispatcher = dispatcher

        self.add_handler(self.match_command_username)
        self.add_handler(self.help, commands=['start', 'help'])
        self.add_handler(self.chat_info, commands=['chatinfo'])
        self.add_handler(self.can_use_admin_commands)
        self.add_handler(self.watch, commands=['watch'])
        self.add_handler(self.unwatch, commands=['unwatch'])
        self.add_handler(self.admin, commands=['admin'])

    def add_handler(self, handler: Coroutine, *args, **kwargs) -> None:
        handler = self.wrap_handler(handler)
        self.dispatcher.register_message_handler(handler, *args, **kwargs)

        try:
            commands: List[str] = kwargs['commands']
        except KeyError:
            pass
        else:
            del kwargs['commands']
            kwargs['regexp'] = r'^/(%s)\b' % '|'.join(
                re.escape(cmd) for cmd in commands
            )

        self.dispatcher.register_channel_post_handler(handler, *args, **kwargs)

    def wrap_handler(self, handler: Coroutine) -> Coroutine:
        @wraps(handler)
        async def wrapped_handler(msg: aiogram.types.Message):
            try:
                res = await handler(msg)
                if isinstance(res, str) and res:
                    await msg.reply(res)
                elif isinstance(res, tuple):
                    text, kwargs = res
                    await msg.reply(text, **kwargs)
            except (SkipHandler, asyncio.CancelledError):
                raise
            except CommandError as ex:
                try:
                    await msg.reply(str(ex))
                except Exception:
                    pass
            except Exception as ex:
                self.logger.error(
                    'error in handler %r: %r',
                    handler.__name__, ex, exc_info=ex
                )
                try:
                    await msg.reply(repr(ex))
                except Exception:
                    pass
        return wrapped_handler

    async def match_command_username(self, msg: aiogram.types.Message) -> None:
        command: List[str] = msg.get_command().split('@', 1)
        if len(command) == 2 and command[1] != self.username:
            return

        name: str
        id_: str
        if msg.from_user is not None:
            name = msg.from_user.mention
            id_ = msg.from_user.id
        else:
            name = msg.chat.mention or msg.chat.title
            id_ = msg.chat.id
        self.logger.info('%r (%r): %r', name, id_, msg.text)

        raise SkipHandler

    async def help(self, msg: aiogram.types.Message) -> None:
        await msg.reply(self.HELP, parse_mode=aiogram.types.ParseMode.HTML)

    async def can_use_admin_commands(self, msg: aiogram.types.Message) -> None:
        if (msg.from_user is not None and
            not self.config.is_admin(msg.from_user.id)):
            await msg.reply('permission denied')
        elif (not self.config['public_admin_commands_enabled'] and
              msg.chat.type != aiogram.types.ChatType.PRIVATE):
            await msg.reply('admin commands are disabled in public chats')
        else:
            raise SkipHandler

    def _get_watch_args(self,
                        msg: aiogram.types.Message,
                        optional_link: bool = False) -> Tuple[int, Optional[Link]]:
        private: bool = msg.chat.type == aiogram.types.ChatType.PRIVATE
        command: str = msg.get_command()
        args: str = msg.get_args().split()
        chat_id: int
        url: Optional[str] = None
        link: Optional[Link] = None
        min_args: int = 0
        max_args: int = 1

        usage = f'usage: {command}'
        if private:
            usage += ' <chat_id>'
            min_args += 1
            max_args += 1
        if optional_link:
            usage += ' [url]'
        else:
            usage += ' <url>'
            min_args += 1

        if len(args) < min_args or len(args) > max_args:
            raise CommandError(usage)

        if private:
            try:
                chat_id = int(args[0])
            except ValueError as ex:
                raise CommandError(str(ex))
            try:
                url = args[1]
            except IndexError:
                pass
        else:
            chat_id = msg.chat.id
            try:
                url = args[0]
            except IndexError:
                pass

        if url is not None:
            try:
                link = Link.from_url(url)
            except ValueError as ex:
                raise CommandError(str(ex))

        return chat_id, link

    async def chat_info(self, msg: aiogram.types.Message):
        self.config.update_chat_info(msg.chat)
        chat_json: Optional[JsonObject] = self.config.get_chat_config(msg.chat.id)
        if chat_json is None:
            chat_json = {
                'id': msg.chat.id,
                'title': msg.chat.full_name,
                'mention': msg.chat.mention,
                'url': await msg.chat.get_url()
            }
            try:
                chat_json['shifted_id'] = msg.chat.shifted_id
            except TypeError:
                chat_json['shifted_id'] = chat_json['id']
        res: str = json.dumps(chat_json, indent=2, sort_keys=False)
        await msg.reply(
            f'<code>{html.escape(res)}</code>',
            parse_mode=aiogram.types.ParseMode.HTML
        )

    async def watch(self, msg: aiogram.types.Message) -> str:
        chat_id, link = self._get_watch_args(msg)
        if self.config.add_link(chat_id, link):
            return f'added {repr(link)} to chat {chat_id}'
        return f'{repr(link)} already exists in chat {chat_id}'

    async def unwatch(self, msg: aiogram.types.Message) -> str:
        chat_id, link = self._get_watch_args(msg, True)

        if link is not None:
            if self.config.remove_link(chat_id, link):
                return f'removed {repr(link)} from chat {chat_id}'
            return f'{repr(link)} does not exist in chat {chat_id}'

        self.config.remove_all_links(chat_id)
        return f'removed all links from chat {chat_id}'

    async def admin(self, msg: aiogram.types.Message) -> str:
        usage: str = 'usage: /admin [user_id] [true|false]'
        args: List[str] = msg.get_args().split()
        user_id: Optional[int] = None
        add_admin: bool = True

        if len(args) > 2:
            raise CommandError(usage)
        if len(args) == 2:
            try:
                user_id = int(args[0])
            except ValueError as ex:
                raise CommandError(str(ex))
            add_admin = args[1].lower() != 'false'
        elif len(args) == 1:
            if args[0].isdigit():
                user_id = int(args[0])
            else:
                add_admin = args[0].lower() != 'false'

        if user_id is None:
            if msg.reply_to_message is not None:
                user_id = msg.reply_to_message.from_user.id
            else:
                raise CommandError('missing user id')

        if add_admin:
            if self.config.add_admin(user_id):
                return f'added admin {user_id}'
            return f'user {user_id} is already an admin'
        if self.config.remove_admin(user_id):
            return f'removed admin {user_id}'
        return f'user {user_id} is not an admin'

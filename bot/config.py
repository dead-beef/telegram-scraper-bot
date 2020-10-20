import os
import json
import time
import logging
from copy import deepcopy
from typing import Dict, Optional, Any, List

import aiogram

from .link import Link
from .post import Post
from .util import T, JsonObject

class BotConfigError(Exception):
    pass

class BotConfig:
    DEFAULTS: JsonObject = {
        'token': '',
        'proxy': '',
        'public_admin_commands_enabled': False,
        'last_update_id': -1,
        'update_timeout': 1,
        'link_update_interval': 86400,
        'connections_limit': 1,
        'loader': {
            'user_agent': (
                'Mozilla/5.0 (X11; Linux x86_64)'
                ' AppleWebKit/537.36 (KHTML, like Gecko)'
                ' Chrome/51.0.2704.79 Safari/537.36'
            ),
            'min_delay': 0.5,
            'max_delay': 1,
            'max_connections': 1,
            'max_connections_per_host': 1,
            'max_workers': 1,
            'cookies': {
            }
        },
        'admins': [],
        'chats': []
    }

    def __init__(self, path: str):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.json: JsonObject = deepcopy(self.DEFAULTS)
        self.path: str = path
        self.load()

    def __str__(self):
        return json.dumps(self.json, indent=2, sort_keys=False)

    def __getitem__(self, key: str) -> Any:
        return self.json[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.json[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.json.get(key, default)

    def load(self) -> None:
        self.logger.info('loading bot config from %r', self.path)
        with open(self.path, 'r') as fp:
            data = json.load(fp)
        self.extend(self.json, data)

    def save(self, path: Optional[str] = None) -> None:
        path = path or self.path
        tmp_path = path + '.tmp'
        self.logger.info('saving bot config to %r', tmp_path)
        data = str(self)
        with open(tmp_path, 'w') as fp:
            fp.write(data)
        self.logger.info('renaming %r to %r', tmp_path, path)
        os.rename(tmp_path, path)

    def check_type(self, dst: Any, src: Any, path: str = '') -> None:
        self.logger.debug('check_type %r %r %r', path, type(dst), type(src))
        number = (int, float)
        if not (
                isinstance(src, type(dst)) or
                isinstance(src, number) and isinstance(dst, number)
        ):
            raise BotConfigError(
                f'invalid type of {path}:'
                f' expected {type(dst).__name__}, got {type(src).__name__}'
            )

    def extend(self, dst: T, src: T, path: str = '<root>') -> None:
        self.logger.debug('extend %r %r %r', dst, src, path)
        self.check_type(dst, src, path)

        if isinstance(dst, dict):
            for key, value in src.items():
                try:
                    old_value = dst[key]
                except KeyError:
                    #self.logger.warning('unknown key %r in %s', key, path)
                    dst[key] = value
                    continue
                path_ = f'{path}.{key}'
                if isinstance(old_value, (dict, list)):
                    self.extend(old_value, value, path_)
                else:
                    self.check_type(old_value, value, path_)
                    dst[key] = value
        elif isinstance(dst, list):
            for i, value in enumerate(src):
                path_ = f'{path}[{i}]'
                if i >= len(dst):
                    dst.append(value)
                else:
                    old_value = dst[i]
                    if isinstance(old_value, (dict, list)):
                        self.extend(old_value, value, path_)
                    else:
                        self.check_type(old_value, value, path_)
                        dst[i] = value
        else:
            raise TypeError(
                f'can not extend object of type {type(dst).__name__}'
            )

    def is_admin(self, user_id: int) -> bool:
        return user_id in self['admins']

    def add_admin(self, user_id: int) -> bool:
        if self.is_admin(user_id):
            return False
        self['admins'].append(user_id)
        return True

    def remove_admin(self, user_id: int) -> bool:
        try:
            self['admins'].remove(user_id)
            return True
        except ValueError:
            return False

    def has_link(self, chat_id: int, link: Link) -> bool:
        links: List[Link] = self.get_chat_config(chat_id).get('links', [])
        return link in links

    def get_chat_config(self,
                        chat_id: int,
                        create: bool = False) -> Optional[JsonObject]:
        try:
            chats = self['chats']
        except KeyError:
            chats = []
            self['chats'] = chats

        try:
            return next(chat for chat in chats if chat['id'] == chat_id)
        except StopIteration:
            if not create:
                return None
            chat_json = {
                'id': chat_id,
                'links': []
            }
            chats.append(chat_json)
            return chat_json

    def update_chat_info(self,
                         chat: aiogram.types.Chat,
                         create: bool = False) -> None:
        chat_json: JsonObject = self.get_chat_config(chat.id, create)
        if chat_json is None:
            return
        #chat_json['id'] = chat.id
        try:
            chat_json['shifted_id'] = chat.shifted_id
        except TypeError:
            chat_json['shifted_id'] = chat_json['id']
        chat_json['mention'] = chat.mention
        chat_json['title'] = chat.full_name
        #chat_json['url'] = await chat.get_url()

    def add_link(self, chat_id: int, link: Link) -> bool:
        if self.has_link(chat_id, link):
            return False
        self.get_chat_config(chat_id, True)['links'].append(link.to_json())
        return True

    def remove_link(self, chat_id: int, link: Link) -> bool:
        try:
            self.get_chat_config(chat_id, True)['links'].remove(link)
            return True
        except ValueError:
            return False

    def remove_all_links(self, chat_id: int) -> None:
        self.get_chat_config(chat_id, True)['links'] = []

    def get_links(self) -> Dict[Link, int]:
        update_interval: int = self['link_update_interval']
        current_time: int = int(time.time())
        self.logger.info('getting links')
        res: Dict[Link, int] = {}
        for chat in self.get('chats', ()):
            for link in chat.get('links', ()):
                link_: Link = Link.from_json(link)
                last_post_id: int = link.get('last_post_id', 0)
                last_update_time: int = link.get('last_update_time', 0)
                if current_time - last_update_time < update_interval:
                    self.logger.info(
                        'skipping link %r in chat %r: %r < %r',
                        link, chat['id'],
                        current_time - last_update_time, update_interval
                    )
                    continue
                if link_ in res:
                    res[link_] = min(res[link_], last_post_id)
                else:
                    res[link_] = last_post_id
        self.logger.info('got links %r', res)
        return res

    def get_chat_posts(self,
                       posts: Dict[Link, List[Post]]) -> Dict[int, List[Post]]:
        self.logger.info('getting new posts')
        res: Dict[int, List[Post]] = {}
        for chat in self.get('chats', ()):
            chat_id = chat['id']
            dst: List[Post] = []
            res[chat_id] = dst
            for link in chat.get('links', ()):
                link_: Link = Link.from_json(link)
                last_post_id: int = link.get('last_post_id', 0)
                src: List[Post] = [post for post in posts.get(link_, [])
                                   if post.id > last_post_id]
                if src:
                    dst.extend(src)
                else:
                    link['last_update_time'] = int(time.time())
        self.logger.info('got new posts %r', res)
        return res

    def update_last_post_id(self, chat_id: int, post: Post) -> None:
        chat: Optional[JsonObject] = self.get_chat_config(chat_id)
        if chat is None:
            raise ValueError(
                f'invalid chat id: {chat_id}: not in {self["chats"]}'
            )
        links: JsonObject = chat.get('links', ())
        link: JsonObject = links[links.index(post.link)]
        link['last_post_id'] = post.id
        link['last_update_time'] = int(time.time())

    def set_link_update_time(self, link: Link) -> None:
        timestamp = int(time.time())
        self.logger.info('set link update time %r %r', link, timestamp)
        for chat in self.get('chats', ()):
            for link_ in chat.get('links', ()):
                if link == link_:
                    link_['last_update_time'] = timestamp

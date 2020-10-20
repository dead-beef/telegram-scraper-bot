from .loader import Loader

from .hb import parse_hb
from .vk import parse_vk
from .ig import load_ig, parse_ig

Loader.add_parser('hb', parse_hb)
Loader.add_parser('vk', parse_vk)
Loader.add_loader('ig', load_ig)
Loader.add_parser('ig', parse_ig)

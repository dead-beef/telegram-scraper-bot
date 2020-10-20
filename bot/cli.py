import asyncio
import logging
from argparse import ArgumentParser, Namespace

from .bot import Bot
from .util import Arguments

def create_arg_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('config', metavar='FILE', help='config file')
    parser.add_argument(
        '-l', '--log-level',
        default='info',
        choices=('critical', 'error', 'warning', 'info', 'debug'),
        help='log level (default: %(default)s)'
    )
    parser.add_argument(
        '-w', '--watch',
        action='store_true',
        help=''
    )
    parser.add_argument(
        '-s', '--single-run',
        dest='watch',
        action='store_false',
        help='(default)'
    )
    return parser

def parse_args(argv: Arguments = None) -> Namespace:
    parser = create_arg_parser()
    if argv is not None:
        return parser.parse_args(argv)
    return parser.parse_args()

def main(argv: Arguments = None) -> None:
    args: Namespace = parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format=Bot.LOG_FORMAT
    )

    logger: logging.Logger = logging.getLogger(__name__)
    bot: Bot = Bot(args.config)
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(bot.start() if args.watch else bot.run())
    except KeyboardInterrupt:
        logger.info('cancelled')
    except Exception as ex:
        logger.error('%r', ex, exc_info=ex)
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()

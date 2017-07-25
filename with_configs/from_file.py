#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import logging
#
from colorlog import ColoredFormatter
# from subprocess import Popen, PIPE, STDOUT
from voluptuous import Schema, Url, Required, Optional, MultipleInvalid
import yaml
from fuzzywuzzy import fuzz
import pprint
from subprocess import Popen, PIPE, STDOUT
import os
from typing import NamedTuple
from glob import glob

__author__ = 'atty_l'

# ---- LOG -----
LOGFORMAT = '%(log_color)s[%(asctime)s][%(levelname)s][%(filename)s][%(funcName)s] %(message)s'

formatter = ColoredFormatter(LOGFORMAT)
LOG_LEVEL = logging.DEBUG
stream = logging.StreamHandler()
stream.setLevel(LOG_LEVEL)
stream.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(stream)
# --------------


# ----- PPRINT ------
# https://stackoverflow.com/questions/1713038/super-fails-with-error-typeerror-argument-1-must-be-type-not-classobj
class P(pprint.PrettyPrinter, object):
    def __init__(self, max_length=10):
        """

        :param max_length:
        """
        super(P, self).__init__()
        self._max_length = max_length
        self._ellipsis = ["..."]

    def _format(self, o, *args, **kwargs):
        if isinstance(o, list):
            if len(o) > self._max_length:
                o = o[:self._max_length] + self._ellipsis
        return pprint.PrettyPrinter._format(self, o, *args, **kwargs)
# --------------


# ----- NAMEDTUPLE -------
# https://stackoverflow.com/questions/34269772/type-hints-in-namedtuple
SAFARI_CONFIG = NamedTuple(
    'SAFARI_CONFIG',
    [
        ('user', str),
        ('password', str),
        ('not_download', bool),
        ('skip_if_exist', bool),
        ('epub_output', str)
    ])
# --------------


def _create_schema():
    """

    :return:
    """
    # https://stackoverflow.com/questions/3262569/validating-a-yaml-document-in-python
    # https://pypi.python.org/pypi/voluptuous/
    # https://julien.danjou.info/blog/2015/python-schema-validation-voluptuous
    # Create the validation schema
    return Schema({
        Required('safari_user'): str,
        Required('safari_password'): str,
        Optional('safari_urls'): [Url(str)],
        Optional('safari_ids'): [str]
    })


def crypt_config(config, fuzzy_pattern='safari_password', min_ratio=80):
    """

    :param config:
    :param fuzzy_pattern:
    :param min_ratio:
    :return:

    >>> crypt_config({'password': 'toto', 'passwd': 'tata', 'key': 'value'})
    {'passwd': '****', 'password': '****', 'key': 'value'}

    """
    return dict(
        (k, '*' * len(v) if fuzz.token_set_ratio(k, fuzzy_pattern) > min_ratio else v)
        for k, v in config.items()
    )


def get_book_informations_from_url(url):
    """

    :param url:
    :return:
    """
    url_tokens = url.split('/')
    book_id = filter(lambda token: token.isdigit(), url_tokens)[0]
    book_name = url_tokens[url_tokens.index(book_id) - 1]
    return book_id, book_name


def _sprocess_cmd(cmd):
    """

    :param cmd:
    :return:
    """
    p = Popen(cmd.split(), stdout=PIPE, stdin=PIPE, stderr=STDOUT, bufsize=1)
    p.stdin.close()  # eof
    for line in iter(p.stdout.readline, ''):
        print line,  # do something with the output here
    p.stdout.close()
    rc = p.wait()
    logger.debug("rc: {}".format(rc))


def _launch_scrapy_book_downloader(container,
                                   functor_to_get_id_name_book,
                                   config):
    """

    :param container:
    :param functor_to_get_id_name_book:
    :param config:
    :return:
    """
    nb_downloaded = 0
    for item in container:
        try:
            book_id, book_name = functor_to_get_id_name_book(item)

            # scrapy crawl SafariBooks -a user=$1 -a password=$2 -a bookid=$3
            cmd = "scrapy crawl SafariBooks -a user={} -a password={} -a bookid={}".format(
                config.user,
                config.password,
                book_id
            )
            logger.debug("cmd: {}".format(cmd))

            if not config.not_download:
                if config.skip_if_exist:
                    # https://stackoverflow.com/questions/2225564/get-a-filtered-list-of-files-in-a-directory
                    find_books_with_id = glob(os.path.join(config.epub_output, "*{}*.epub".format(book_id)))
                    if not find_books_with_id:
                        _sprocess_cmd(cmd)
                    else:
                        logger.info(
                            "'skip-if_exist' option activate and used for {} \
                            because {} exist.".format(book_id, find_books_with_id))
            else:
                logger.info("'not_download' option activate and used for {}.".format(book_id))

        except Exception, e:
            logger.error("Exception: {}".format(e))
        else:
            nb_downloaded += 1

    return nb_downloaded


def _launch_sbd_from_urls(urls, config):
    """
    sbd: Scrappy BooksOnline Downloader

    :param urls:
    :type urls: list
    :param config:
     :type config: SAFARI_CONFIG
    :return:
    """
    return _launch_scrapy_book_downloader(urls, lambda url: get_book_informations_from_url(url), config)


def _launch_downloader_from_ids(ids, config):
    """

    :param ids:
    :type ids: list
    :param config:
     :type config: SAFARI_CONFIG
    :return:
    """
    return _launch_scrapy_book_downloader(ids, lambda id_book: (id_book, id_book), config)


def _generate_configuration(args, yaml_config):
    """

    :param args:
    :param yaml_config:
    :return:
    :rtype: NamedTuple
    """
    # https://stackoverflow.com/questions/24902258/pycharm-warning-about-not-callable
    # noinspection PyCallingNonCallable
    return SAFARI_CONFIG(
        user=yaml_config['safari_user'],
        password=yaml_config['safari_password'],
        not_download=args.not_download,
        skip_if_exist=args.skip_if_exist,
        epub_output=args.epub_output
    )


def _process(args):
    """
    :param args:
    :return:

    """
    yaml_configs = list(yaml.load_all(args.configs))

    schema = _create_schema()

    # TODO: a revoir ce changement (a l'arrache) de path ...
    os.chdir('..')

    for yaml_config in yaml_configs:
        logger.debug("yaml_config: {}".format(P().pprint(crypt_config(yaml_config))))
        try:
            # use the validation schema
            schema(yaml_config)
        except MultipleInvalid as e:
            logger.error("Schema not valid !\nException {}".format(e))
        else:
            config = _generate_configuration(args, yaml_config)

            if 'safari_urls' in yaml_config:
                _launch_sbd_from_urls(yaml_config['safari_urls'], config)

            if 'safari_ids' in yaml_config:
                _launch_downloader_from_ids(yaml_config['safari_ids'], config)


def parse_arguments():
    """

    :return:
    """
    parser = argparse.ArgumentParser()
    #
    parser.add_argument('configs', type=argparse.FileType('r'),
                        help='<Required> Configs file')
    parser.add_argument('-o', '--epub-output', type=str, default='./epub/',
                        help="EPub output directory (default: %(default)s")
    #
    parser.add_argument("--not-download", action="store_true", default=False,
                        help="Desactivate downloads (debug purpose)")
    parser.add_argument("--skip-if-exist", action="store_true", default=True,
                        help="Skip downloads if the book already exist")
    #
    parser.add_argument("-v", "--verbose", action="store_true", default=False,
                        help="increase output verbosity")
    # return parsing
    return parser.parse_args()


def main():
    args = parse_arguments()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    _process(args)


if __name__ == '__main__':
    main()

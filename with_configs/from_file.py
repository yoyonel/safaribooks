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
import getpass

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
NT_Safari_Config = NamedTuple(
    'SAFARI_CONFIG',
    [
        ('user', str),
        ('password', str),
        ('not_download', bool),
        ('skip_if_exist', bool),
        ('epub_output', str)
    ])
# --------------


# ----- INPUT USER ------
try:
    input = raw_input
except NameError:
    pass


def prompt(message, errormessage, isvalid, _input=input):
    """Prompt for input given a message and return that value after verifying the input.

    Keyword arguments:
    message -- the message to display when asking the user for the value
    errormessage -- the message to display when the value fails validation
    isvalid -- a function that returns True if the value given by the user is valid
    """
    res = None
    while res is None:
        res = _input(str(message)+': ')
        if not isvalid(res):
            print str(errormessage)
            res = None
    return res


def prompt_for_password(message, errormessage, isvalid):
    """

    :param message:
    :param errormessage:
    :param isvalid:
    :return:
    """
    return prompt(message, errormessage, isvalid, _input=getpass.getpass)
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
        Optional('safari_user'): str,
        Optional('safari_password'): str,
        Optional('safari_urls'): [Url(str)],
        Optional('safari_ids'): [str]
    })


def crypt_config(config, fuzzy_pattern='safari_password', min_ratio=80):
    """

    :param config:
    :type config: dict
    :param fuzzy_pattern:
    :type fuzzy_pattern: str
    :param min_ratio:
    :type min_ratio: int
    :return:
    :rtype: dict

    >>> crypt_config({'password': 'toto', 'passwd': 'tata', 'key': 'value'})
    {'passwd': '****', 'password': '****', 'key': 'value'}

    """
    return dict(
        (k, '*' * len(v) if v and fuzz.token_set_ratio(k, fuzzy_pattern) > min_ratio else v)
        for k, v in config.items()
    )


def get_book_informations_from_url(url):
    """

    :param url:
    :type url: str
    :return:
    :rtype: (str, str)
    """
    url_tokens = filter(lambda token: bool(token), url.split('/'))

    # pas forcement vrai, par exemple:
    # - url: https://www.safaribooksonline.com/library/view/the-pragmatic-programmer/020161622X/
    # -> '020161622X' n'est pas un full digit, car 'X' n'est pas un digit.
    #
    # book_id = filter(lambda token: token.isdigit(), url_tokens)[0]
    # id_token_for_book_name = url_tokens.index(book_id) - 1
    # book_name = url_tokens[id_token_for_book_name]

    # On va supposer que l'ID est le dernier token
    book_id = url_tokens[-1]
    # si ID du book est le dernier element => le NAME du book est l'avant dernier element
    book_name = url_tokens[-2]

    return book_id, book_name


def _sprocess_cmd(cmd):
    """

    :param cmd:
    :type cmd: str
    """
    p = Popen(cmd.split(), stdout=PIPE, stdin=PIPE, stderr=STDOUT, bufsize=1)
    p.stdin.close()  # eof
    for line in iter(p.stdout.readline, ''):
        print line,  # do something with the output here
    p.stdout.close()
    rc = p.wait()
    logger.debug("rc: {}".format(rc))


def _launch_scrapy_book_downloader(container, functor_to_get_id_name_book, config):
    """

    :param container:
    :type container: iter
    :param functor_to_get_id_name_book:
    :param config:
    :return:
    :rtype: int
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
                            "'skip-if_exist' activate and used for {} because {} exist.".format(
                                book_id, find_books_with_id)
                        )
            else:
                logger.info("'not_download' activate and used for {}.".format(book_id))

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


def _generate_configuration_for_sdb(args, yaml_config):
    """

    :param args:
    :param yaml_config:
    :type yaml_config: dict
    :return:
    :rtype: NamedTuple
    """
    # user
    try:
        sbo_user = yaml_config['safari_user']
    except KeyError:
        sbo_user = prompt(message="Enter your SafariBookOnline user name",
                          errormessage="The user name must be provided",
                          isvalid=lambda v: len(v) > 0)
    # password
    try:
        sbo_password = yaml_config['safari_password']
    except KeyError:
        sbo_password = prompt_for_password(message="Enter your SafariBookOnline password",
                                           errormessage="The password must be provided",
                                           isvalid=lambda v: len(v) > 0)
        logger.debug("sbo_password: {}".format(sbo_password))

    # https://stackoverflow.com/questions/24902258/pycharm-warning-about-not-callable
    # noinspection PyCallingNonCallable
    return NT_Safari_Config(
        user=sbo_user,
        password=sbo_password,
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
        logger.debug("yaml_config: {}".format(P().pformat(crypt_config(yaml_config))))

        try:
            # use the validation schema
            schema(yaml_config)
        except MultipleInvalid as e:
            logger.error("Schema not valid !\nException {}".format(e))
        else:
            sdb_config = _generate_configuration_for_sdb(args, yaml_config)

            if 'safari_urls' in yaml_config:
                _launch_sbd_from_urls(yaml_config['safari_urls'], sdb_config)

            if 'safari_ids' in yaml_config:
                _launch_downloader_from_ids(yaml_config['safari_ids'], sdb_config)


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

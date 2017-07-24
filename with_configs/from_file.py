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
        Optional('safari_ids'): [str, int]
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


def _launch_downloader_from_urls(urls,
                                 safari_user,
                                 safari_password,
                                 not_download=False):
    """

    :param urls:
    :param safari_user:
    :param safari_password:
    :param not_download:
    :return:
    """
    nb_downloaded = 0
    for safari_url in urls:
        try:
            logger.debug("safari_url: {}".format(safari_url))

            book_id, book_name = get_book_informations_from_url(safari_url)
            logger.debug("Safari book id: {}".format(book_id))

            if not not_download:
                # scrapy crawl SafariBooks -a user=$1 -a password=$2 -a bookid=$3
                cmd = "scrapy crawl SafariBooks -a user={} -a password={} -a bookid={}".format(
                    safari_user,
                    safari_password,
                    book_id
                )
                logger.debug("cmd: {}".format(cmd))
                #
                _sprocess_cmd(cmd)
        except Exception, e:
            logger.error("Exception: {}".format(e))
        else:
            nb_downloaded += 1

    return nb_downloaded


def _launch_downloader_from_ids(ids,
                                safari_user,
                                safari_password,
                                not_download=False):
    """

    :param ids:
    :param safari_user:
    :param safari_password:
    :param not_download:
    :return:
    """
    nb_downloaded = 0
    for safari_id in ids:
        try:
            logger.debug("safari_id: {}".format(safari_id))

            book_id = safari_id
            logger.debug("Safari book id: {}".format(book_id))

            if not not_download:
                # scrapy crawl SafariBooks -a user=$1 -a password=$2 -a bookid=$3
                cmd = "scrapy crawl SafariBooks -a user={} -a password={} -a bookid={}".format(
                    safari_user,
                    safari_password,
                    book_id
                )
                logger.debug("cmd: {}".format(cmd))
                #
                _sprocess_cmd(cmd)
        except Exception, e:
            logger.error("Exception: {}".format(e))
        else:
            nb_downloaded += 1

    return nb_downloaded


def _process(args):
    """

    :param args:
    :return:

    """
    yaml_configs = list(yaml.load_all(args.configs))

    schema = _create_schema()

    os.chdir('..')

    for yaml_config in yaml_configs:
        logger.debug("yaml_config: {}".format(P().pprint(crypt_config(yaml_config))))
        try:
            # use the validation schema
            schema(yaml_config)
        except MultipleInvalid as e:
            logger.error("Schema not valid !\nException {}".format(e))
        else:
            # get access login/password
            safari_user = yaml_config['safari_user']
            safari_password = yaml_config['safari_password']

            if 'safari_urls' in yaml_config:
                _launch_downloader_from_urls(yaml_config['safari_urls'],
                                             safari_user=safari_user,
                                             safari_password=safari_password,
                                             not_download=args.not_download)

            if 'safari_ids' in yaml_config:
                _launch_downloader_from_ids(yaml_config['safari_ids'],
                                            safari_user,
                                            safari_password,
                                            not_download=args.not_download)


def parse_arguments():
    """

    :return:
    """
    parser = argparse.ArgumentParser()
    #
    parser.add_argument('configs', type=argparse.FileType('r'),
                        help='<Required> Configs file')
    #
    parser.add_argument("-d", "--not-download", action="store_true", default=False,
                        help="Desactivate downloads (debug purpose)")
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

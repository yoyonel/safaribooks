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
from fuzzywuzzy import process

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
        Required('safari_urls'): [Url(str)],
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
        (k, '*'*len(v) if fuzz.token_set_ratio(k, fuzzy_pattern) > min_ratio else v)
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


def _process(args):
    """

    :param args:
    :return:

    """
    yaml_configs = list(yaml.load_all(args.configs))

    schema = _create_schema()

    for yaml_config in yaml_configs:
        logger.debug("yaml_config: {}".format(crypt_config(yaml_config)))
        try:
            # use the validation schema
            schema(yaml_config)
        except MultipleInvalid as e:
            logger.error("Schema not valid !\nException {}".format(e))
        else:
            # get access login/password
            safari_user = yaml_config['safari_user']
            safari_password = yaml_config['safari_password']

            for safari_url in yaml_config['safari_urls']:
                logger.debug("safari_url: {}".format(safari_url))

                book_id, book_name = get_book_informations_from_url(safari_url)

                if not args.not_download:
                    # launch_safaribooks_downloader(
                    #     book_id,
                    #     safari_user,
                    #     safari_password,
                    #     "books/",
                    #     book_name
                    # )
                    pass


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
    process(args)


if __name__ == '__main__':
    main()

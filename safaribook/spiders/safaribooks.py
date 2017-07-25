import os
import re
import shutil
from functools import partial
import codecs

import scrapy
from jinja2 import Template
from BeautifulSoup import BeautifulSoup

import ntpath

import json


null = None
false = False

PAGE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
{{body}}
</body>
</html>"""


class SafariBooksSpider(scrapy.Spider):
    toc_url = 'https://www.safaribooksonline.com/nest/epub/toc/?book_id='
    name = "SafariBooks"
    # allowed_domains = []
    start_urls = ["https://www.safaribooksonline.com/"]
    host = "https://www.safaribooksonline.com/"

    def __init__(self, user='', password='', bookid='', **kwargs):
        super(SafariBooksSpider, self).__init__(**kwargs)
        self.user = user
        self.password = password
        self.bookid = bookid
        self.book_name = ''
        self.info = {}
        #
        self.output_dir = kwargs.get('output', './output/{}/'.format(bookid))
        self.initialize_output(self.output_dir)
        #
        self.epub_output_dir = kwargs.get('epub_output', './')

    @staticmethod
    def initialize_output(output, rm_previous_output=True):
        """

        :param output:
        :param rm_previous_output:
        :return:
        """
        if rm_previous_output:
            # https://docs.python.org/2/library/shutil.html
            shutil.rmtree(output, ignore_errors=True)
        shutil.copytree('data/', output)

    def parse(self, response):
        return scrapy.FormRequest.from_response(
            response,
            formdata={"email": self.user, "password1": self.password},
            callback=self.after_login)

    def after_login(self, response):
        if 'Recommended For You' not in response.body:
            self.logger.error("Failed login")
            return
        yield scrapy.Request(self.toc_url + self.bookid, callback=self.parse_toc)

    @staticmethod
    def parse_cover_img(_, response, output_dir):
        # inspect_response(response, self)
        with open("{}/OEBPS/cover-image.jpg".format(output_dir), "w") as f:
            f.write(response.body)

    # @staticmethod
    def parse_content_img(self, img, response, output_dir):
        img_path = os.path.join("{}/OEBPS".format(output_dir), img)
        self.logger.debug("img_path: {}".format(img_path))

        img_dir = os.path.dirname(img_path)
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)

        with open(img_path, "wb") as f:
            f.write(response.body)

    def parse_page_json(self, title, bookid, response):
        # TODO: fix a potential exploit
        # Grosse erreur de code ! Une grosse possibilite d'injection de code a ce niveau (faille de securite).
        # En plus ca ne fonctionne pas tout le temps ! :-/
        # page_json = eval(response.body)
        # https://stackoverflow.com/questions/28843876/nulls-instead-of-nones-in-json-data-with-python
        page_json = json.loads(response.body)

        yield scrapy.Request(page_json["content"],
                             callback=partial(self.parse_page, title, bookid, page_json["full_path"],
                                              output_dir=self.output_dir))

    def parse_page(self, title, bookid, path, response, output_dir):
        template = Template(PAGE_TEMPLATE)

        # PATCH: Il y avait des soucys avec des sous chemins pour recuperer les pages html.
        # Certains books utilisent un sous repertoire 'xhtml/' (par exemple).
        # Ca cree potentiellement des pbs pour le rapatriement des images par la suite.
        # TODO: Stabiliser (refactorer) les chemins relatifs (pour les pages)

        # https://stackoverflow.com/questions/8384737/tract-file-name-from-path-no-matter-what-the-os-path-format
        # https://stackoverflow.com/questions/8384737/extract-file-name-from-path-no-matter-what-the-os-path-format
        # https://www.safaribooksonline.com/library/view/python-standard-library/0596000960/ch13s03.html
        filename = ntpath.basename(path)
        dirname = ntpath.dirname(path)
        output_dirname = "{}/OEBPS/".format(output_dir) + dirname
        if not os.path.exists(output_dirname):
            self.logger.warning("Path: '{}' doesn't exist !".format(output_dirname))
            os.mkdir(output_dirname)

        # with codecs.open("{}/OEBPS/".format(output_dir) + filename, "wb", "utf-8") as f:
        with codecs.open(os.path.join(output_dirname, filename), "wb", "utf-8") as f:
            pretty = BeautifulSoup(response.body).prettify()
            f.write(template.render(body=pretty.decode('utf8')))

        for img in response.xpath("//img/@src").extract():
            if img:
                # PATCH: il y a probleme de chemin relatif sur les pages (parfois dans un sous repertoire 'xhtml') et
                # les images (dans le cas de 'xhtml' par exemple, le path relatif contient '../' pour remonter a une
                # racine (du projet du livre).
                # TODO: Stabiliser (refactorer) les chemins relatifs (pour les images)
                img = img.replace("../", "")
                img_url = self.host + '/library/view/' + title + '/' + bookid + '/' + img
                self.logger.info("img_url: {}".format(img_url))

                yield scrapy.Request(img_url,
                                     callback=partial(self.parse_content_img, img, output_dir=self.output_dir))

    def parse_toc(self, response):
        # TODO: fix a potential exploit
        # Grosse erreur de code ! Une grosse possibilite d'injection de code a ce niveau (faille de securite).
        # En plus ca ne fonctionne pas tout le temps ! :-/
        # toc = eval(response.body)
        # https://stackoverflow.com/questions/28843876/nulls-instead-of-nones-in-json-data-with-python
        toc = json.loads(response.body)

        self.book_name = toc['title_safe']
        cover_path, = re.match(r'<img src="(.*?)" alt.+', toc["thumbnail_tag"]).groups()
        yield scrapy.Request(self.host + cover_path,
                             callback=partial(self.parse_cover_img, "cover-image", output_dir=self.output_dir))
        for item in toc["items"]:
            yield scrapy.Request(self.host + item["url"],
                                 callback=partial(self.parse_page_json, toc["title_safe"], toc["book_id"]))

        template = Template(file("{}/OEBPS/content.opf".format(self.output_dir)).read())
        with codecs.open("{}/OEBPS/content.opf".format(self.output_dir), "wb", "utf-8") as f:
            f.write(template.render(info=toc))

        template = Template(file("{}/OEBPS/toc.ncx".format(self.output_dir)).read())
        with codecs.open("{}/OEBPS/toc.ncx".format(self.output_dir), "wb", "utf-8") as f:
            f.write(template.render(info=toc))

    def closed(self, _):
        # https://docs.python.org/2/library/shutil.html
        archive = shutil.make_archive(base_name=self.book_name, format='zip', root_dir=self.output_dir)
        epub_filename = "{}_{}.epub".format(self.bookid, self.book_name)
        # https://docs.python.org/2/library/os.path.html
        shutil.move(archive, os.path.join(self.epub_output_dir, epub_filename))
        self.logger.info("EPUB generated: {}".format(epub_filename))

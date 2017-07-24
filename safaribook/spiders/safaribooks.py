import os
import re
import shutil
from functools import partial
import codecs

import scrapy
from jinja2 import Template
from BeautifulSoup import BeautifulSoup

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
        self.epub_output_dir = kwargs.get('output', './')

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

    @staticmethod
    def parse_content_img(img, response, output_dir):
        img_path = os.path.join("{}/OEBPS".format(output_dir), img)

        img_dir = os.path.dirname(img_path)
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)

        with open(img_path, "wb") as f:
            f.write(response.body)

    def parse_page_json(self, title, bookid, response):
        page_json = eval(response.body)
        yield scrapy.Request(page_json["content"],
                             callback=partial(self.parse_page, title, bookid, page_json["full_path"],
                                              output_dir=self.output_dir))

    def parse_page(self, title, bookid, path, response, output_dir):
        template = Template(PAGE_TEMPLATE)
        with codecs.open("{}/OEBPS/".format(output_dir) + path, "wb", "utf-8") as f:
            pretty = BeautifulSoup(response.body).prettify()
            f.write(template.render(body=pretty.decode('utf8')))

        for img in response.xpath("//img/@src").extract():
            if img:
                yield scrapy.Request(self.host + '/library/view/' + title + '/' + bookid + '/' + img,
                                     callback=partial(self.parse_content_img, img, output_dir=self.output_dir))

    def parse_toc(self, response):
        toc = eval(response.body)
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
        # https://docs.python.org/2/library/os.path.html
        shutil.move(archive, os.path.join(self.epub_output_dir, self.book_name + '.epub'))

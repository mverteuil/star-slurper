#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
from datetime import datetime
import logging
import os
import re
import shutil
import subprocess
from urlparse import urlparse

from bs4 import BeautifulSoup
from feedreader import parser
from genshi.template import TemplateLoader
import requests

from epub import Book
import settings


LOGGING_ENABLED = False
log = logging.getLogger(__name__)

XHTML_KWARGS = {'method': 'xhtml',
                'doctype': 'xhtml11',
                'drop_xml_decl': False}

token_matcher = re.compile(r"/(\d+)--")


class DownloadedArticle(object):
    """ Contains article metadata and file path """
    templates = None
    category = None
    token = None
    article_data = None
    path = None

    def __init__(self, category, token, article_soup, templates=None):
        self.category = category
        if templates:
            self.templates = templates
        else:
            self.templates = self.category.templates
        self.token = token
        self.article_data = article_soup
        self.path = os.path.join(
            self.category.folder_path,
            "%s_%s.html" % (self.category.name, self.token)
        )

    def remove_tags(self):
        """ Removes unwanted tags from the document """
        def unwanted_tags():
            """ Generates a list of unwanted tags """
            # Remove CSS links
            for link in self.article_data.findAll('link'):
                yield link
            # Remove "Back to article" anchor
            has_back_to = lambda x: "Back to" in x.string if x else False
            for anchor in self.article_data.findAll("a", text=has_back_to):
                yield anchor
        for tag in unwanted_tags():
            tag.decompose()
        for tag in self.article_data.findAll(True):
            del(tag['style'])

    def set_content_type(self):
        """ Sets the correct encoding for the document """
        meta_tag = self.article_data.new_tag("meta",
                                             content="text/html;charset=utf-8")
        meta_tag["http-equiv"] = "Content-Type"
        self.article_data.find("head").append(meta_tag)
        return self.article_data

    def set_styles(self):
        """ Sets the correct stylesheet for the document """
        link_tag = self.article_data.new_tag("link",
                                             rel="stylesheet",
                                             href=settings.CSS_PATH,
                                             type="text/css")
        self.article_data.find("head").append(link_tag)
        return self.article_data

    def clean_data(self):
        self.remove_tags()
        self.set_content_type()
        self.set_styles()

    def download_image(self, image_url):
        local_name = urlparse(image_url).path.replace("/", "_")[1:]
        local_path = os.path.join(self.category.folder_path, local_name)
        if not os.path.exists(local_path):
            log.info("Downloading article image: %s", local_path)
            with open(local_path, "wb") as local_image:
                response = requests.get(image_url)
                local_image.write(response.content)
        else:
            log.debug("%s already exists. Skipping.", local_path)
        return local_name, local_path

    def save_images(self):
        """
        Saves images for a downloaded article and replaces references in the
        article data with local copies.
        """
        def add_base_if_missing(url):
            if not url.startswith('http'):
                return settings.BASE_URL + url
            return url
        for image_tag in self.article_data.find_all('img'):
            image_url = add_base_if_missing(image_tag.get('src'))
            local_name, local_path = self.download_image(image_url)
            image_tag['src'] = local_name
            self.category.edition.images.add(local_path)
        return self.article_data

    def get_title(self):
        """ Finds the title in the article data """
        return self.article_data.findAll('h1')[0].text

    def get_author(self):
        """ Finds the author in the article data """
        author = self.article_data.find('div', 'td-author')
        if author:
            return author.find('strong').text
        return ""

    def get_date(self):
        """ Finds the date in the article data """
        return parse_date(self.article_data)

    def get_masthead(self):
        """ Finds the masthead in the article data """
        masthead = self.article_data.find('img', {'alt': 'Logo'})
        if masthead:
            return masthead['src']
        return ""

    def get_image(self):
        """ Finds the image for this article if one exists """
        image = self.article_data.find('img', 'topsImage')
        if image:
            return image['src']

    def get_image_title(self):
        """ Finds the image title for this article if one exists """
        heading = self.article_data.find('h3', 'topsTitle')
        if heading:
            return heading.find('span').text
        return ""

    def get_image_credit(self):
        """ Finds the image credit for this article if one exists """
        credit = self.article_data.find('span', 'topsCredit')
        if credit:
            return credit.text
        return ""

    def get_image_caption(self):
        """ Finds the image caption for this article if one exists """
        caption = self.article_data.find('span', 'topsCaption')
        if caption:
            return caption.text
        return ""

    def get_paragraphs(self):
        """ Finds the article body paragraphs """
        return [node.text for node in self.article_data.findAll('p')]

    def save(self):
        """
        Saves this article to its category folder with its images, cleaning up
        unwanted tags and instrumenting with star-slurper styles
        """
        self.clean_data()
        self.save_images()
        template = self.templates.load(settings.ARTICLE_HTML_TEMPLATE)
        stream = template.generate(article=self)
        article_data = stream.render(**XHTML_KWARGS)
        article_data = BeautifulSoup(article_data)
        with open(self.path, "w+") as local_copy:
            local_copy.write(article_data.prettify().encode('utf-8'))
        return self

    def __str__(self):
        return self.get_title()


class UpstreamArticle(object):
    """ Refers to the article before its data has been downloaded """
    token = None
    category = None
    article_data = None

    def __init__(self, category, token):
        self.category = category
        self.token = token

    def download_url(self):
        return settings.PRINT_TEMPLATE % self.token

    def download(self):
        """
        Downloads the article and returns the result as a DownloadedArticle
        """
        log.info("Downloading %s", self.download_url())
        response = requests.get(self.download_url())
        self.article_data = BeautifulSoup(response.content)
        return DownloadedArticle(self.category, self.token, self.article_data)


class Category(object):
    """ News category. Categories contain a set of Articles """
    name = None
    toc_path = None
    folder_path = None
    feed_url = None
    templates = None
    articles = None

    def __init__(self, edition, name, templates=None):
        self.feed_url = settings.RSS_TEMPLATE % name
        self.edition = edition
        if templates:
            self.templates = templates
        else:
            self.templates = self.edition.templates
        self.folder_path = self.edition.path
        self.name = name = name.replace("/", "_")
        self.toc_path = os.path.join(self.folder_path, "%s.html" % name)
        self.articles = []

    def __str__(self):
        return self.name

    def check_feed_for_new_articles(self):
        """
        Retrieves the list of new articles from the RSS feed
        """
        log.info("Fetching %s article list...", self)
        feed = parser.from_url(self.feed_url)
        upstream_articles = [
            UpstreamArticle(self, parse_token(article.id))
            for article in feed.entries
        ]
        return upstream_articles

    def save_table_of_contents(self):
        """ Generates HTML table of contents from current state """
        with open(self.toc_path, "w+") as toc_file:
            template = self.templates.load(settings.CATEGORY_HTML_TEMPLATE)
            stream = template.generate(date=self.edition.date, category=self)
            toc_data = stream.render(**XHTML_KWARGS)
            toc_file.write(toc_data)
        return BeautifulSoup(toc_data)

    def save(self):
        """
        Retrieves a news category and its articles, generates a
        table of contents and returns the modified category instance.
        """
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        for upstream_article in self.check_feed_for_new_articles():
            article = upstream_article.download()
            self.articles.append(article.save())
        if self.templates:
            self.save_table_of_contents()
        return self

    def iter_articles(self):
        for article in sorted(self.articles):
            yield (article.path, "%s.html" % article.token, article, )


class Edition(object):
    """ Newspaper edition. Editions contain a set of categories """
    date = datetime.today().strftime("%Y-%m-%d")
    categories = None
    images = None
    templates = None
    path = None
    toc_path = None

    def __init__(self, templates, base_path, rss_categories):
        """ Generates the current edition from a list of RSS categories """
        self.path = os.path.join(base_path, "%s/" % self.date)
        self.toc_path = os.path.join(self.path, "index.html")
        self.templates = templates
        self.categories = [Category(self, c) for c in rss_categories]
        self.images = set()

    def save(self):
        """ Saves this edition to disk """
        # Copy from template folder
        try:
            os.makedirs(self.path)
        except OSError, err:
            log.debug(err)
            log.info("Path already exists, updating downloaded files...")
        for category in self.categories:
            category.save()
        self.save_table_of_contents()

    def save_table_of_contents(self):
        """ Generates HTML table of contents from current state """
        with open(self.toc_path, "w+") as toc_file:
            template = self.templates.load(settings.INDEX_HTML_TEMPLATE)
            stream = template.generate(date=self.date,
                                       newspaper=self)
            toc_data = stream.render(**XHTML_KWARGS)
            toc_file.write(toc_data)
        return BeautifulSoup(toc_data)

    @property
    def title(self):
        return "The Toronto Star - %s" % self.date

    def iter_categories(self):
        for category in sorted(self.categories):
            yield (category.toc_path, "%s.html" % category.name, category, )

    def iter_images(self):
        for image in sorted(self.images):
            yield (image, os.path.split(image)[1], )


def with_logging(logged):
    """
    Enables logging on the instrumented function

    logged -- The function which requires logging enabled
    """
    def enable_logging():
        if settings.DEBUG:
            log.setLevel(settings.LOG_LEVEL)
            log_file = logging.FileHandler(settings.LOG_FILE)
            log_file.setFormatter(logging.Formatter(settings.LOG_FILE_FORMAT))
            log_stdout = logging.StreamHandler()
            log_stdout.setFormatter(
                logging.Formatter(settings.LOG_STDOUT_FORMAT)
            )
            for handler in (log_file, log_stdout):
                handler.setLevel(settings.LOG_LEVEL)
                log.addHandler(handler)

    def wrapper(*args, **kwargs):
        global LOGGING_ENABLED
        if not LOGGING_ENABLED:
            LOGGING_ENABLED = True
            enable_logging()
        return logged(*args, **kwargs)
    wrapper.__name__ = logged.__name__
    wrapper.__doc__ = logged.__doc__
    return wrapper


def parse_date(article_soup):
    """
    Gets the article date from article data and returns it as a datetime.date

    article_soup -- bs4 article data
    """
    title_and_date = article_soup.findAll("div",
                                          {'class': 'tdArticleMainInside'})[0]
    date_string = title_and_date.find("span").text
    date_string = " ".join(date_string.split(" ")[2:])
    article_date = datetime.strptime(date_string, "%A %B %d, %Y")
    return article_date.date()


def parse_token(url):
    """
    Converts article URL from the default browser view to the unique ID
    that represents it
    """
    url = str(url)  # Sometimes this isn't a string proper and blows up
    match = token_matcher.search(url)
    token = match.groups()[0]
    return token


def convert_html_to_epub(input_file, output_file):
    """
    Converts the saved edition at the specified path to a compiled
    epub document
    """
    call_list = [settings.EBOOK_CONVERT, input_file, output_file]
    call_list += settings.CONVERSION_OPTIONS.split(" ")
    log.info(call_list)
    subprocess.call(call_list)


@with_logging
def main():
    templates = TemplateLoader("templates")
    newspaper = Edition(templates,
                        settings.OUTPUT_FOLDER,
                        settings.RSS_CATEGORIES)
    newspaper.save()
    book = Book()
    book.title = newspaper.title
    book.add_creator("Star-Slurper")
    book.add_meta_info('date', '2010', event='publication')
    book.enable_title_page()
    book.set_table_of_contents(newspaper.toc_path)
    book.add_css(r'templates/main.css', 'main.css')
    for c_index, c_data in enumerate(newspaper.iter_categories()):
        i, o, category = c_data
        print "%s %s %s" % c_data
        manifest_item = book.add_html(i, o, None)
        book.add_spine_item(manifest_item)
        book.add_toc_node(
            manifest_item.dest_path,
            category.name,
            1,
        )
        for a_index, a_data in enumerate(category.iter_articles()):
            i, o, article = a_data
            print "%s %s %s" % a_data
            manifest_item = book.add_html(i, o, None)
            book.add_spine_item(manifest_item)
            book.add_toc_node(
                manifest_item.dest_path,
                article.get_title(),
                2,
            )
    [book.add_image(i, o) for (i, o) in newspaper.iter_images()]
    root_dir = os.path.join("/", "tmp", newspaper.date)
    if os.path.exists(root_dir):
        shutil.rmtree(root_dir)
    book.raw_publish(root_dir)
    target_file = os.path.join(settings.OUTPUT_FOLDER,
                               "%s.epub" % newspaper.date)
    Book.create_epub(root_dir, target_file)
    log.info("Done!")

if __name__ == "__main__":
    main()

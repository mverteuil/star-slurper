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
import requests

import settings

LOGGING_ENABLED = False
log = logging.getLogger(__name__)


token_matcher = re.compile(r"/(\d+)--")


class DownloadedArticle(object):
    """ Contains article metadata and file path """
    category = None
    token = None
    article_data = None
    path = None

    def __init__(self, category, token, article_soup):
        self.category = category
        self.token = token
        self.article_data = article_soup
        self.path = os.path.join(
            self.category.folder_path,
            "%s.html" % self.token
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
            local_name = urlparse(image_url).path.replace("/", "_")[1:]
            image_tag['src'] = local_name
            local_path = os.path.join(self.category.folder_path, local_name)
            if not os.path.exists(local_path):
                log.info("Downloading article image: %s", local_path)
                with open(local_path, "wb") as local_image:
                    response = requests.get(image_url)
                    local_image.write(response.content)
            else:
                log.debug("%s already exists. Skipping.", local_path)
        return self.article_data

    def get_title(self):
        """ Finds the title in the article data """
        return self.article_data.findAll('h1')[0].text

    def get_date(self):
        """ Finds the date in the article data """
        return parse_date(self.article_data)

    def save(self):
        """
        Saves this article to its category folder with its images, cleaning up
        unwanted tags and instrumenting with star-slurper styles
        """
        self.clean_data()
        self.save_images()
        with open(self.path, "w+") as local_copy:
            local_copy.write(self.article_data.prettify().encode('utf-8'))
        return self

    def __str__(self):
        return self.title


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
    articles = []

    def __init__(self, edition, name):
        self.edition = edition
        self.name = name
        self.toc_path = os.path.join(self.edition.path, "%s.html" % name)
        self.folder_path = os.path.join(self.edition.path, name)
        self.feed_url = settings.RSS_TEMPLATE % name

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
        self.save_table_of_contents()
        return self

    def save_table_of_contents(self):
        """ Generates HTML table of contents from current state """
        metadata = {
            'date': datetime.today().strftime("%Y-%m-%d"),
            'category': self.name
        }
        template = os.path.join(
            settings.TEMPLATE_FOLDER,
            settings.CATEGORY_HTML_TEMPLATE
        )
        toc = BeautifulSoup(open(template, "r+"))
        for tag in toc.findAll(['title', 'h1', 'h2']):
            tag.string = (tag.string % metadata)
        for article in self.articles:
            listitem_tag = toc.new_tag("li")
            anchor_tag = toc.new_tag("a", href=article.path)
            anchor_tag.string = article.get_title()
            listitem_tag.append(anchor_tag)
            toc.find('ul').append(listitem_tag)
        with open(self.toc_path, "w+") as toc_file:
            toc_file.write(toc.prettify().encode('utf-8'))
        return toc


class Edition(object):
    """ Newspaper edition. Editions contain a set of categories """
    date = datetime.today().strftime("%Y-%m-%d")
    categories = []
    path = None
    toc_path = None

    def __init__(self, rss_categories, base_path):
        """ Generates the current edition from a list of RSS categories """
        self.path = os.path.join(base_path, "%s/" % self.date)
        self.toc_path = os.path.join(self.path, settings.INDEX_HTML_TEMPLATE)
        self.categories = [Category(self, c) for c in rss_categories]

    def save(self):
        """ Saves this edition to disk """
        # Copy from template folder
        try:
            shutil.copytree(
                settings.TEMPLATE_FOLDER,
                self.path,
                ignore=lambda x, y: ["_cat_toc.html", "index.html"],
            )
        except OSError, err:
            log.debug(err)
            log.info("Path already exists, updating downloaded files...")
        for category in self.categories:
            category.save()
        self.save_table_of_contents()

    def save_table_of_contents(self):
        """ Generates HTML table of contents from current state """
        metadata = {
            'date': self.date
        }
        template = os.path.join(
            settings.TEMPLATE_FOLDER,
            settings.INDEX_HTML_TEMPLATE,
        )
        toc = BeautifulSoup(open(template, "r+"))
        for tag in toc.findAll(['title', 'h1']):
            tag.string = (tag.string % metadata)
        for category in self.categories:
            listitem_tag = toc.new_tag("li")
            anchor_tag = toc.new_tag("a", href=category.toc_path)
            anchor_tag.string = category.name
            listitem_tag.append(anchor_tag)
            toc.find('ul').append(listitem_tag)
        with open(self.toc_path, "w+") as toc_file:
            toc_file.write(toc.prettify().encode('utf-8'))
        return toc


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
    call_list = [ settings.EBOOK_CONVERT, input_file, output_file ]
    call_list += settings.CONVERSION_OPTIONS.split(" ")
    log.info(call_list)
    subprocess.call(call_list)


@with_logging
def main():
    newspaper = Edition(settings.RSS_CATEGORIES, settings.OUTPUT_FOLDER)
    newspaper.save()
    input_file = os.path.join(newspaper.path, settings.INDEX_HTML_TEMPLATE)
    output_file = os.path.join(
        settings.OUTPUT_FOLDER,
        "%s.%s" % (newspaper.date, settings.OUTPUT_FORMAT)
    )
    convert_html_to_epub(input_file, output_file)
    log.info("Done!")

if __name__ == "__main__":
    main()

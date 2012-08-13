#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
from datetime import datetime
import logging
import os
import re
import shutil
import tempfile
from urlparse import urlparse

from bs4 import BeautifulSoup
from feedreader import parser
import requests

import settings

LOGGING_ENABLED = False
log = logging.getLogger(__name__)


token_matcher = re.compile(r"/(\d+)--")


class Article(object):
    """ Contains article metadata and file path """
    title = None
    date = None
    path = None

    def __init__(self, article_soup, path):
        """
        Parses the soup for article metadata and sets the path

        article_soup -- bs4 article data
        path -- path to the downloaded html
        """
        self.title = article_soup.findAll('h1')[0].text
        self.date = parse_date(article_soup)
        self.path = path


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


def find_article_images(article_data):
    """
    Finds images in a BeautifulSoup object and returns a list of tags

    article_data -- The BeautifulSoup of a print-view article
    """
    return article_data.findAll("img")


def save_images(category, article_data):
    """
    Saves images for a local copy of a downloaded article and replaces
    references in the article data with local copies.

    category -- The category path for the article
    article_data -- The BeautifulSoup of a print-view article
    """
    def add_base_if_missing(url):
        if not url.startswith('http'):
            return settings.BASE_URL + url
        return url
    for image_tag in find_article_images(article_data):
        image_url = add_base_if_missing(image_tag.get('src'))
        local_name = urlparse(image_url).path.replace("/", "_")[1:]
        image_tag['src'] = local_name
        local_path = os.path.join(category, local_name)
        if not os.path.exists(local_path):
            log.info("Downloading %s to %s", image_url, local_path)
            with open(local_path, "wb") as local_image:
                response = requests.get(image_url)
                local_image.write(response.content)
        else:
            log.debug("%s already exists. Skipping.", local_path)
    return article_data


def get_articles(category):
    """
    Gets articles for all categories and return them for processing

    category -- Category ID
    """
    log.info("Fetching %s article list...", category)
    feed_url = settings.RSS_TEMPLATE % category
    feed = parser.from_url(feed_url)
    articles = [parse_token(article.id) for article in feed.entries]
    log.info("(%d articles)", len(articles))
    return articles


def remove_tags(article_soup):
    """
    Removes unwanted tags from the document

    article_soup -- bs4 article data
    """
    def unwanted_tags():
        """ Generates a list of unwanted tags """
        # Remove CSS links
        for link in article_soup.findAll('link'):
            yield link
        # Remove "Back to article" anchor
        has_back_to = lambda x: "Back to" in x.string if x else False
        for anchor in article_soup.findAll("a", text=has_back_to):
            yield anchor
    for tag in unwanted_tags():
        tag.decompose()
    for tag in article_soup.findAll(True):
        del(tag['style'])
    return article_soup


def set_content_type(article_soup):
    """
    Sets the correct encoding for the document

    article_soup -- bs4 article data
    """
    meta_tag = article_soup.new_tag("meta", content="text/html;charset=utf-8")
    meta_tag["http-equiv"] = "Content-Type"
    article_soup.find("head").append(meta_tag)
    return article_soup


def save_article(category, article):
    """
    Saves an article's print view data to a category folder

    category -- The category folder for this article
    article -- The article token
    """
    article_url = settings.PRINT_TEMPLATE % article
    log.info("Downloading %s", article_url)
    response = requests.get(article_url)
    article_data = BeautifulSoup(response.content)
    article_path = os.path.join(category, "%s.html" % article)
    with open(article_path, "wb") as local_copy:
        article_data = save_images(category, article_data)
        remove_tags(article_data)
        set_content_type(article_data)
        local_copy.write(article_data.prettify().encode('utf-8'))
    return Article(article_data, article_path)


def save_category(work_folder, category):
    """
    Retrieves a news category and saves the contents to disk

    work_folder -- The working directory where category data should be
                   saved during processing
    category -- The news category to retrieve
    """
    cat_folder = os.path.join(work_folder, category)
    os.makedirs(cat_folder)
    for article in get_articles(category):
        article = save_article(cat_folder, article)
        log.info("%s (%s)", article.title, article.path)
    return cat_folder


@with_logging
def main():
    if os.path.exists(settings.OUTPUT_FOLDER):
        shutil.rmtree(settings.OUTPUT_FOLDER)
    work_folder = tempfile.mkdtemp()
    for category in settings.RSS_CATEGORIES:
        cat_folder = save_category(work_folder, category)
        shutil.move(cat_folder, settings.OUTPUT_FOLDER)
    shutil.rmtree(work_folder)
    log.info("Done!")

if __name__ == "__main__":
    main()

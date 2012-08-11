#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
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
            log_stdout.setFormatter(logging.Formatter(settings.LOG_STDOUT_FORMAT))
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


def parse_token(url):
    """
    Converts article URL from the default browser view to the unique ID
    that represents it
    """
    url = str(url) # Sometimes this isn't a string proper and blows up
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
    Saves images for a local copy of a downloaded article and replaces references
    in the article data with local copies.

    category -- The category path for the article
    article_data -- The BeautifulSoup of a print-view article
    """
    def add_base_if_missing(url):
        if not url.startswith('http'):
            return settings.BASE_URL + url
        return url
    for image_tag in find_article_images(article_data):
        image_url = add_base_if_missing(image_tag.get('src'))
        local_name = urlparse(image_url).path.replace("/","_")[1:]
        image_tag['src'] = local_name
        local_path = os.path.join(category, local_name)
        if not os.path.exists(local_path):
            log.info("Downloading %s to %s", image_url, local_path)
            with open(local_path, "wb") as local_image:
                response = requests.get(image_url)
                local_image.write(response.content)
        else:
            log.debug("%s already exists. Skipping.",  local_path)
    return article_data


def get_articles():
    """ Gets articles for all categories and return them for processing """
    log.info("Fetching article list...")
    for category in settings.RSS_CATEGORIES:
        feed_url = settings.RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        articles = [parse_token(article.id) for article in feed.entries]
        log.info("%s (%d articles)", category, len(articles))
        yield (category, articles)


def remove_tags(article_soup):
    """
    Removes unwanted tags from the document

    article_soup -- bs4 article data
    """
    for link in article_soup.findAll('link'):
        link.decompose()
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
    with open(os.path.join(category, "%s.html" % article), "wb") as local_copy:
        article_data = save_images(category, article_data)
        remove_tags(article_data)
        local_copy.write(article_data.prettify().encode('utf-8'))


@with_logging
def main():
    if os.path.exists(settings.OUTPUT_FOLDER):
        shutil.rmtree(settings.OUTPUT_FOLDER)
    work_folder = tempfile.mkdtemp()
    for category, articles in get_articles():
        cat_folder = os.path.join(work_folder, category)
        os.makedirs(cat_folder)
        for article in articles:
            save_article(cat_folder, article)
        shutil.move(cat_folder, settings.OUTPUT_FOLDER)
    shutil.rmtree(work_folder)
    log.info("Done!")

if __name__ == "__main__":
    main()

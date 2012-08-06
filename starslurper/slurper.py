#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
import os
import re
import shutil
import tempfile

from feedreader import parser

import requests

import settings


image_url_matcher = re.compile(r"<img [^>]*src=\"([^\"]+)\"[^>]*>")
token_matcher = re.compile(r"/(\d+)--")

def parse_token(url):
    """
    Converts article URL from the default browser view to the unique ID
    that represents it
    """
    url = str(url) # Sometimes this isn't a string proper and blows up
    match = token_matcher.search(url)
    token = match.groups()[0]
    return token


def parse_img_url(html):
    """
    Removes the part of the img tag that's not necessary and returns the url
    
    html -- html snippet containing an img tag
    """
    html = str(html)
    match = image_url_matcher.search(html)
    img_url = match.groups()[0]
    return img_url


def get_articles():
    """ Gets articles for all categories and return them for processing """
    for category in settings.RSS_CATEGORIES:
        feed_url = settings.RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        articles = [parse_token(article.id) for article in feed.entries]
        yield (category, articles)


def find_article_images(article_data):
    """
    Finds images for a local copy of a downloaded article and retuns a list
    of their urls.

    article_data -- The local downloaded HTML data of a print-view article
    """
    imglines = [parse_img_url(line) for line in article_data.split("\r") if "<img" in line]
    for line in imglines:
        print imglines


def save_article(category, article):
    """
    Saves an article's print view data to a category folder

    category -- The category folder for this article
    article -- The article token
    """
    article_url = settings.PRINT_TEMPLATE % article
    print "Downloading %s" % article_url
    response = requests.get(article_url)
    article_data = response.content
    with open(os.path.join(category, "%s.html" % article), "wb") as local_copy:
        local_copy.write(article_data)
        find_article_images(article_data)


def main():
    work_folder = tempfile.mkdtemp()
    for category, articles in get_articles():
        cat_folder = os.path.join(work_folder, category)
        os.makedirs(cat_folder)
        for article in articles:
            save_article(cat_folder, article)
        shutil.move(cat_folder, settings.OUTPUT_FOLDER)
    shutil.rmtree(work_folder)
    print "Done!"

if __name__ == "__main__":
    main()

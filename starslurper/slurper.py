#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
import os
import re
import tempfile

from feedreader import parser

import requests

import settings


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


def get_articles():
    """ Get articles for all categories and return them for processing """
    for category in settings.RSS_CATEGORIES:
        feed_url = settings.RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        articles = [parse_token(article.id) for article in feed.entries]
        yield (category, articles)


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


def main():
    target_folder = tempfile.mkdtemp()
    for category, articles in get_articles():
        cat_folder = os.path.join(target_folder, category)
        os.makedirs(cat_folder)
        for article in articles:
            save_article(cat_folder, article)
    print "Done!"

if __name__ == "__main__":
    main()

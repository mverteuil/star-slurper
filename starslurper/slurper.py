#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
import re

from feedreader import parser

import requests

import settings


token_matcher = re.compile(r"/(\d+)--")

def convert_to_print_view(url):
    """ Converts article URL from the default browser view to the minimal 
    print version """
    url = str(url) # Sometimes this isn't a string proper and blows up
    match = token_matcher.search(url)
    token = match.groups()[0]
    return settings.PRINT_TEMPLATE % token


def get_articles():
    """ Get articles for all categories and return them for processing """
    for category in settings.RSS_CATEGORIES:
        feed_url = settings.RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        articles = [convert_to_print_view(article.id) for article in feed.entries]
        yield (category, articles)


def main():
    for category, articles in get_articles():
        print category
        for article in articles:
            print article


if __name__ == "__main__":
    main()

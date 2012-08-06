#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
from feedreader import parser


RSS_TEMPLATE = "http://www.thestar.com/rss?category=/%s"
RSS_CATEGORIES = [
    "news",
    "travel",
    "business",
    "opinion",
    "news/sciencetech",
    "sports",
    "entertainment",
]


def get_articles():
    """ Get articles for all categories and print them to the console """
    for category in RSS_CATEGORIES:
        feed_url = RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        print "%s: %s" % ( str(category).upper(), feed.title )
        for entry in feed.entries:
            print entry.id


def main():
    get_articles()


if __name__ == "__main__":
    main()

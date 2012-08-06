#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
from feedreader import parser

RSS_FEED = "http://www.thestar.com/rss?category=%2fnews"


def main():
    response = parser.from_url(RSS_FEED)
    print response.title
    print response.link
    print response.published

if __name__ == "__main__":
    main()

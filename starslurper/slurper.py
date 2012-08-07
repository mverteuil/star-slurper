#!/usr/bin/env python
"""
Toronto Star News Grabber and Formatter
"""
import os
import re
import shutil
import tempfile
from urlparse import urlparse

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


def find_article_images(article_data):
    """
    Finds images for a local copy of a downloaded article and retuns a list
    of their urls.

    article_data -- The local downloaded HTML data of a print-view article
    """
    parsed = [parse_img_url(line) for line in article_data.split("\r") if "<img" in line]
    for url in parsed:
        if not url.startswith("http"):
            url = settings.BASE_URL + url
        yield url


def save_images(category, article_data):
    """
    Saves images for a local copy of a downloaded article and replaces references
    in the article data with local copies.

    category -- The category path for the article
    article_data -- The local downloaded HTML data of a print-view article
    """
    def replace_all(text, dic):
        for i, j in dic.iteritems():
            text = text.replace(i, j)
        return text
    replacements = dict()
    for image_url in find_article_images(article_data):
        local_name = urlparse(image_url).path.replace("/","_")[1:]
        local_path = os.path.join(category, local_name)
        if not os.path.exists(local_path):
            print "Downloading %s to %s" % (image_url, local_path)
            with open(local_path, "wb") as local_image:
                response = requests.get(image_url)
                local_image.write(response.content)
        else:
            print "%s already exists. Skipping." % local_path
        replacements[image_url] = os.path.split(local_path)[1]
    return replace_all(article_data, replacements)


def get_articles():
    """ Gets articles for all categories and return them for processing """
    print "Fetching article list..."
    for category in settings.RSS_CATEGORIES:
        feed_url = settings.RSS_TEMPLATE % category
        feed = parser.from_url(feed_url)
        articles = [parse_token(article.id) for article in feed.entries]
        print "%s (%d articles)" % ( category, len(articles) )
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
    article_data = response.content.decode('utf-8')
    with open(os.path.join(category, "%s.html" % article), "wb") as local_copy:
        updated_article_data = save_images(category, article_data)
        local_copy.write(updated_article_data.encode('utf-8'))


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

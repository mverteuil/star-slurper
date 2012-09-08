from datetime import date
import json
import unittest
import os
import shutil
import tempfile

import bs4
import feedreader
from genshi.template import TemplateLoader
import globalsub
import mock
import requests

from starslurper import settings
from starslurper import slurper
from tests.util import read_sample


FULL_IMAGE_URL = read_sample('sample_long.url')
SHORT_IMAGE_URL = read_sample('sample_short.url')
TOKEN_SAMPLE = "1239413"
ENTRY_SAMPLE = json.loads(read_sample('sample_entries.json'))
ARTICLE_URL_SAMPLE = ENTRY_SAMPLE[0]
ARTICLE_SAMPLE = read_sample('sample_article.html')
CATEGORY_TOC_SAMPLE = read_sample('sample_cat_toc.html')


def with_work_folder(wrapped):
    """
    Decorates a test by providing a temporary work folder on its instance
    """
    def wrapper(self):
        self.work_folder = tempfile.mkdtemp()
        wrapped(self)
        shutil.rmtree(self.work_folder)
        self.work_folder = None
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    return wrapper


class TestSlurper(unittest.TestCase):
    """
    Tests the slurper, making sure all of its core functions
    perform as expected
    """
    def setUp(self):
        super(TestSlurper, self).setUp()
        self.temp_folder = tempfile.mkdtemp()
        self.soup = bs4.BeautifulSoup(ARTICLE_SAMPLE)

    def tearDown(self):
        super(TestSlurper, self).tearDown()
        globalsub.restore(feedreader.parser)
        globalsub.restore(requests.get)
        if hasattr(self, 'work_folder') and self.work_folder:
            shutil.rmtree(self.work_folder)
            self.work_folder = None

    def test_parse_token(self):
        """ Token (unique ID) is found in a URL """
        token = slurper.parse_token(ARTICLE_URL_SAMPLE)
        assert token == TOKEN_SAMPLE

    @with_work_folder
    def test_save_category(self):
        """ Saves a category and its articles given an ID """
        assert self.work_folder
        edition = slurper.Edition(None, self.work_folder, [])
        category = slurper.Category(edition, "derp")
        mock_check_feed = mock.Mock(name="check_feed")
        mock_check_feed.return_value = [
            slurper.UpstreamArticle(category, "derp")
        ]
        category.check_feed_for_new_articles = mock_check_feed
        mock_get = mock.Mock(name="requests_get")
        mock_get.return_value = mock.Mock()
        mock_get.return_value.content = ARTICLE_SAMPLE
        globalsub.subs(requests.get, mock_get)
        category.save()

    @with_work_folder
    def test_get_articles(self):
        """
        Gets addresses for articles from RSS feed and converts
        to print view URL
        """
        class FakeRSSItem:
            """ Simulates an RSS20Item """
            def __init__(self, id):
                self.id = id
        mock_feed = mock.Mock(name="feed")
        mock_feed.entries = [FakeRSSItem(url) for url in ENTRY_SAMPLE]
        mock_parser = mock.Mock(name="parser")
        mock_parser.from_url.return_value = mock_feed
        globalsub.subs(feedreader.parser, mock_parser)
        edition = slurper.Edition(None, self.work_folder, [])
        category = slurper.Category(edition, "derp")
        articles = category.check_feed_for_new_articles()
        assert len(articles) == len(ENTRY_SAMPLE)

    @with_work_folder
    def test_save_article(self):
        """ Saves article according to category """
        assert self.work_folder
        mock_get = mock.Mock(name="requests_get")
        mock_get.return_value = mock.Mock()
        mock_get.return_value.content = ARTICLE_SAMPLE.decode('latin-1')
        mock_save_images = mock.Mock(name="save_images")
        mock_save_images.return_value = self.soup
        globalsub.subs(requests.get, mock_get)
        edition = slurper.Edition(None, self.work_folder, [])
        category = slurper.Category(edition, "derp")
        category.folder_path = self.work_folder
        article = slurper.DownloadedArticle(category, "derp", self.soup)
        article.save_images = mock_save_images
        article.save()
        assert article.get_title() == self.soup.findAll('h1')[0].text
        assert article.get_date() == slurper.parse_date(self.soup)
        saved_data = open(article.path, "r+").read()
        assert saved_data
        assert mock_save_images.call_count == 1

    def test_parse_date(self):
        """ Finds the date of an article and return it as python Date obj """
        article_date = slurper.parse_date(self.soup)
        assert article_date == date(year=2012, month=8, day=10)

    def test_remove_tags(self):
        """ Removes unwanted tags from the article """
        mock_category = mock.Mock()
        mock_category.folder_path = "/tmp/"
        article = slurper.DownloadedArticle(mock_category, "derp", self.soup)
        article.remove_tags()
        assert len(article.article_data.findAll('link')) == 0
        assert len(self.soup.findAll('link')) == 0
        is_not_none = lambda x: x is not None
        assert len(self.soup.findAll(attrs={'style': is_not_none})) == 0
        has_back_to_article = lambda x: "Back to" in x.string
        assert len(self.soup.findAll(text=has_back_to_article)) == 0

    def test_set_content_type(self):
        """ Sets the correct encoding for the article data """
        mock_category = mock.Mock()
        mock_category.folder_path = "/tmp/"
        article = slurper.DownloadedArticle(mock_category, "derp", self.soup)
        article.set_content_type()
        meta_tag = self.soup.find('meta')
        assert meta_tag
        assert meta_tag.get('http-equiv')
        assert "utf-8" in meta_tag.get('content')

    def test_set_styles(self):
        """ Sets the correct encoding for the article data """
        mock_category = mock.Mock()
        mock_category.folder_path = "/tmp/"
        article = slurper.DownloadedArticle(mock_category, "derp", self.soup)
        article.remove_tags()
        article.set_styles()
        link_tag = self.soup.find('link')
        assert link_tag
        assert link_tag.get('href') == settings.CSS_PATH
        assert "text/css" in link_tag.get('type')

    @with_work_folder
    def test_save_images(self):
        """
        Saves the images for an article and switches tags to use new relative
        paths
        """
        assert self.work_folder
        mock_category = mock.Mock()
        mock_category.folder_path = self.work_folder
        article = slurper.DownloadedArticle(mock_category, "derp", self.soup)
        result = article.save_images()
        assert result
        assert "http://i.thestar.com" not in str(result)
        sources = [img['src'] for img in result.findAll('img')]
        assert "images_72_fc_57efb6d944ac8f167b01c5be4b26.jpg" in sources

    @with_work_folder
    def test_save_table_of_contents(self):
        """ Generates a TOC document from the template """
        templates = TemplateLoader("templates")
        edition = slurper.Edition(templates, self.work_folder, [])
        category = slurper.Category(edition, "derp")
        article = slurper.DownloadedArticle(category, "derp", self.soup)
        category.articles = [article]
        edition.categories.append(category)
        os.makedirs(os.path.dirname(edition.toc_path))
        toc = edition.save_table_of_contents()
        assert "derp" in toc.findAll("li")[0].text
        assert date.today().isoformat() in toc.findAll("title")[0].text
        assert date.today().isoformat() in toc.findAll("h1")[0].text
        assert len(toc.findAll("li")) == 2

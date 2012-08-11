import json
import os
import unittest
import shutil
import tempfile

import bs4
import feedreader
import globalsub
import mock
import requests

from starslurper import settings
from starslurper import slurper
from tests.util import read_sample


FULL_IMAGE_URL = '''<li class="tdLast" data-assetuid="1116788"><a href="http://www.moneyville.ca/" target="_blank" title="Moneyville Logo"><img src="http://i.thestar.com/images/6d/5a/00f26e67488cbfbd837ed5b4d752.jpg" /></a></li>'''
SHORT_IMAGE_URL = '''<li class="tdLast" data-assetuid="1116788"><a href="http://www.derp.ca/" target="_blank" title="Derp"><img src="/content/images/derp.gif" /></a></li>'''
TOKEN_SAMPLE = "1239413"
ENTRY_SAMPLE = json.loads(read_sample('sample_entries.json'))
ARTICLE_URL_SAMPLE = ENTRY_SAMPLE[0]
ARTICLE_SAMPLE = read_sample('sample_article.html')


def with_work_folder(wrapped):
    """ 
    Decorates a test by providing a temporary work folder on its instance
    """
    def wrapper(self):
        errors = None
        self.work_folder = tempfile.mkdtemp()
        wrapped(self)
        shutil.rmtree(self.work_folder)
        self.work_folder = None
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    return wrapper


class TestSlurper(unittest.TestCase):
    """ Tests the slurper, making sure all of its core functions perform as expected """
    def setUp(self):
        super(TestSlurper, self).setUp()
        self.temp_folder = tempfile.mkdtemp()
        self.soup = bs4.BeautifulSoup(ARTICLE_SAMPLE)

    def tearDown(self):
        super(TestSlurper, self).tearDown()
        globalsub.restore(feedreader.parser)
        globalsub.restore(requests.get)
        globalsub.restore(slurper.get_articles)
        globalsub.restore(slurper.save_article)
        globalsub.restore(slurper.save_images)
        if hasattr(self, 'work_folder') and self.work_folder:
            shutil.rmtree(self.work_folder)
            self.work_folder = None

    def test_parse_token(self):
        """ Token (unique ID) is found in a URL """
        token = slurper.parse_token(ARTICLE_URL_SAMPLE)
        assert token == TOKEN_SAMPLE

    def test_get_articles(self):
        """ Gets addresses for articles from RSS feed and converts to print view URL """
        class FakeRSSItem:
            """ Simulates an RSS20Item """
            def __init__(self, id):
                self.id = id
        mock_feed = mock.Mock(name="feed")
        mock_feed.entries = [FakeRSSItem(url) for url in ENTRY_SAMPLE]
        mock_parser = mock.Mock(name="parser")
        mock_parser.from_url.return_value = mock_feed
        globalsub.subs(feedreader.parser, mock_parser)
        categories = list(slurper.get_articles())
        category, articles = categories[0]
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
        globalsub.subs(slurper.save_images, mock_save_images)
        slurper.save_article(self.work_folder, TOKEN_SAMPLE)
        files = os.listdir(self.work_folder)
        for filename in files:
            if TOKEN_SAMPLE in filename:
                saved_data = open(os.path.join(self.work_folder, filename), "r+").read()
        assert saved_data

    @with_work_folder
    def test_save_images(self):
        """ 
        Saves the images for an article and switches tags to use new relative
        paths
        """
        assert self.work_folder
        result = slurper.save_images(self.work_folder, self.soup)
        # Run it again and make sure it doesn't redownload
        self.setUp()
        slurper.save_images(self.work_folder, self.soup)
        assert result
        assert "http://i.thestar.com" not in str(result)
        assert "images_72_fc_57efb6d944ac8f167b01c5be4b26.jpg" in [img['src'] for img in result.findAll('img')]

    def test_main_happy_path(self):
        """
        Runs through when everything behaves as it should
        """
        mock_get_articles = mock.Mock(name="get_articles")
        mock_get_articles.return_value = [('news',[ARTICLE_URL_SAMPLE],)]
        globalsub.subs(slurper.get_articles, mock_get_articles)
        mock_save_article =  mock.Mock(name="save_article")
        mock_save_article.return_value = None
        globalsub.subs(slurper.save_article, mock_save_article)
        slurper.main()

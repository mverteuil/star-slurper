from datetime import date
import json
import unittest
import shutil
import tempfile

import bs4
import feedreader
import globalsub
import mock
import requests

from starslurper import slurper
from tests.util import read_sample


FULL_IMAGE_URL = read_sample('sample_long.url')
SHORT_IMAGE_URL = read_sample('sample_short.url')
TOKEN_SAMPLE = "1239413"
ENTRY_SAMPLE = json.loads(read_sample('sample_entries.json'))
ARTICLE_URL_SAMPLE = ENTRY_SAMPLE[0]
ARTICLE_SAMPLE = read_sample('sample_article.html')


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

    @with_work_folder
    def test_save_category(self):
        """ Saves a category and its articles given an ID """
        assert self.work_folder
        mock_get_articles = mock.Mock(name="get_articles")
        mock_get_articles.return_value = [ARTICLE_URL_SAMPLE]
        globalsub.subs(slurper.get_articles, mock_get_articles)
        mock_save_article = mock.Mock(name="save_article")
        mock_save_article.return_value = slurper.Article(self.soup, None)
        globalsub.subs(slurper.save_article, mock_save_article)
        cat_folder = slurper.save_category(self.work_folder, "derp")
        assert cat_folder
        assert mock_get_articles.call_count == 1
        assert mock_save_article.call_count == 1

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
        articles = slurper.get_articles("derp")
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
        article = slurper.save_article(self.work_folder, TOKEN_SAMPLE)
        assert article.title == self.soup.findAll('h1')[0].text
        assert article.date == slurper.parse_date(self.soup)
        saved_data = open(article.path, "r+").read()
        assert saved_data

    def test_parse_date(self):
        """ Finds the date of an article and return it as python Date obj """
        article_date = slurper.parse_date(self.soup)
        assert article_date == date(year=2012, month=8, day=10)

    def test_remove_tags(self):
        """ Removes unwanted tags from the article """
        result = slurper.remove_tags(self.soup)
        assert len(result.findAll('link')) == 0
        assert len(self.soup.findAll('link')) == 0
        is_not_none = lambda x: x is not None
        assert len(self.soup.findAll(attrs={'style': is_not_none})) == 0
        has_back_to_article = lambda x: "Back to" in x.string
        assert len(self.soup.findAll(text=has_back_to_article)) == 0

    def test_set_content_type(self):
        """ Sets the correct encoding for the article data """
        result = slurper.set_content_type(self.soup)
        meta_tag = result.find('meta')
        assert meta_tag
        assert meta_tag.get('http-equiv')
        assert "utf-8" in meta_tag.get('content')

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
        sources = [img['src'] for img in result.findAll('img')]
        assert "images_72_fc_57efb6d944ac8f167b01c5be4b26.jpg" in sources

    def test_new_category_toc_from_template(self):
        """ Generates a category TOC document from the template """
        template = slurper.new_category_toc_from_template("derp")
        assert "derp" in template.findAll("title")[0].text
        assert "derp" in template.findAll("h2")[0].text
        assert date.today().isoformat() in template.findAll("title")[0].text
        assert date.today().isoformat() in template.findAll("h1")[0].text

    def test_append_article_to_category_toc(self):
        """ Appends an article to category table of contents """
        pass

    def test_main_happy_path(self):
        """ Runs through when everything behaves as it should """
        mock_get_articles = mock.Mock(name="get_articles")
        mock_get_articles.return_value = [('news', [ARTICLE_URL_SAMPLE],)]
        globalsub.subs(slurper.get_articles, mock_get_articles)
        mock_save_article = mock.Mock(name="save_article")
        mock_save_article.return_value = slurper.Article(self.soup, None)
        globalsub.subs(slurper.save_article, mock_save_article)
        slurper.main()

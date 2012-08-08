import unittest

from starslurper import slurper

EXAMPLE_ARTICLE_URL = "http://www.thestar.com/business/article/1238545--roger-communications-and-competition-bureau-in-court-over-misleading-cellphone-ads"
HTML_FRAGMENT = '''<li class="tdLast" data-assetuid="1116788"><a href="http://www.moneyville.ca/" target="_blank" title="Moneyville Logo"><img src="http://i.thestar.com/images/6d/5a/00f26e67488cbfbd837ed5b4d752.jpg" /></a></li>'''


class TestSlurper(unittest.TestCase):
    def test_parse_token(self):
        """ Tests that the token (unique ID) is found in a URL """
        token = slurper.parse_token(EXAMPLE_ARTICLE_URL)
        assert token == "1238545"

    def test_parse_img_url(self):
        """ Tests that the URL of an image is found in an HTML fragment """
        img_url = slurper.parse_img_url(HTML_FRAGMENT)
        assert img_url == "http://i.thestar.com/images/6d/5a/00f26e67488cbfbd837ed5b4d752.jpg"

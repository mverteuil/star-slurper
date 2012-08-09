import unittest

import globalsub
import mock

from starslurper import settings
from starslurper import slurper


EXAMPLE_ARTICLE_URL = "http://www.thestar.com/business/article/1238545--roger-communications-and-competition-bureau-in-court-over-misleading-cellphone-ads"
FULL_IMAGE_URL = '''<li class="tdLast" data-assetuid="1116788"><a href="http://www.moneyville.ca/" target="_blank" title="Moneyville Logo"><img src="http://i.thestar.com/images/6d/5a/00f26e67488cbfbd837ed5b4d752.jpg" /></a></li>'''
SHORT_IMAGE_URL = '''<li class="tdLast" data-assetuid="1116788"><a href="http://www.derp.ca/" target="_blank" title="Derp"><img src="/content/images/derp.gif" /></a></li>'''
ENTRY_SAMPLE = ["http://www.thestar.com/news/gta/article/1239413--toronto-mayor-rob-ford-remains-hospitalized-thursday-afternoon",
 "http://www.thestar.com/news/world/article/1239408--philippines-flooding-sun-shines-after-relentless-rain-revealing-deluge-of-debris-in-manila",
 "http://www.thestar.com/news/canada/politics/article/1239311--ontario-government-secures-third-deal-with-provincial-education-union",
 "http://www.thestar.com/news/world/article/1239397--assailants-leave-14-corpses-on-major-mexican-highway",
 "http://www.thestar.com/news/world/article/1239389--u-s-starts-landmark-cleanup-of-agent-orange-nearly-40-years-after-vietnam-war-s-end",
 "http://www.thestar.com/news/canada/article/1239381--canada-immigration-minister-jason-kenney-to-announce-ukraine-vote-observers",
 "http://www.thestar.com/news/world/article/1239364--canadian-electro-pop-star-peaches-makes-video-for-pussy-riot",
 "http://www.thestar.com/news/world/article/1239264--cairo-hit-by-massive-power-outage",
 "http://www.thestar.com/news/world/article/1239377--cambodian-leader-makes-longest-speech-5-hours-20-minutes",
 "http://www.thestar.com/news/world/article/1239357--uproar-over-greek-politician-s-move-to-hire-daughter",
 "http://www.thestar.com/news/world/article/1239353--clashes-rage-in-rebel-bastions-of-aleppo-iran-summons-meeting-of-syrian-allies",
 "http://www.thestar.com/news/world/article/1239266--underground-sect-some-of-whom-had-never-seen-daylight-found-in-russia",
 "http://www.thestar.com/news/canada/article/1239308--tony-accurso-arrested-on-allegations-of-tax-evasion",
 "http://www.thestar.com/news/world/article/1239290--mars-crater-where-rover-touched-down-looks-like-earth-scientists-say",
 "http://www.thestar.com/news/world/article/1239285--belarus-arrests-journalists-for-teddy-bear-photo-shoot",
 "http://www.thestar.com/news/world/article/1239246--murder-trial-of-disgraced-chinese-politician-s-wife-lasts-just-four-hours",
 "http://www.thestar.com/business/sciencetech/article/1239249--samsung-says-it-s-not-considering-buying-rim",
 "http://www.thestar.com/news/gta/crime/article/1239209--lawyers-across-north-america-targeted-in-email-scam-partly-run-out-of-greater-toronto-police-say",
 "http://www.thestar.com/news/gta/article/1239019--hume-setting-the-stage-for-violence-at-the-eaton-centre",
 "http://www.thestar.com/news/world/royalfamily/article/1239237--prince-harry-is-odd-man-out-in-this-cycle-of-romance"
]

class Item:
    def __init__(self, id):
        self.id = id

class TestSlurper(unittest.TestCase):
    def tearDown(self):
        super(TestSlurper, self).tearDown()
        import feedreader
        globalsub.restore(feedreader.parser)

    def test_parse_token(self):
        """ Token (unique ID) is found in a URL """
        token = slurper.parse_token(EXAMPLE_ARTICLE_URL)
        assert token == "1238545"

    def test_parse_img_url(self):
        """ URL of an image is found in an HTML fragment """
        img_url = slurper.parse_img_url(FULL_IMAGE_URL)
        assert img_url == "http://i.thestar.com/images/6d/5a/00f26e67488cbfbd837ed5b4d752.jpg"

    def test_prepends_on_short_urls(self):
        """ Prepends server/protocol to relative URLs """
        images = list(slurper.find_article_images(SHORT_IMAGE_URL))[0]
        assert images
        assert "http://www.thestar.com" in images

    def test_get_articles(self):
        """ Gets addresses for articles from RSS feed and converts to print view URL """
        import feedreader
        mock_feed = mock.Mock(name="feed")
        mock_feed.entries = [Item(url) for url in ENTRY_SAMPLE]
        mock_parser = mock.Mock(name="parser")
        mock_parser.from_url.return_value = mock_feed
        globalsub.subs(feedreader.parser, mock_parser)
        categories = list(slurper.get_articles())
        category, articles = categories[0]
        assert len(articles) == len(ENTRY_SAMPLE)

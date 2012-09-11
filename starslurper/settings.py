""" Main Configuration """
import json
import logging
import os
from ConfigParser import ConfigParser

PROJECT_FOLDER = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(PROJECT_FOLDER, "starslurper.conf")
config = ConfigParser()
config.read(CONFIG_PATH)

EBOOK_CONVERT = config.get('calibre', 'ebook_convert')
OUTPUT_FORMAT = config.get('calibre', 'output_format')
CONVERSION_OPTIONS = config.get('calibre', 'options')

# Template url used for print-view of article for easier parsing
# than the default
PRINT_TEMPLATE = config.get('source', 'print_template')
# Template url used for pulling the RSS feed for top level news categories
RSS_TEMPLATE = config.get('source', 'category_template')
# JSON list of category names to handle
RSS_CATEGORIES = json.loads(config.get('source', 'categories'))
BASE_URL = config.get('source', 'base_url')

INDEX_HTML_TEMPLATE = "index.html"
CATEGORY_HTML_TEMPLATE = "category-toc.html"
ARTICLE_HTML_TEMPLATE = "article.html"
# Used for CSS links in HTML
CSS_PATH = os.path.join("main.css")
TEMPLATE_FOLDER = os.path.join(PROJECT_FOLDER, "templates")
OUTPUT_FOLDER = config.get('target', 'output_folder')
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

DEBUG = config.getboolean('debug', 'enabled')
LOG_FILE = config.get('debug', 'log_file')
LOG_LEVEL = getattr(logging, config.get('debug', 'log_level'), "DEBUG")
LOG_FILE_FORMAT = "[%(levelname)s:%(pathname)s:%(lineno)s] %(message)s"
LOG_STDOUT_FORMAT = "%(message)s"

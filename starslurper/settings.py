""" Main Configuration """
import json
import os
from ConfigParser import ConfigParser

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "starslurper.conf")
config = ConfigParser()
config.read(CONFIG_PATH)

# Template url used for print-view of article for easier parsing than the default
PRINT_TEMPLATE = config.get('source', 'print_template')
# Template url used for pulling the RSS feed for top level news categories
RSS_TEMPLATE = config.get('source', 'category_template')
# JSON list of category names to handle
RSS_CATEGORIES = json.loads(config.get('source', 'categories'))
BASE_URL = config.get('source', 'base_url')

OUTPUT_FOLDER = config.get('target', 'output_folder')
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

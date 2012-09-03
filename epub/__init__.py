#!/usr/bin/env python
"""
                   __
.-----.-----.--.--.  |--.
|  -__|  _  |  |  |  _  |
|_____|   __|_____|_____|
      |__|  B U I L D E R

Original developed by Bin Tan (http://code.google.com/p/python-epub-builder/)
With modifications by Matthew de Verteuil
    * Pythonic names (vs Java-eque original)
    * Removed some helper functions that I didn't deem necessary
    * Renamed several methods to better represent their actions
"""
import itertools
import mimetypes
import os
import shutil
import subprocess
import uuid
from zipfile import ZipFile
from zipfile import ZIP_STORED
from zipfile import ZIP_DEFLATED

from genshi.template import TemplateLoader
from genshi.template import NewTextTemplate
from genshi.template import MarkupTemplate
from lxml import etree


# Guide Item Types
G_COVER = "cover"
G_TITLE = "title-page"
G_TOC = "toc"

# Open Container Format: The OCF specifies how to organize these files
# in the ZIP
OCF_METADATA = "container.xml"

# Navigation Control XML: Hierarchical table of contents for the EPUB file
NCX_METADATA = "toc.ncx"

# Open Packaging Format: Houses the EPUB book's metadata, file manifest,
# and linear reading order
OPF_METADATA = "content.opf"

# Text Document: ASCII that contains the string application/epub+zip
# It must also be uncompressed, unencrypted, and the first file
# in the ZIP archive
MIMETYPE_METADATA = "mimetype"

# Contains the Book data(XHTML, CSS, etc) and NCX, OPF metadata files.
OEBPS = "OEBPS"

# Contains the OCF metadata file
META_INF = "META-INF"

# Mimetype must be in the first position by requirement of EPUB specification
METADATA_FILES = [
    # Folder, File name, File type, Encoding, Template loader
    ('.', MIMETYPE_METADATA, 'text', "latin-1", NewTextTemplate),
    (META_INF, OCF_METADATA, 'xml', "utf-8", MarkupTemplate),
    (OEBPS, OPF_METADATA, 'xml', "utf-8", MarkupTemplate),
    (OEBPS, NCX_METADATA, 'xml', "utf-8", MarkupTemplate),
]

# A list of acceptable values for opf:role attribute of dc:creator
# http://idpf.org/epub/20/spec/OPF_2.0.1_draft.htm#Section2.2.6
CREATOR_ROLES = (
    ("adp", "Adapter"),
    ("ann", "Annotator"),
    ("arr", "Arranger"),
    ("art", "Artist"),
    ("asn", "Associated name"),
    ("aut", "Author"),
    ("aqt", "Author in quotations or text extracts"),
    ("aft", "Author of afterword, colophon, etc."),
    ("aui", "Author of introduction, etc."),
    ("ant", "Bibliographic antecedent"),
    ("bkp", "Book producer"),
    ("clb", "Collaborator"),
    ("cmm", "Commentator"),
    ("dsr", "Designer"),
    ("edt", "Editor"),
    ("ill", "Illustrator"),
    ("lyr", "Lyricist"),
    ("mdc", "Metadata contact"),
    ("mus", "Musician"),
    ("nrt", "Narrator"),
    ("oth", "Other"),
    ("pht", "Photographer"),
    ("prt", "Printer"),
    ("red", "Redactor"),
    ("rev", "Reviewer"),
    ("spn", "Sponsor"),
    ("ths", "Thesis advisor"),
    ("trc", "Transcriber"),
    ("trl", "Translator")
)


class TableOfContentsNode(object):
    play_order = 0
    title = None
    href = None
    children = None
    depth = 0

    def __init__(self):
        self.play_order = 0
        self.title = ""
        self.href = ""
        self.children = []
        self.depth = 0

    def update_play_order(self):
        next_play_order = [0]
        self.__update_play_order(next_play_order)

    def __update_play_order(self, next_play_order):
        self.play_order = next_play_order[0]
        next_play_order[0] = self.play_order + 1
        for child in self.children:
            child.__update_play_order(next_play_order)


class ManifestItem(object):
    def __init__(self):
        self.key = ''
        self.src_path = ''
        self.dest_path = ''
        self.mimetype = ''
        self.html = ''


class Book(object):
    """ Produces epub archives from model contents """
    loader = TemplateLoader("templates")
    lang = "en-US"
    uuid = None
    title = ""
    creators = []

    meta_info = []
    images = {}
    html_docs = {}
    css_docs = {}

    cover_image = None
    cover_page = None
    toc_page = None

    spine = []
    guide = {}

    def __init__(self):
        self.uuid = uuid.uuid1()
        self.rootDir = ""

        self.tocMapRoot = TableOfContentsNode()
        self.last_node_at_depth = {0: self.tocMapRoot}

    def add_creator(self, name, role='aut'):
        """
        Adds creator metadata

        Creator metadata is written into content.opf and is utilized by
        ereader devices for sorting and display.
        """
        assert role in [code for code, desc in CREATOR_ROLES]
        self.creators.append((name, role))

    def add_meta_info(self, name, value, **attributes):
        """
        Adds metadata information

        Metadata information is written into content.opf and is utilized
        by ereader devices for sorting and display.
        """
        self.meta_info.append((name, value, attributes))

    def render_meta_tags(self):
        """
        Generates Dublin Core metadata tags

        Metadata information is written into content.opf and is utilized
        by ereader devices for sorting and display.
        """
        for name, value, attribute in self.meta_info:
            tag_open = '<dc:%s' % name
            if attribute:
                for attr_name, attr_value in attribute.iteritems():
                    tag_open += ' opf:%s="%s"' % (attr_name, attr_value)
            tag_open += '>'
            tag_close = '</dc:%s>' % name
            yield (tag_open, value, tag_close)

    def get_all_items(self):
        return sorted(
            itertools.chain(
                self.images.values(),
                self.html_docs.values(),
                self.css_docs.values()
            ), key=lambda x: x.key
        )

    def add_image(self, src_path, dest_path):
        item = ManifestItem()
        item.key = 'image_%d' % (len(self.images) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.mimetype = mimetypes.guess_type(dest_path)[0]
        assert item.dest_path not in self.images
        self.images[dest_path] = item
        return item

    def add_html(self, src_path, dest_path, html):
        item = ManifestItem()
        item.key = 'html_%d' % (len(self.html_docs) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.html = html
        item.mimetype = 'application/xhtml+xml'
        assert item.dest_path not in self.html_docs
        self.html_docs[item.dest_path] = item
        return item

    def add_css(self, src_path, dest_path):
        item = ManifestItem()
        item.key = 'css_%d' % (len(self.css_docs) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.mimetype = 'text/css'
        assert item.dest_path not in self.css_docs
        self.css_docs[item.dest_path] = item
        return item

    def __render_title_page(self):
        assert self.cover_page
        if self.cover_page.html:
            return
        tmpl = self.loader.load('title-page.html')
        stream = tmpl.generate(book=self)
        self.cover_page.html = stream.render('xhtml',
                                             doctype='xhtml11',
                                             drop_xml_decl=False)

    def enable_title_page(self, html=''):
        assert not self.cover_page
        self.cover_page = self.add_html('', 'title-page.html', html)
        self.add_spine_item(self.cover_page, True, -200)
        self.add_guide_reference(G_TITLE, "Title Page", "title-page.html")

    def __render_table_of_contents(self):
        assert self.toc_page
        tmpl = self.loader.load('toc.html')
        stream = tmpl.generate(book=self)
        self.toc_page.html = stream.render('xhtml',
                                           doctype='xhtml11',
                                           drop_xml_decl=False)

    def enable_table_of_contents(self):
        assert not self.toc_page
        self.toc_page = self.add_html('', 'toc.html', '')
        self.add_spine_item(self.toc_page, False, -100)
        self.add_guide_reference(G_TOC, "Table of Contents", "toc.html")

    def get_spine(self):
        return sorted(self.spine)

    def add_spine_item(self, item, linear=True, order=None):
        assert item.dest_path in self.html_docs
        if order is None:
            order = (max(order for order, _, _ in self.spine)
                     if self.spine else 0) + 1
        self.spine.append((order, item, linear))

    def get_guide(self):
        return sorted(self.guide.values(), key=lambda x: x[2])

    def add_guide_reference(self, reftype, title, href):
        self.guide[reftype] = (href, title, reftype)

    def get_toc_map_height(self):
        return max(self.last_node_at_depth.keys())

    def add_toc_node(self, href, title, depth=None, parent=None):
        node = TableOfContentsNode()
        node.href = href
        node.title = title
        if parent is None:
            if depth is None:
                parent = self.tocMapRoot
            else:
                parent = self.last_node_at_depth[depth - 1]
        parent.children.append(node)
        node.depth = parent.depth + 1
        self.last_node_at_depth[node.depth] = node
        return node

    def __write_metadata_files(self):
        self.tocMapRoot.update_play_order()
        for folder, file_name, file_type, encode, loader in METADATA_FILES:
            path = os.path.join(self.rootDir, folder, file_name)
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, 'w') as target_file:
                template = self.loader.load(file_name, cls=loader)
                stream = template.generate(book=self)
                target_file.write(stream.render(file_type, encoding=encode))

    def __write_book_data(self):
        for item in self.get_all_items():
            print item.key, item.dest_path
            path = os.path.join(self.rootDir, 'OEBPS', item.dest_path)
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            if item.html:
                with open(path, 'w') as fout:
                    fout.write(item.html)
            else:
                shutil.copyfile(item.src_path, path)

    @staticmethod
    def __get_manifest_items(contentOPFPath):
        tree = etree.parse(contentOPFPath)
        return tree.xpath(
            "//opf:manifest/opf:item/@href",
            namespaces={'opf': 'http://www.idpf.org/2007/opf'}
        )

    @staticmethod
    def create_epub(root_dir, output_path):
        saved_cwd = os.getcwd()
        os.chdir(root_dir)
        with ZipFile(output_path, 'w') as epub_archive:
            for folder, file_name, _, _, _ in METADATA_FILES:
                path = os.path.join(folder, file_name)
                epub_archive.write(path, compress_type=ZIP_STORED)
            opf_path = os.path.join(OEBPS, OPF_METADATA)
            manifest_items = Book.__get_manifest_items(opf_path)
            for file_name in manifest_items:
                path = os.path.join(OEBPS, file_name)
                epub_archive.write(path, compress_type=ZIP_DEFLATED)
            epub_archive.close()
        os.chdir(saved_cwd)

    @staticmethod
    def validate_epub(checkerPath, epubPath):
        subprocess.call(['java', '-jar', checkerPath, epubPath], shell=True)

    def raw_publish(self, rootDir):
        if self.cover_page:
            self.__render_title_page()
        if self.toc_page:
            self.__render_table_of_contents()
        self.rootDir = rootDir
        self.__write_book_data()
        self.__write_metadata_files()

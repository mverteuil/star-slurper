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
import zipfile
from genshi.template import TemplateLoader
from lxml import etree


# Guide Item Types
G_COVER = "cover"
G_TITLE = "title-page"
G_TOC = "toc"


class TableOfContentsNode(object):
    play_order = 0
    title = None
    href = None
    children = None
    depth = 0

    def __init__(self):
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
        self.srcPath = ''
        self.destPath = ''
        self.mimeType = ''
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
        self.creators.append((name, role))

    def add_meta_info(self, name, value, **attributes):
        self.meta_info.append((name, value, attributes))

    def render_meta_tags(self):
        l = []
        for name, value, attribute in self.meta_info:
            tag_open = '<dc:%s' % name
            if attribute:
                for attr_name, attr_value in attribute.iteritems():
                    tag_open += ' opf:%s="%s"' % (attr_name, attr_value)
            tag_open += '>'
            tag_close = '</dc:%s>' % name
            l.append((tag_open, value, tag_close))
        return l

    def get_all_items(self):
        return sorted(
            itertools.chain(
                self.images.values(),
                self.html_docs.values(),
                self.css_docs.values()
            ), key=lambda x: x.key
        )

    def add_image(self, srcPath, destPath):
        item = ManifestItem()
        item.key = 'image_%d' % (len(self.images) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.mimeType = mimetypes.guess_type(destPath)[0]
        assert item.destPath not in self.images
        self.images[destPath] = item
        return item

    def add_html(self, srcPath, destPath, html):
        item = ManifestItem()
        item.key = 'html_%d' % (len(self.html_docs) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.html = html
        item.mimeType = 'application/xhtml+xml'
        assert item.destPath not in self.html_docs
        self.html_docs[item.destPath] = item
        return item

    def add_css(self, srcPath, destPath):
        item = ManifestItem()
        item.key = 'css_%d' % (len(self.css_docs) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.mimeType = 'text/css'
        assert item.destPath not in self.css_docs
        self.css_docs[item.destPath] = item
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
        self.set_guide_item(G_TITLE, "Title Page", "title-page.html")

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
        self.set_guide_item(G_TOC, "Table of Contents", "toc.html")

    def get_spine(self):
        return sorted(self.spine)

    def add_spine_item(self, item, linear=True, order=None):
        assert item.destPath in self.html_docs
        if order is None:
            order = (max(order for order, _, _ in self.spine)
                     if self.spine else 0) + 1
        self.spine.append((order, item, linear))

    def get_guide(self):
        return sorted(self.guide.values(), key=lambda x: x[2])

    def set_guide_item(self, i_type, title, href):
        self.guide[i_type] = (href, title, i_type)

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

    def __write_folders(self):
        try:
            os.makedirs(os.path.join(self.rootDir, 'META-INF'))
        except OSError:
            pass
        try:
            os.makedirs(os.path.join(self.rootDir, 'OEBPS'))
        except OSError:
            pass

    def __write_container_xml(self):
        path = os.path.join(self.rootDir, 'META-INF', 'container.xml')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('container.xml')
            stream = tmpl.generate()
            fout.write(stream.render('xml'))

    def __write_toc_ncx(self):
        self.tocMapRoot.update_play_order()
        path = os.path.join(self.rootDir, 'OEBPS', 'toc.ncx')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('toc.ncx')
            stream = tmpl.generate(book=self)
            fout.write(stream.render('xml'))

    def __write_content_opf(self):
        path = os.path.join(self.rootDir, 'OEBPS', 'content.opf')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('content.opf')
            stream = tmpl.generate(book=self)
            fout.write(stream.render('xml'))

    def __write_book_data(self):
        for item in self.get_all_items():
            print item.key, item.destPath
            path = os.path.join(self.rootDir, 'OEBPS', item.destPath)
            if item.html:
                with open(path, 'w') as fout:
                    fout.write(item.html)
            else:
                shutil.copyfile(item.srcPath, path)

    def __write_mimetype(self):
        fout = open(os.path.join(self.rootDir, 'mimetype'), 'w')
        fout.write('application/epub+zip')
        fout.close()

    @staticmethod
    def __get_manifest_items(contentOPFPath):
        tree = etree.parse(contentOPFPath)
        return tree.xpath(
            "//opf:manifest/opf:item/@href",
            namespaces={'opf': 'http://www.idpf.org/2007/opf'}
        )

    @staticmethod
    def create_epub(rootDir, outputPath):
        fout = zipfile.ZipFile(outputPath, 'w')
        cwd = os.getcwd()
        os.chdir(rootDir)
        fout.write('mimetype', compress_type=zipfile.ZIP_STORED)
        fileList = []
        fileList.append(os.path.join('META-INF', 'container.xml'))
        fileList.append(os.path.join('OEBPS', 'content.opf'))
        content_opf = os.path.join('OEBPS', 'content.opf')
        manifest_items = Book.__get_manifest_items(content_opf)
        for itemPath in manifest_items:
            fileList.append(os.path.join('OEBPS', itemPath))
        for filePath in fileList:
            fout.write(filePath, compress_type=zipfile.ZIP_DEFLATED)
        fout.close()
        os.chdir(cwd)

    @staticmethod
    def validate_epub(checkerPath, epubPath):
        subprocess.call(['java', '-jar', checkerPath, epubPath], shell=True)

    def raw_publish(self, rootDir):
        if self.cover_page:
            self.__render_title_page()
        if self.toc_page:
            self.__render_table_of_contents()
        self.rootDir = rootDir
        self.__write_folders()
        self.__write_mimetype()
        self.__write_book_data()
        self.__write_container_xml()
        self.__write_content_opf()
        self.__write_toc_ncx()

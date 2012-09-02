#!/usr/bin/env python
"""
                   __
.-----.-----.--.--.  |--.
|  -__|  _  |  |  |  _  |
|_____|   __|_____|_____|
      |__|  B U I L D E R

Original developed by Bin Tan (http://code.google.com/p/python-epub-builder/)
With modifications by Matthew de Verteuil
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


class TocMapNode:

    def __init__(self):
        self.playOrder = 0
        self.title = ''
        self.href = ''
        self.children = []
        self.depth = 0

    def assignPlayOrder(self):
        nextPlayOrder = [0]
        self.__assignPlayOrder(nextPlayOrder)

    def __assignPlayOrder(self, nextPlayOrder):
        self.playOrder = nextPlayOrder[0]
        nextPlayOrder[0] = self.playOrder + 1
        for child in self.children:
            child.__assignPlayOrder(nextPlayOrder)


class EpubItem:

    def __init__(self):
        self.id = ''
        self.srcPath = ''
        self.destPath = ''
        self.mimeType = ''
        self.html = ''


class Book:
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

        self.tocMapRoot = TocMapNode()
        self.lastNodeAtDepth = {0: self.tocMapRoot}

    def add_creator(self, name, role='aut'):
        self.creators.append((name, role))

    def add_meta_info(self, name, value, **attributes):
        self.meta_info.append((name, value, attributes))

    def getMetaTags(self):
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
            ), key=lambda x: x.id
        )

    def add_image(self, srcPath, destPath):
        item = EpubItem()
        item.id = 'image_%d' % (len(self.images) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.mimeType = mimetypes.guess_type(destPath)[0]
        assert item.destPath not in self.images
        self.images[destPath] = item
        return item

    def add_html(self, srcPath, destPath, html):
        item = EpubItem()
        item.id = 'html_%d' % (len(self.html_docs) + 1)
        item.srcPath = srcPath
        item.destPath = destPath
        item.html = html
        item.mimeType = 'application/xhtml+xml'
        assert item.destPath not in self.html_docs
        self.html_docs[item.destPath] = item
        return item

    def add_css(self, srcPath, destPath):
        item = EpubItem()
        item.id = 'css_%d' % (len(self.css_docs) + 1)
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

    def getSpine(self):
        return sorted(self.spine)

    def add_spine_item(self, item, linear=True, order=None):
        assert item.destPath in self.html_docs
        if order is None:
            order = (max(order for order, _, _ in self.spine)
                     if self.spine else 0) + 1
        self.spine.append((order, item, linear))

    def getGuide(self):
        return sorted(self.guide.values(), key=lambda x: x[2])

    def set_guide_item(self, i_type, title, href):
        self.guide[i_type] = (href, title, i_type)

    def getTocMapRoot(self):
        return self.tocMapRoot

    def getTocMapHeight(self):
        return max(self.lastNodeAtDepth.keys())

    def addTocMapNode(self, href, title, depth=None, parent=None):
        node = TocMapNode()
        node.href = href
        node.title = title
        if parent is None:
            if depth is None:
                parent = self.tocMapRoot
            else:
                parent = self.lastNodeAtDepth[depth - 1]
        parent.children.append(node)
        node.depth = parent.depth + 1
        self.lastNodeAtDepth[node.depth] = node
        return node

    def makeDirs(self):
        try:
            os.makedirs(os.path.join(self.rootDir, 'META-INF'))
        except OSError:
            pass
        try:
            os.makedirs(os.path.join(self.rootDir, 'OEBPS'))
        except OSError:
            pass

    def __writeContainerXML(self):
        path = os.path.join(self.rootDir, 'META-INF', 'container.xml')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('container.xml')
            stream = tmpl.generate()
            fout.write(stream.render('xml'))

    def __writeTocNCX(self):
        self.tocMapRoot.assignPlayOrder()
        path = os.path.join(self.rootDir, 'OEBPS', 'toc.ncx')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('toc.ncx')
            stream = tmpl.generate(book=self)
            fout.write(stream.render('xml'))

    def __writeContentOPF(self):
        path = os.path.join(self.rootDir, 'OEBPS', 'content.opf')
        with open(path, 'w') as fout:
            tmpl = self.loader.load('content.opf')
            stream = tmpl.generate(book=self)
            fout.write(stream.render('xml'))

    def __writeItems(self):
        for item in self.get_all_items():
            print item.id, item.destPath
            path = os.path.join(self.rootDir, 'OEBPS', item.destPath)
            if item.html:
                with open(path, 'w') as fout:
                    fout.write(item.html)
            else:
                shutil.copyfile(item.srcPath, path)

    def __writeMimeType(self):
        fout = open(os.path.join(self.rootDir, 'mimetype'), 'w')
        fout.write('application/epub+zip')
        fout.close()

    @staticmethod
    def __listManifestItems(contentOPFPath):
        tree = etree.parse(contentOPFPath)
        return tree.xpath(
            "//opf:manifest/opf:item/@href",
            namespaces={'opf': 'http://www.idpf.org/2007/opf'}
        )

    @staticmethod
    def createArchive(rootDir, outputPath):
        fout = zipfile.ZipFile(outputPath, 'w')
        cwd = os.getcwd()
        os.chdir(rootDir)
        fout.write('mimetype', compress_type=zipfile.ZIP_STORED)
        fileList = []
        fileList.append(os.path.join('META-INF', 'container.xml'))
        fileList.append(os.path.join('OEBPS', 'content.opf'))
        content_opf = os.path.join('OEBPS', 'content.opf')
        manifest_items = Book.__listManifestItems(content_opf)
        for itemPath in manifest_items:
            fileList.append(os.path.join('OEBPS', itemPath))
        for filePath in fileList:
            fout.write(filePath, compress_type=zipfile.ZIP_DEFLATED)
        fout.close()
        os.chdir(cwd)

    @staticmethod
    def checkEpub(checkerPath, epubPath):
        subprocess.call(['java', '-jar', checkerPath, epubPath], shell=True)

    def createBook(self, rootDir):
        if self.cover_page:
            self.__render_title_page()
        if self.toc_page:
            self.__render_table_of_contents()
        self.rootDir = rootDir
        self.makeDirs()
        self.__writeMimeType()
        self.__writeItems()
        self.__writeContainerXML()
        self.__writeContentOPF()
        self.__writeTocNCX()

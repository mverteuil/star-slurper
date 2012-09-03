import os
import unittest
import shutil

from epub import Book
from tests.util import get_minimal_html


class TestBook(unittest.TestCase):
    def test_book(self):
        book = Book()
        book.title = 'Most Wanted Tips for Aspiring Young Pirates'
        book.add_creator('Monkey D Luffy')
        book.add_creator('Guybrush Threepwood')
        book.add_meta_info('contributor', 'Smalltalk80', role='bkp')
        book.add_meta_info('date', '2010', event='publication')

        book.enable_title_page()
        book.enable_table_of_contents()

        book.add_css(r'template/css/main.css', 'main.css')

        n1 = book.add_html('', '1.html', get_minimal_html('Chapter 1'))
        n11 = book.add_html('', '2.html', get_minimal_html('Section 1.1'))
        n111 = book.add_html('', '3.html', get_minimal_html('Section 1.1.1'))
        n12 = book.add_html('', '4.html', get_minimal_html('Section 1.2'))
        n2 = book.add_html('', '5.html', get_minimal_html('Chapter 2'))

        book.add_spine_item(n1)
        book.add_spine_item(n11)
        book.add_spine_item(n111)
        book.add_spine_item(n12)
        book.add_spine_item(n2)

        # You can use both forms to add TOC map
        #t1 = book.add_toc_node(n1.dest_path, '1')
        #t11 = book.add_toc_node(n11.dest_path, '1.1', parent = t1)
        #t111 = book.add_toc_node(n111.dest_path, '1.1.1', parent = t11)
        #t12 = book.add_toc_node(n12.dest_path, '1.2', parent = t1)
        #t2 = book.add_toc_node(n2.dest_path, '2')

        book.add_toc_node(n1.dest_path, '1')
        book.add_toc_node(n11.dest_path, '1.1', 2)
        book.add_toc_node(n111.dest_path, '1.1.1', 3)
        book.add_toc_node(n12.dest_path, '1.2', 2)
        book.add_toc_node(n2.dest_path, '2')

        rootDir = r'/tmp/epubtest/'
        if os.path.exists(rootDir):
            shutil.rmtree(rootDir)
        book.raw_publish(rootDir)
        Book.create_epub(rootDir, rootDir + '.epub')
        Book.validate_epub('../epubcheck-1.1.jar', rootDir + '.epub')

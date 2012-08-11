import os

from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # Import here because outside the eggs aren't loaded
        import pytest
        pytest.main(self.test_args)


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="star-slurper",
    version="dev",
    author="Matthew de Verteuil",
    author_email="onceuponajooks@gmail.com",
    description="A Toronto Star news grabber and reformatter",
    license="GNU",
    keywords="news",
    url="http://github.com/mverteuil/star-slurper",
    packages=['starslurper', 'tests'],
    long_description=read('README.md'),
    tests_require=['pytest'],
    cmdclass={'test': PyTest},
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        ("License :: OSI Approved :: ",
         "GNU General Public License v3 or later (GPLv3+)"),
        "Programming Language :: Python :: 2.7",
        "Topic :: Text Processing",
    ],
)

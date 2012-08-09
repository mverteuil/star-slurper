import os

def read_sample(fname):
    """ Reads sample data from a file and returns it """
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

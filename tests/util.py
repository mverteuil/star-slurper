import os


def read_sample(fname):
    """ Reads sample data from a file and returns it """
    return open(os.path.join(os.path.dirname(__file__), fname,), "r+").read()


def get_minimal_html(content):
    """ Gets sample HTML for book generation tests """
    sample = read_sample("sample_minihtml.html")
    return sample % (content, content)

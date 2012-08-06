import requests

RSS_FEED = "http://www.thestar.com/rss?category=%2fnews"


def main():
    response = requests.get(RSS_FEED)
    print response.content

if __name__ == "__main__":
    main()

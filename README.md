star-slurper
============

Calibre almost pulls the Toronto Star in a fashion I can read on my Kobo Touch, but not quite. I'm not going to pay $15 for someone else to do formatting work that I'm fairly sure I can write code to do for me instead. We'll see. We'll see.

Update:
So, it seems that the epub spec for xhtml 1.1 differs slightly from the spec for browsers. details:
http://idpf.org/epub/20/spec/OPS_2.0.1_draft.htm#Section2.2

Update:
The class paradigm I'm using seemed a bit cluttered as I was designing it yesterday, but after careful review and laying it out in terms of what each object has and what it is expected to do, I'm actually very happy with the pattern that emerged.
Following are my notes from this morning when trying to decipher the refactoring I did yesterday:

Newspaper has:
 - Categories
 - A date

Newspaper can:
 - Download categories
 - Generate a TOC for its categories
 - Be saved to disk

Category has:
 - Articles
 - A name
 - An RSS Feed
 - A folder

Category can:
 - Download UpstreamArticles and save them
 - Be saved to disk by newspaper
 - Generate a TOC for its articles

UpstreamArticle has:
 - A print view URL
 - A token
 - A category

UpstreamArticle can:
 - Be downloaded by category

DownloadedArticle has:
 - Images
 - Copy
 - A print view URL
 - A filename

DownloadedArticle can:
 - Download images
 - Be saved to disk by category
 - Remove unwanted elements
 - Add its own styles
 - Update its own image urls

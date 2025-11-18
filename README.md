
# Wiki-Scraper-n8n
It is used to scrape all html code from a wiki side and optionally send it to a webhook.

Export MediaWiki to HTML


The task is to export a MediaWiki to HTML.

There is the extension DumpHTML, but it is unmaintained: https://www.mediawiki.org/wiki/Extension%3aDumpHTML

This Python script supports the following features:

* links between the pages
* links to anchors
* links to non-existing pages
* directly embedded images
* thumbnails
* supports authentication for dumping a protected wiki
* export all (currently up to 500) pages, or export a single page

You need to use a bot password, to make the script work, see [[Special:BotPasswords]] / https://www.mediawiki.org/wiki/Manual:Bot_passwords

Install
=======

    git clone https://github.com/dominik70437/Wiki-Scraper-n8n
    cd Wiki-Scraper-n8n
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Usage


For all commands, you need to activate the virtual environment first:

    cd Wiki-Scraper-n8n
    source .venv/bin/activate

Please pass the url of the wiki

    python3 scraper.py --url https://mywiki.example.org

Optionally pass the page id of the page you want to download, eg. for debugging:

    python3 scraper.py --url https://mywiki.example.org --page 180

Optionally pass the name of a Bot and the Bot password (create a Bot at https://wiki.example.org/index.php?title=Spezial:BotPasswords):

    python3 scraper.py --url https://mywiki.example.org --user "myuser@botname" --password "botpwd" [pageid]

Optionally add --webhook-url="http-webhook-test" to send for each page an array with content and link as post.

example of usage:

 python3 scraper.py --url="https://your.wiki.com"   --username="Username@Botname"   --password="your-bot-password"   --webhook-url="Your-webhook" 
 --numberOfPages="max"



You can use `--help` to see all options.

Contribute


Feel free to file any issues, and Pull Requests are welcome as well!


import os
from urllib import parse
import requests
import json
import re
from pathlib import Path
import argparse
from bs4 import BeautifulSoup

description = """
Export MediaWiki pages to HTML or send to n8n webhook
Call like this:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org
   Optionally pass the page id of the page you want to download, eg. for debugging:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --page=180
   Optionally pass the page id of the category, all pages with that category will be exported:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --category=22
   Optionally pass the namespace id, only pages in that namespace will be exported:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --namespace=0
   Optionally pass the username and password:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --username="myusername@botname" --password=botsecret
   Optionally pass the directory to dump the export to (default: export):
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --outputDir=export
   Or send ALL pages at once to n8n webhook:
   ./exportMediaWiki2Html.py --url=https://mywiki.example.org --webhook-url="https://your.n8n.webhook.url"
"""
parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('-l','--url', help='The url of the wiki',required=True)
parser.add_argument('-u','--username', help='Your username and bot name, eg. "myuser@botname"',required=False)
parser.add_argument('-p','--password', help='Your bot password',required=False)
parser.add_argument('-c','--category', help='The category to export',required=False)
parser.add_argument('-g','--page', help='The page to export',required=False)
parser.add_argument('-s', '--namespace', help='The namespace to export', required=False)
parser.add_argument('-n', '--numberOfPages', help='The number of pages to export, or max', required=False, default=500)
parser.add_argument('-o', '--outputDir', help='The destination directory for the export (only for local export)', type=Path, required=False, default="export")
parser.add_argument('--shortUrl', help='Custom short url path for the wiki (only for local export)', required=False, default='wiki/')
parser.add_argument('--listPages', help='List available pages', required=False, default=False, action='store_true')
parser.add_argument('--dontOverwrite', help='Skip already downloaded files (only for local export)', required=False, default=False, action='store_true')
parser.add_argument('--webhook-url', help='n8n webhook URL to send HTML to', required=False) # <-- NEU: Webhook URL

try:
    parser.add_argument('--ssl', help='Enable SSL redirection', required=False, default=True, action=argparse.BooleanOptionalAction)
except AttributeError:
    # BooleanOptionalAction was introduced in Python 3.9
    parser.add_argument('--ssl', help='Enable SSL redirection', required=False, default=True)
args = parser.parse_args()

# Check if webhook mode is active
is_webhook_mode = args.webhook_url is not None

if args.numberOfPages != "max":
  try:
    int(args.numberOfPages)
    numberOfPages = str(args.numberOfPages)
  except ValueError:
      print("Provided number of pages is invalid")
      exit(-1)
else:
  numberOfPages = "max"

url = args.url
if not url.endswith('/'):
  url = url + '/'

# get the subpath of the url, eg. https://www.example.org/wiki/ => wiki/, or empty for no subpath
subpath = url[url.index("://") + 3:]
subpath = subpath[subpath.index("/")+1:]

pageOnly = -1
categoryOnly = -1
namespace = args.namespace
if args.category is not None:
  categoryOnly = int(args.category)
  if namespace is None:
    namespace = "*" # all namespaces
else:
  if namespace is None:
    namespace = 0
  # the allpages API only supports integer IDs
  namespace = str(int(namespace))
if args.page is not None:
  pageOnly = int(args.page)

# Only create output directory if not in webhook mode
if not is_webhook_mode:
    (args.outputDir / "img").mkdir(parents=True, exist_ok=True)
    if not args.shortUrl.endswith('/'):
        args.shortUrl = args.shortUrl + '/'
    shortUrl = args.shortUrl

S = requests.Session()
if args.username is not None and args.password is not None:
  LgUser = args.username
  LgPassword = args.password
  # Retrieve login token first
  PARAMS_0 = {
      'action':"query",
      'meta':"tokens",
      'type':"login",
      'format':"json"
  }
  R = S.get(url=url + "/api.php", params=PARAMS_0)
  DATA = R.json()
  LOGIN_TOKEN = DATA['query']['tokens']['logintoken']
  # Main-account login via "action=login" is deprecated and may stop working without warning. To continue login with "action=login", see [[Special:BotPasswords]]
  PARAMS_1 = {
      'action':"login",
      'lgname':LgUser,
      'lgpassword':LgPassword,
      'lgtoken':LOGIN_TOKEN,
      'format':"json"
  }
  
  # NEUER, BESSERER CODE für Login-Debug (bereits im vorherigen Step eingefügt)
  print("Attempting to log in...")
  R = S.post(url + "/api.php", data=PARAMS_1)
  try:
    DATA = R.json()
  except json.JSONDecodeError:
    print("ERROR: Could not parse JSON from login response.")
    print("Raw response:", R.text)
    exit(-1)

  # Verbesserte Überprüfung des Login-Status
  if "error" in DATA:
    print(f"ERROR: Login API returned an error: {DATA['error']}")
    exit(-1)
  
  login_result = DATA.get('login', {}).get('result')
  if login_result == 'Success':
    print(f"Login successful for user '{DATA['login']['lgusername']}'.")
    print(f"Session cookies after login: {S.cookies}") # <-- WICHTIGE DEBUG-AUSGABE!
  else:
    print(f"ERROR: Login failed. Result: {login_result}")
    print("Full API response:", DATA)
    print("\nPlease check your username and bot password.")
    exit(-1)

if categoryOnly != -1:
  params_all_pages = {
    'action': 'query',
    'list': 'categorymembers',
    'format': 'json',
    'cmpageid': categoryOnly,
    'cmnamespace': namespace,
    'cmlimit': numberOfPages
  }
else:
  params_all_pages = {
    'action': 'query',
    'list': 'allpages',
    'format': 'json',
    'apnamespace': namespace,
    'aplimit': numberOfPages
  }
response = S.get(url + "api.php", params=params_all_pages)
data = response.json()
if "error" in data:
  print(data)
  if data['error']['code'] == "readapidenied":
    print()
    print("get login token here: " + url + "/api.php?action=query&meta=tokens&type=login")
    print("and then call this script with parameters: myuser topsecret mytoken")
    exit(-1)
if categoryOnly != -1:
  pages = data['query']['categorymembers']
else:
  pages = data['query']['allpages']
# user may want to download a single page, but needs to know the page number
if args.listPages:
    for page in pages:
        print(f'{page["pageid"]}: {page["title"]}')
    exit(0)
while 'continue' in data and (numberOfPages == 'max' or len(pages) < int(numberOfPages)):
  if categoryOnly != -1:
    params_all_pages['cmcontinue'] = data['continue']['cmcontinue']
  else:
    params_all_pages['apcontinue'] = data['continue']['apcontinue']
  response = S.get(url + "api.php", params=params_all_pages)
  data = response.json()
  if "error" in data:
    print(data)
    if data['error']['code'] == "readapidenied":
      print()
      print(f'get login token here: {url}/api.php?action=query&meta=tokens&type=login')
      print("and then call this script with parameters: myuser topsecret mytoken")
      exit(-1)
  if categoryOnly != -1:
    pages.extend(data['query']['categorymembers'])
  else:
    pages.extend(data['query']['allpages'])

# --- Funktion zum Umwandeln relativer URLs in absolute URLs für Webhook-Modus ---
def make_absolute_urls_bs4(html_content, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')

    # base_url sollte immer mit einem '/' enden
    if not base_url.endswith('/'):
        base_url += '/'

    for tag in soup.find_all(src=True):
        if not tag['src'].startswith(('http://', 'https://', '//', 'data:')):
            tag['src'] = parse.urljoin(base_url, tag['src'])
    for tag in soup.find_all(href=True):
        if not tag['href'].startswith(('http://', 'https://', '//', 'data:', '#', 'mailto:')):
            tag['href'] = parse.urljoin(base_url, tag['href'])
    for tag in soup.find_all(srcset=True):
        new_srcset = []
        for item in tag['srcset'].split(','):
            item = item.strip()
            parts = item.split(' ')
            url_part = parts[0]
            if not url_part.startswith(('http://', 'https://', '//', 'data:')):
                new_srcset.append(f"{parse.urljoin(base_url, url_part)}{' '.join(parts[1:])}")
            else:
                new_srcset.append(item)
        tag['srcset'] = ', '.join(new_srcset)
    return str(soup)
# ----------------------------------------------------------------------------------

# Diese Funktionen werden nur im lokalen Exportmodus benötigt
if not is_webhook_mode:
    def quote_title(title):
      return parse.quote(title.replace(' ', '_'))
    downloadedimages = []
    def DownloadImage(filename, urlimg, ignorethumb=True):
      fileOut = f'{args.outputDir}/img/{filename}'
      if not filename in downloadedimages:
        if ignorethumb and '/thumb/' in urlimg:
          urlimg = urlimg.replace('/thumb/', '/')
          urlimg = urlimg[:urlimg.rindex('/')]
        if not urlimg.startswith("http"):
            urlimg = url + urlimg[1:]
        print(f"Downloading {urlimg}")
        response = S.get(urlimg)
        if response.status_code == 404:
          raise Exception("404: cannot download " + urlimg)
        content = response.content
        f = open(fileOut, "wb")
        f.write(content)
        f.close()
        downloadedimages.append(filename)

    def DownloadFile(filename, urlfilepage):
      fileOut = f'{args.outputDir}/img/{filename}'
      if args.dontOverwrite and os.path.exists(fileOut):
          print(f'Ignoring {filename} (already downloaded)')
          downloadedimages.append(filename)
          return
      if not filename in downloadedimages:
        # get the file page
        response = S.get(urlfilepage)
        content = response.text
        filepos = content.find('href="/' + subpath + 'images/')
        if filepos == -1:
          return
        fileendquote = content.find('"', filepos + len('href="'))
        urlfile = content[filepos+len('href="') + len(subpath):fileendquote]
        DownloadImage(filename, urlfile)

    def PageTitleToFilename(title):
        temp = re.sub('[^A-Za-z0-9\u0400-\u0500\u4E00-\u9FFF]+', '_', title);
        return temp.replace("(","_").replace(")","_").replace("__", "_")

# NEU: Liste zum Sammeln aller Seiten-Daten für den Webhook-Batch-Send
webhook_data_batch = []

for page in pages:
    if (pageOnly > -1) and (page['pageid'] != pageOnly):
        continue
    print(f"Processing page: {page['title']} (ID: {page['pageid']})")
    
    quoted_pagename = parse.quote(page['title'].replace(' ', '_'))
    # Die tatsächliche URL der Wiki-Seite, die man im Browser aufrufen würde (Basis für absolute Links)
    page_view_url = url + "index.php?title=" + quoted_pagename 

    # --- ÄNDERUNG HIER: Verwende action=parse statt action=render ---
    params_parse = {
        'action': 'parse',
        'page': page['title'], # Wir können den Titel verwenden
        'format': 'json',
        'prop': 'text' # Fordert den geparsten HTML-Inhalt an
    }
    
    print(f"DEBUG: Requesting API parse for '{page['title']}'. Parameters: {params_parse}")
    response = S.get(url + "api.php", params=params_parse)
    
    # Check for API errors for action=parse
    try:
        parse_data = response.json()
    except json.JSONDecodeError:
        print(f"ERROR: Could not parse JSON from API parse response for '{page['title']}'. Raw response: {response.text}")
        continue # Überspringt diese Seite und geht zur nächsten

    if "error" in parse_data:
        print(f"ERROR: API parse returned an error for '{page['title']}': {parse_data['error']}")
        # Wenn der Fehler "readapidenied" ist, ist die Session nicht gültig
        if parse_data['error']['code'] == "readapidenied":
            print("Login session seems to be invalid or expired for API parsing. Exiting.")
            exit(-1)
        continue # Überspringt diese Seite und geht zur nächsten
    
    # Der HTML-Inhalt ist im 'parse' -> 'text' -> '*' Feld
    raw_content = parse_data['parse']['text']['*'] 
    
    print(f"DEBUG: HTTP Status Code for API parse '{page['title']}': {response.status_code}")
    # Nach action=parse sollte hier eigentlich nie eine Anmeldeseite zurückkommen, 
    # da der API-Login schon früher scheitern würde, wenn nicht genug Berechtigungen da wären.
    # Trotzdem lassen wir die Warnung zur Sicherheit drin.
    if "Anmeldung erforderlich" in raw_content or "Login required" in raw_content or "Spezial:Anmelden" in raw_content:
        print(f"WARNING: API parse for '{page['title']}' returned content resembling a login page! First 500 chars of content:")
        print(raw_content[:500]) # Zeigt die ersten 500 Zeichen an
    # --- ENDE DER ÄNDERUNG ---

    # Entferne Kommentare (gilt für beide Modi)
    processed_content = re.sub("(<!--).*?(-->)", '', raw_content, flags=re.DOTALL)
    
    # --- Modus-spezifische Logik ---
    if is_webhook_mode:
        # Absolute URLs erstellen
        content_with_absolute_urls = make_absolute_urls_bs4(processed_content, page_view_url)
        
        # Die komplette HTML-Struktur, die an n8n gesendet wird
        final_html_output = (
            f"<html>\n<head><title>{page['title']}</title></head>\n<body>\n"
            f"<h1>{page['title']}</h1>\n"
            f"{content_with_absolute_urls}\n"
            f"</body></html>"
        )

        # Das Payload-Format für n8n
        page_payload = {
            'link': page_view_url,  # Die URL der Wiki-Seite
            'content': final_html_output # Der komplette HTML-Inhalt mit absoluten Links
        }
        webhook_data_batch.append(page_payload) # <-- NEU: Payload zur Liste hinzufügen
        
    else: # Lokaler Export-Modus (Original-Funktionalität)
        content = processed_content
        
        # ACHTUNG: Die folgenden URL-Ersetzungen sind für den lokalen Exportmodus gedacht.
        # Da make_absolute_urls_bs4 im lokalen Modus nicht genutzt wird, bleiben diese hier bestehen.
        # Wenn hier immer noch Probleme mit relativen URLs auftreten, müsste diese Logik
        # eventuell durch einen lokalen Aufruf von make_absolute_urls_bs4 ersetzt werden.
        url_title = url + "index.php?title="
        if (url_title not in content) and args.ssl:
            url_title = url_title.replace("http://", "https://")
        if url_title not in content:
            protocol = url_title[:url_title.index(":")]
            url_title_without_protocol = url_title[url_title.index('/'):]
            content = content.replace(f'a href="{url_title_without_indexphp}', f'a href="{protocol}:{url_title_without_protocol}')
        if url_title not in content:
            url_title_without_indexphp = url_title.replace("index.php?title=", shortUrl)
            content = content.replace(f'a href="{url_title_without_indexphp}', f'a href="{url_title}')
        pos = 0
        while url_title in content:
            pos = content.find(url_title)
            posendquote = content.find('"', pos)
            file_url = content[pos:posendquote]
            linkedpage = file_url
            linkedpage = linkedpage[linkedpage.find('=') + 1:]
            linkedpage = linkedpage.replace('%27', '_')
            if linkedpage.startswith('File:') or linkedpage.startswith('Datei:') or linkedpage.startswith('Image:'):
              if linkedpage.startswith('File:'):
                  linkType = "File"
              elif linkedpage.startswith('Datei:'):
                  linkType = "Datei"
              elif linkedpage.startswith('Image:'):
                  linkType = "Image"
              origlinkedpage = linkedpage[linkedpage.find(':')+1:]
              linkedpage = parse.unquote(origlinkedpage)
              if linkType == "File" or linkType == "Datei":
                DownloadFile(linkedpage, file_url)
              content = content.replace(url_title+linkType+":"+origlinkedpage, "img/"+origlinkedpage)
            elif "&amp;action=edit&amp;redlink=1" in linkedpage:
              content = content[:pos] + "page_not_existing.html\" style='color:red'" + content[posendquote+1:]
            elif "#" in linkedpage:
              linkWithoutAnchor = linkedpage[0:linkedpage.find('#')]
              linkWithoutAnchor = PageTitleToFilename(linkWithoutAnchor)
              content = content[:pos] + linkWithoutAnchor + ".html#" + linkedpage[linkedpage.find('#')+1:] + content[posendquote:]
            else:
              linkedpage = PageTitleToFilename(parse.unquote(linkedpage))
              content = content[:pos] + linkedpage + ".html" + content[posendquote:]
        imgpos = 0
        while imgpos > -1:
            imgpos = content.find('href="' + url + 'images/', imgpos)
            if imgpos > -1:
              imgendquote = content.find('"', imgpos + len('href="'))
              imgpath = content[imgpos+len('href="'):imgendquote]
              filename = imgpath[imgpath.rindex("/")+1:]
              DownloadImage(filename, imgpath, ignorethumb=False)
              content = content.replace(content[imgpos + len('href="'):imgendquote], "img/"+filename)
        imgpos = 0
        while imgpos > -1:
            imgpos = content.find('src="/' + subpath + 'images/', imgpos)
            if imgpos > -1:
              imgendquote = content.find('"', imgpos + len('src="'))
              imgpath = content[imgpos+len('src="') + len(subpath):imgendquote]
              filename = imgpath[imgpath.rindex("/")+1:]
              DownloadImage(filename, imgpath, ignorethumb=False)
              content = content.replace("/"+subpath+imgpath, "img/"+filename)
        imgpos = 0
        while imgpos > -1:
            imgpos = content.find('srcset="/' + subpath + 'images/', imgpos)
            if imgpos > -1:
              imgendquote = content.find('"', imgpos + len('srcset="'))
              srcsetval = content[imgpos+len('srcset="'):imgendquote]
              for srcsetitem in srcsetval.split(','):
                imgpath = srcsetitem.strip().split()[0][len(subpath):]
                filename = imgpath[imgpath.rindex("/")+1:]
                DownloadImage(filename, imgpath, ignorethumb=False)
                content = content.replace("/"+subpath+imgpath, "img/"+filename)
        
        f = open(args.outputDir / (PageTitleToFilename(page['title']) + ".html"), "wb")
        f.write(("<html>\n<head><title>" + page['title'] + "</title></head>\n<body>\n").encode("utf8"))
        f.write(("<h1>" + page['title'] + "</h1>").encode("utf8"))
        f.write(content.encode('utf8'))
        f.write("</body></html>".encode("utf8"))
        f.close()

# NEU: Nach der Schleife, wenn im Webhook-Modus, den Batch senden!
if is_webhook_mode and webhook_data_batch: # Nur senden, wenn Daten gesammelt wurden
    print(f"\nSending {len(webhook_data_batch)} pages in a single batch to webhook...")
    try:
        # Hier senden wir die gesamte Liste als ein JSON-Array
        webhook_response = requests.post(args.webhook_url, json=webhook_data_batch, timeout=120) # Timeout erhöht
        webhook_response.raise_for_status()
        print(f"Successfully sent batch to webhook. Status: {webhook_response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not send batch to webhook: {e}")
        exit(-1) # Bei Batch-Fehler ist es sinnvoller abzubrechen

if not is_webhook_mode:
    f = open(args.outputDir / "page_not_existing.html", "wb")
    f.write(("<html>\n<head><title>This page does not exist yet</title></head>\n<body>\n").encode("utf8"))
    f.write(("<h1>This page does not exist yet</h1>").encode("utf8"))
    f.write("</body></html>".encode("utf8"))
    f.close()

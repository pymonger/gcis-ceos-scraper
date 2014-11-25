#!/usr/bin/env python
import os, sys, re, argparse, json, requests
from lxml import html
from lxml.etree import tostring


CEOS_URL = "http://database.eohandbook.com/database/missiontable.aspx"

AGENCY_CACHE_FILE = "agency.json"

ACRO_URL = "http://www.acronymfinder.com/Organizations/"


def query_acronym(a):
    """Query acronym finder service. Return list of possible meanings."""

    #print "Finding meanings for %s" % a
    meanings = []
    r = requests.get("%s/%s.html" % (ACRO_URL, a)) 
    r.raise_for_status()
    t = html.fromstring(r.text)
    tbl = t.xpath('//table[@class="table table-striped result-list"]')
    if len(tbl) == 0: return meanings
    for tr in tbl[0].xpath('tbody/tr'):
        acr = tr.xpath('td[@class="result-list__body__rank"]/a/text()')[0]
        meaning = tr.xpath('td[@class="result-list__body__meaning"]/a/text()')
        if len(meaning) == 1: meaning = meaning[0]
        else: meaning = tr.xpath('td[@class="result-list__body__meaning"]/text()')[0]
        meanings.append((acr, meaning))
    return meanings


def get_agency(a):
    """Return canonical agency name."""

    # simple agency cache
    if os.path.exists(AGENCY_CACHE_FILE):
        with open(AGENCY_CACHE_FILE) as f:
            cache = json.load(f)
    else: cache = {}
    if a in cache: return cache[a]

    # query for possible meanings
    meanings = query_acronym(a)

    # clear console
    os.system("clear")

    # if none found, ask user to specify
    if len(meanings) == 0:
        agency = raw_input("No meaning found for %s. Please specify: " % a)
        cache[a] = agency
        with open(AGENCY_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        return cache[a]

    # ask user to select
    for i, (acr, meaning) in enumerate(meanings[:10]):
        print "%d %s" % (i + 1, meaning)
    while True:
        choice = raw_input("Select meaning to use for %s [default=1] or type 'S' to specify: " % a)
        if choice == 'S':
            agency = raw_input("Please specify: ")
            cache[a] = agency
            with open(AGENCY_CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
            return cache[a]
        if not re.search(r'\d+', choice):
            print "Invalid choice: %s" % choice
            continue
        choice = int(choice) - 1 
        if choice >= 0 and choice < len(meanings):
            print "selected %s" % meanings[choice][1] 
            cache[a] = meanings[choice][1]
            with open(AGENCY_CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
            return cache[a]
        else: print "Invalid choice: %s" % choice
    

def scrape_ceos():
    """Scrape CEOS missions and return as JSON."""

    # build parameters to POST for all results
    r = requests.get(CEOS_URL)
    r.raise_for_status()
    t = html.fromstring(r.text)
    params = {
        "ddlAgency":               "All",
        "ddlDisplayResults":       "All",
        "ddlEOLYearFilterType":    "All",
        "ddlLaunchYearFiltertype": "All",
        "ddlMissionStatus":        "All",
        "ddlRepeatCycleFilter":    "All",
        "tbApplications":          "",
        "tbInstruments":           "",
        "tbMission":               "",
        "btExportToExcel":         "",
        "__VIEWSTATE":             t.xpath('//input[@id="__VIEWSTATE"]')[0].get('value'),
        "__EVENTVALIDATION":       t.xpath('//input[@id="__EVENTVALIDATION"]')[0].get('value'),
        "__EVENTTARGET":           "",
        "__EVENTARGUMENT":         "",
        "__LASTFOCUS":             "",
        "__VIEWSTATEENCRYPTED":    "",
    } 

    # get all results
    r = requests.post(CEOS_URL, data=params)
    r.raise_for_status()
    t = html.fromstring(r.text)
    #print tostring(t, pretty_print=True)

    # extract headers
    headers = [th for th in t.xpath('//tr/th/text()')] 
    #print headers

    # extract mission info
    missions = []
    for tr in t.xpath('//tr[position() > 1]'):
        mission = {}
        for i, td in enumerate(tr.xpath('td/text()')):
            # replace NO-BREAK SPACE (\u00a0) with null
            if td == u'\u00a0': td = None

            # if agency
            if headers[i] == "Mission Agencies":
                # split multiple agencies
                agencies = []
                for a in td.split(','):
                    a = a.strip()
                    match = re.search(r'^(\w+)\s*\(.+\)$', a)
                    if match: a = match.group(1)
                    agencies.append(a)
                #print "agencies:", agencies
                mission[headers[i]] = agencies
                agency_names = [get_agency(a) for a in agencies]
                mission['canonical-agency-names'] = agency_names
            else: mission[headers[i]] = td
        missions.append(mission)

    print json.dumps(missions, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape CEOS metadata.')
    #parser.add_argument('url', nargs='?', default=url, help='CEOS url')
    args = parser.parse_args()

    scrape_ceos()

#!/usr/bin/env python
import sys
import psycopg2
import psycopg2.extras
import requests
import json
import re
import getopt
import logging
from settings import config

logging.basicConfig(
    format='%(asctime)s:%(levelname)s:%(message)s', filename='/tmp/sync_facilities.log',
    datefmt='%Y-%m-%d %I:%M:%S', level=logging.DEBUG
)
cmd = sys.argv[1:]
opts, args = getopt.getopt(
    cmd, 'c:u:l:af',
    ['created-since', 'updated-since', 'id-list', 'all-facilities', 'force-sync'])

SYNC_ALL = False
FORCE_SYNC = False
facility_id_list = ""
# This the additional query string to DHIS2 orgunit URL
query_string = "fields=id,code,name,parent[id,name,href],dataSets[id],organisationUnitGroups[id]"

for option, parameter in opts:
    if option == '-a':
        query_string += "&paging=false"
        SYNC_ALL = True
    if option == '-c':
        query_string += "&filter=created:ge:%s" % (parameter)
    if option == '-u':
        query_string += "&filter=lastUpdated:ge:%s" % (parameter)
    if option == '-l':
        facility_id_list = parameter
    if option == '-f':
        FORCE_SYNC = True

URL = "%s.json?%s" % (config["orgunits_url"], query_string)
url_list = []
if facility_id_list:
    for dhis2id in facility_id_list.split(','):
        url_list.append("%s/%s.json?%s" % (config["orgunits_url"], dhis2id.strip(), query_string))

user = config["dhis2_user"]
passwd = config["dhis2_passwd"]

conn = psycopg2.connect(
    "dbname=" + config["dbname"] + " host= " + config["dbhost"] + " port=" + config["dbport"] +
    " user=" + config["dbuser"] + " password=" + config["dbpasswd"])

cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)


def get_url(url, payload={}):
    res = requests.get(url, params=payload, auth=(user, passwd))
    return res.text


def get_facility_details(facilityJson):
    is_033b = False
    level = ""
    # parent = facilityJson["parent"]["name"].replace('Subcounty', '').strip()
    parent = re.sub(
        'Subcounty.*$|Sub\ County.*$', "", facilityJson["parent"]["name"],
        flags=re.IGNORECASE).strip()
    district_url = "%s/%s.json?fields=id,name,parent" % (config["orgunits_url"], facilityJson["parent"]["id"])
    print district_url
    districtJson = get_url(district_url)
    # district = json.loads(districtJson)["parent"]["name"].replace('District', '').strip()
    district = re.sub(
        'District.*$', "",
        json.loads(districtJson)["parent"]["name"], flags=re.IGNORECASE).strip()

    orgunitGroups = facilityJson["organisationUnitGroups"]
    orgunitGroupsIds = ["%s" % k["id"] for k in orgunitGroups]
    for k, v in config["levels"].iteritems():
        if k in orgunitGroupsIds:
            level = v

    dataSets = facilityJson["dataSets"]
    dataSetsIds = ["%s" % k["id"] for k in dataSets]
    if getattr(config, "hmis_033b_id", "V1kJRs8CtW4") in dataSetsIds:
        is_033b = True
    # we return tuple (Subcounty, District, Level, is033B)
    return parent, district, level, is_033b

if FORCE_SYNC:  # this is only used when you want to sync the contents alread id sync db
    logging.debug("START FULL SYNC for DB")
    cur.execute(
        "SELECT id, name, uuid, dhis2id, district, subcounty, level, is_033b "
        "FROM facilities WHERE level <> ''")
    res = cur.fetchall()
    for r in res:
        sync_params = {
            'username': config["sync_user"], 'password': config["sync_passwd"],
            'name': r["name"], 'uuid': r["uuid"],
            'dhis2id': r["dhis2id"], 'ftype': r["level"], 'district': r["district"],
            'subcounty': r["subcounty"], 'is_033b': r["is_033b"]
        }
        try:
            resp = get_url(config["sync_url"], sync_params)
            logging.debug("Syncing facility: %s" % r["uuid"])
        except:
            logging.error("E00: Sync Service failed for facility: %s" % r["uuid"])
    logging.debug("END FULL SYNC for DB")
    sys.exit()

if facility_id_list and url_list:  # this is for a list of ids
    orgunits = []
    for url in url_list:
        try:
            response = get_url(url)
            orgunit_dict = json.loads(response)
            orgunits.append(orgunit_dict)
        except:
            logging.error("E01: Sync Service failed for multiple ids:")
            pass  # just keep quiet
else:
    try:
        response = get_url(URL)
        orgunits_dict = json.loads(response)
        orgunits = orgunits_dict['organisationUnits']
    except:
        logging.error("E02: Sync Service failed")
        # just keep quiet for now
for orgunit in orgunits:
    subcounty, district, level, is_033b = get_facility_details(orgunit)
    cur.execute(
        "SELECT id, name, uuid, dhis2id, district, subcounty, level, is_033b "
        "FROM facilities WHERE dhis2id = %s", [orgunit["id"]])
    res = cur.fetchone()
    if not res:  # we don't have an entry already
        logging.debug("Sync Service: adding facility:%s to fsync" % orgunit["id"])
        cur.execute(
            "INSERT INTO facilities(name, dhis2id, uuid, district, subcounty, level, is_033b) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (orgunit["name"], orgunit["id"], orgunit["uuid"], district, subcounty, level, is_033b))
        # call service to create it in mTrac
        sync_params = {
            'username': config["sync_user"], 'password': config["sync_passwd"],
            'name': orgunit["name"], 'uuid': orgunit["uuid"],
            'dhis2id': orgunit["id"], 'ftype': level, 'district': district,
            'subcounty': subcounty, 'is_033b': is_033b
        }
        try:
            resp = get_url(config["sync_url"], sync_params)
            print "Sync Service: %s" % resp
        except:
            print "Sync Service failed for:%s" % orgunit["id"]
            logging.error("E03: Sync Service failed for:%s" % orgunit["id"])
    else:  # we have the entry
        logging.debug("Sync Service: updating facility:%s to fsync" % orgunit["id"])
        cur.execute(
            "UPDATE facilities SET name = %s, dhis2id = %s, "
            "district = %s, subcounty = %s, level = %s, is_033b = %s, "
            "ldate = NOW()"
            "WHERE dhis2id = %s",
            (orgunit["name"], orgunit["uuid"], district, subcounty, level, is_033b, orgunit["id"]))
        if (res["name"] != orgunit["name"]) or (res["level"] != level) or \
                (res["is_033b"] != is_033b) or (res["district"] != district) or \
                (res["subcounty"] != subcounty):
                print "Worth Updating..........", res["id"]
                sync_params = {
                    'username': config["sync_user"], 'password': config["sync_passwd"],
                    'name': orgunit["name"], 'uuid': "",
                    'dhis2id': orgunit["id"], 'ftype': level, 'district': district,
                    'subcounty': subcounty, 'is_033b': is_033b
                }
                try:
                    resp = get_url(config["sync_url"], sync_params)
                    logging.debug("Sync Service: ")
                    print "Sync Service: %s" % resp
                except:
                    print "Sync Service failed for:%s" % orgunit["id"]
                    logging.error("E04: Sync Service failed for:%s" % orgunit["id"])
        else:
            print "Sync Service: Nothing changed for facility:[UID: %s]" % orgunit["id"]

    conn.commit()

conn.close()

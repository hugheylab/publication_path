import requests
from c3po.db import get_db
from c3po.db import pg_query
from c3po.db import get_orcid_read_token
from c3po.db import get_orcid_app_info
import xml.etree.ElementTree as ET


public_base_url = 'https://pub.orcid.org/v3.0/'
oauth_base_url = 'https://orcid.org/oauth/authorize'
token_url = 'https://orcid.org/oauth/token'
redirect_uri = 'https://localhost:5000/auth/register'
accept = 'application/vnd.orcid+xml'

def get_app_info(db):
    return(get_orcid_app_info(db))

def get_oauth_link(app_key):
    if app_key is None:
        db = get_db()
        app_key = get_app_info(db)
        db.close()
    orcid_auth_link = oauth_base_url + '?client_id=' + app_key['client_id'] + '&response_type=code&scope=/authenticate&redirect_uri=' + redirect_uri
    return(orcid_auth_link)

def get_read_token():
    get_orcid_read_token(token_url = token_url)

def get_login_access_token(code, db, app_key):
    if app_key is None:
        app_key = get_app_info(db)
    headers = {'Accept' : 'application/json'}
    data = {}
    data = { 
        'client_id' : app_key['client_id'],
        'client_secret' : app_key['client_secret'],
        'grant_type' : 'authorization_code',
        'code' : code,
        'redirect_uri' : redirect_uri,
    }
    r = requests.post(token_url, headers=headers, data=data)
    print('Access token response: ' + r.text)
    orcid_user = pg_query(db, 'fetchone', 'SELECT * FROM user_orcid WHERE orcid_id = \'' + r.json()['orcid'] + '\' AND orcid_scope = \'/authenticate\'', ())
    if orcid_user != None:
        sql = 'UPDATE user_orcid SET orcid_access_token = %s, orcid_refresh_token = %s, orcid_scope = %s, raw_text = %s WHERE orcid_id = %s AND orcid_scope = %s;'
        values = (r.json()['access_token'], r.json()['refresh_token'], r.json()['scope'], r.text, r.json()['orcid'], r.json()['scope'])
        pg_query(db, 'update', sql, values)
    else:
        sql = ''' INSERT INTO user_orcid(orcid_id, orcid_access_token, orcid_refresh_token, orcid_name, orcid_scope, raw_text, full_name)
            VALUES(%s, %s, %s, %s, %s, %s, %s) '''
        values = (r.json()['orcid'], r.json()['access_token'], r.json()['refresh_token'], r.json()['name'], r.json()['scope'], r.text, r.json()['name'])
        # cur = db.cursor()
        # cur.execute(sql, email_url_tmp)
        # db.commit()
        pg_query(db, 'insert', sql, values)
    return(r.json()['orcid'])

def get_user_works(orcid, app_key):
    if app_key is None:
        db = get_db()
        app_key = get_app_info(db)
        db.close()
    url = public_base_url + orcid +'/record'
    headers = { 'Authorization' : 'Bearer ' + app_key['read_public_key'],
     'Accept' : accept }
    r = requests.get(url, headers = headers)
    root = ET.fromstring(r.text)
    works_xml_parse_string = ('{http://www.orcid.org/ns/activities}activities-summary/' + 
        '{http://www.orcid.org/ns/activities}works/' +
        '{http://www.orcid.org/ns/activities}group/' +
        '{http://www.orcid.org/ns/common}external-ids/' +
        '{http://www.orcid.org/ns/common}external-id')
    external_id_type = '{http://www.orcid.org/ns/common}external-id-type'
    external_id_value = '{http://www.orcid.org/ns/common}external-id-value'
    dois = []
    for external_id in root.findall(works_xml_parse_string):
        if external_id.find(external_id_type).text == 'doi':
            dois.append(external_id.find(external_id_value).text)
    return(dois)
    

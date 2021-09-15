from c3po.auth import login_required
import functools
import re
import psycopg2
from psycopg2.extras import DictCursor

from datetime import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify
)
import requests
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import close_db, get_db
from c3po.db import pg_query
from c3po.email_handler import send_email
from c3po.orcid_api import get_user_works
from c3po.orcid_api import get_app_info
import hashlib

bp = Blueprint('home', __name__, url_prefix='/home')

@bp.route('/landing', methods=('GET', 'POST'))
@login_required
def landing():
    return render_template('home/landing.html', user = g.user)

@bp.route('/orcid', methods=('GET', 'POST'))
@login_required
def orcid():
    orcid = g.user['orcid_id']
    dois = get_user_works(orcid, None)
    print(dois)
    query_val = str(dois).replace('[', '(').replace(']', ')')
    print(query_val)
    close_db()
    db = get_db()
    user_papers = pg_query(db, 'fetchone', 'SELECT * FROM user_papers WHERE orcid_id = %s', (orcid,))
    if user_papers is None or len(user_papers) == 0:
        query = (
            'INSERT INTO user_papers (orcid_id, dois) '
            'VALUES (%s, ARRAY ' + str(dois) + ') ;')
        values = (g.user['orcid_id'],)
        print(query)
        pg_query(db, 'insert', query, values)
    else:
        dois_in_db = user_papers['dois']
        added = False
        for doi in dois:
            if doi not in dois_in_db:
                dois_in_db.append(doi)
                added = True
        if added:
            query = (
                'UPDATE user_papers SET dois = ARRAY ' + str(dois_in_db).replace('None, ', '') + ' WHERE '
                'orcid_id = %s;')
            values = (g.user['orcid_id'],)
            print(query)
            pg_query(db, 'update', query, values)
    articles = pg_query(db, 'fetchall', 'SELECT * FROM article_info WHERE doi IN ' + query_val + ' ORDER BY pub_date DESC', ())
    print(articles)
    if len(articles) > 0:
        print(articles[0])
        print(articles[0]["title"])
    article_infos = []

    all_author_ids = '('

    all_has_emails = False

    for article in articles:
        doi = article['doi']
        doi_child = pg_query(db, 'fetchone', 'SELECT * FROM doi_child_tables WHERE doi = %s', (doi,))

        print(doi_child)

        auth_ids = str(doi_child['author_ids']).replace('[', '(').replace(']', ')')

        email_ids = str(doi_child['email_ids']).replace('[', '(').replace(']', ')')

        email_ids = email_ids.replace('None, ', '').replace('None)', ')')

        # cur.execute(
        #     'SELECT * FROM author_doi WHERE doi = %s', (doi,)
        # )
        # authors = cur.fetchall()
        authors = pg_query(db, 'fetchall', 'SELECT * FROM author_doi WHERE id IN ' + auth_ids + ' ORDER BY author_pos ASC NULLS LAST, affiliation_pos ASC ', ())

        completed_urls = pg_query(db, 'fetchall', 'SELECT * FROM email_url WHERE doi = %s and completed_timestamp IS NOT NULL ORDER BY completed_timestamp DESC LIMIT 1 ', (doi,))
        
        has_path = (completed_urls != None and len(completed_urls) > 0)

        auth_aff_list = []
        affiliation_list = []
        for author in authors:
            if author['author_affiliation'] in affiliation_list:
                aff_num = affiliation_list.index(author['author_affiliation']) + 1
            elif author['author_affiliation'] != None:
                affiliation_list.append(author['author_affiliation'])
                aff_num = len(affiliation_list)
            if len(auth_aff_list) > 0 and auth_aff_list[len(auth_aff_list) - 1].author['author_pos'] == author['author_pos']:
                auth_aff_list[len(auth_aff_list) - 1].affiliation_nums.append(aff_num)
            else:
                if author['author_affiliation'] == None:
                    auth_aff = author_affiliations(author, [])
                else:
                    auth_aff = author_affiliations(author, [aff_num])
                auth_aff_list.append(auth_aff)

        # cur.execute(
        #     'SELECT * FROM email_doi WHERE doi = %s', (doi,)
        # )
        # emails = cur.fetchall()
        email_list = []
        emails = None
        if auth_ids != '()':
            all_author_ids = all_author_ids + str(doi_child['author_ids']).replace('[', '').replace(']', '') + ',' 
        has_emails = True
        if emails == None or len(emails) == 0:
            has_emails = False
        else:
            for email_tmp in emails:
                if not email_tmp['email'] in email_list:
                    email_list.append(email_tmp['email'])
        all_has_emails = (all_has_emails or has_emails)
        article_info_tmp = article_info(article, auth_aff_list, emails, has_emails, affiliation_list, has_path)
        article_infos.append(article_info_tmp)
        email_list.sort()

    return render_template('home/orcid.html', user = g.user, dois = dois, article_infos = article_infos)

class article_info:
  def __init__(self, article, authors, emails, has_emails, affiliation_list, has_path):
    self.article = article
    self.authors = authors
    self.emails = emails
    self.has_emails = has_emails
    self.affiliation_list = affiliation_list
    self.has_path = has_path

class author_affiliations:
    def __init__(self, author, affiliation_nums):
        self.author = author
        self.affiliation_nums = affiliation_nums
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

from c3po.db import get_db
from c3po.db import pg_query
from c3po.email_handler import send_email
import c3po.orcid_api
import hashlib

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=('GET', 'POST'))
def register():

    url_code = request.args.get('code')
    db = get_db()
    # Uncomment below and replace string with dynamic link redirect
    redirect_uri = 'https://localhost:5000/auth/register'
    app_key = c3po.orcid_api.get_app_info(db)
    scope = '/authenticate'
    orcid_link = 'https://orcid.org/oauth/authorize?client_id=' + app_key['client_id'] + '&response_type=code&scope=' + scope + '&redirect_uri=' + redirect_uri
    if url_code != None and url_code != "" :
        print('url_code: ' + url_code)
        orcid_auth_url = 'https://orcid.org/oauth/token'
        headers = {'Accept' : 'application/json'}
        data = { 
            'client_id' : app_key['client_id'],
            'client_secret' : app_key['client_secret'],
            'grant_type' : 'authorization_code',
            'code' : url_code,
            'redirect_uri' : redirect_uri,
        }
        r = requests.post(orcid_auth_url, headers=headers, data=data)
        print(r.json())
        orcid_user = pg_query(db, 'fetchone', 'SELECT * FROM user_orcid WHERE orcid_id = \'' + r.json()['orcid'] + '\' AND orcid_scope = \'' + scope + '\'', ())
        if orcid_user != None:
            sql = 'UPDATE user_orcid SET orcid_access_token = %s, orcid_refresh_token = %s, orcid_scope = %s, raw_text = %s WHERE orcid_id = %s AND orcid_scope = %s;'
            values = (r.json()['access_token'], r.json()['refresh_token'], r.json()['scope'], r.text, r.json()['orcid'], r.json()['scope'])
            pg_query(db, 'update', sql, values)
        else:
            sql = ''' INSERT INTO user_orcid(orcid_id, orcid_access_token, orcid_refresh_token, orcid_name, orcid_scope, raw_text)
                VALUES(%s, %s, %s, %s, %s, %s) '''
            values = (r.json()['orcid'], r.json()['access_token'], r.json()['refresh_token'], r.json()['name'], r.json()['scope'], r.text)
            # cur = db.cursor()
            # cur.execute(sql, email_url_tmp)
            # db.commit()
            pg_query(db, 'insert', sql, values)
    else:
        db.close()
        return(render_template('auth/register.html', orcid_link = orcid_link))

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view

class email_url:
  def __init__(self, email, url_param_id, doi, revision, author_id, completed_timestamp):
    self.email = email
    self.url_param_id = url_param_id
    self.doi = doi
    self.revision = revision
    self.author_id = author_id
    self.completed_timestamp = completed_timestamp

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
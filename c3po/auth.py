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
from c3po.db import close_db
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
    app_key = c3po.orcid_api.get_app_info(db)
    orcid_link = c3po.orcid_api.get_oauth_link(app_key);
    if url_code != None and url_code != "" :
        orcid_user_id = c3po.orcid_api.get_login_access_token(url_code, db, app_key)
        session.clear()
        session['user_id'] = orcid_user_id
        db.close()
        return redirect(url_for('home.landing'))
    else:
        db.close()
        return(render_template('auth/register.html', orcid_link = orcid_link))

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = pg_query(db, 'fetchone', 'SELECT * FROM user_orcid WHERE orcid_id = \'' + user_id + '\';', ())
        close_db()
        db.close()

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.register'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.register'))

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
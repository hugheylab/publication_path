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

@bp.route('/initialize', methods=('GET', 'POST'))
def initialize():
    if g.user['full_name'] == None:
        g.user['full_name'] = ''
    if g.user['email'] == None:
        g.user['email'] = ''
    if g.user['gender'] == None:
        g.user['gender'] = ''
    if g.user['ethnicity'] == None:
        g.user['ethnicity'] = ''
    if g.user['career_stage'] == None:
        g.user['career_stage'] = ''
    if g.user['highest_education'] == None:
        g.user['highest_education'] = ''
    gender_opts = ['', 'Female', 'Male', 'Non-Binary', 'Other', 'Prefer not to answer']
    ethnicity_opts = ['', 'American Indian or Alaska Native', 'Asian',
        'Black or African American', 'Hispanic or Latino', 'Native Hawaiian or Other Pacific Islander',
        'White', 'Other', 'Prefer not to answer']
    career_opts = ['', 'Undergraduate', 'Graduate student', 'Postdoctoral scholar',
        'Principal investigator', 'Research staff', 'Other', 'Prefer not to answer']
    education_opts = ['', 'High School', 'Bachelors', 'Masters', 'PHD', 'Other',
    'Prefer not to answer']
    if request.method == 'POST' and 'save' in request.form:
        db = get_db()
        query = (
            'UPDATE user_orcid SET email = %s, gender = %s, '
            'ethnicity = %s, career_stage = %s, highest_education = %s, '
            'initialized = true '
            'WHERE orcid_id = %s;')
        values = (request.form['email'], request.form['gender'],
        request.form['ethnicity'], request.form['career_stage'], request.form['highest_education'],
        g.user['orcid_id'])
        pg_query(db, 'insert', query, values)
        db.close()
        return(redirect(url_for('home.landing')))
    
    return(render_template('auth/initialize.html', user = g.user, gender_opts = gender_opts, ethnicity_opts = ethnicity_opts, career_opts = career_opts, education_opts = education_opts))

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = pg_query(db, 'fetchone', 'SELECT * FROM user_orcid WHERE orcid_id = \'' + user_id + '\';', ())
        close_db()

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.register'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.register'))
        else:
            if g.user['initialized']:
                return view(**kwargs)
            else:
                return redirect(url_for('auth.initialize'))

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
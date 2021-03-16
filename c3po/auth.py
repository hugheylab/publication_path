import functools
import re
import psycopg2
from psycopg2.extras import DictCursor

from datetime import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db
from c3po.email_handler import send_email

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=('GET', 'POST'))
def register():

    if request.method == 'POST':
        db = get_db()
        cur = db.cursor()
        error = None
        doi = request.form['doi']
        email = ''
        if len(re.findall('[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]+', doi)) > 0:
            email = str(doi)
            print('Email: ' + email)

            cur.execute(
                'SELECT * FROM email_doi WHERE email = ?', (email,)
            )
            emails = cur.fetchall()
            cur = db.cursor()

            print(str(emails))

            if len(emails) == 0:
                error = "No articles found associated to supplied email. Please search for a different email or a specific article."
                flash(error)
                return render_template('auth/register.html')
            else:
                return redirect(url_for('auth.confirm', doi = doi, email = email))

        if 'doi.org' in doi:
            doi = doi.replace('http://www.', '')
            doi = doi.replace('https://www.', '')
            doi = doi.replace('https://', '')
            doi = doi.replace('http://', '')
            doi = doi.replace('www.doi.org/', '')
            doi = doi.replace('doi.org/', '')


        cur.execute(
            'SELECT * FROM article_info WHERE doi = %s', (doi,)
        )
        article = cur.fetchone()
        cur = db.cursor()
        pmid = 0
        if article is None:
            pmid = doi
            cur.execute(
                'SELECT * FROM article_info WHERE pmid = %s', (pmid,)
            )
            article = cur.fetchone()
            cur = db.cursor()
            if not article is None:
                doi = article["doi"]

        cur.execute(
            'SELECT * FROM email_doi WHERE doi = %s', (doi,)
        )
        emails = cur.fetchone()
        cur = db.cursor()

        if article is None:
            error = "No article found with supplied DOI. Please try searching again."
        elif emails is None:
            error = "No emails associated with supplied DOI. Please try searching for another DOI."
        else:
            cur.execute(
                'SELECT * FROM author_doi WHERE doi = %s', (doi,)
            )
            authors = cur.fetchall()
            cur = db.cursor()

            if authors is None:
                error = 'No authors found for selected DOI.'

            if error is None:
                return redirect(url_for('auth.confirm', doi = doi, email = email))

        

        flash(error)
    
    return render_template('auth/register.html')

@bp.route('/confirm', methods=('GET', 'POST'))
def confirm():

    doi = request.args.get('doi')
    email = request.args.get('email')
    db = get_db()
    cur = db.cursor()

    cur.execute(
        'SELECT * FROM article_info WHERE doi = %s', (doi,)
    )
    articles = cur.fetchall()
    print(articles)
    print(articles[0])
    print(articles[0]["title"])
    cur = db.cursor()


    cur.execute(
        'SELECT * FROM author_doi WHERE doi = %s', (doi,)
    )
    authors = cur.fetchall()
    cur = db.cursor()


    cur.execute(
        'SELECT * FROM email_doi WHERE doi = %s', (doi,)
    )
    emails = cur.fetchall()
    cur = db.cursor()

    error = None
    if request.method == 'POST':
        now = datetime.now().timestamp()
        now = round(now)

        for email in emails:
            print(str(email['email']) + ' found in form: ' + str(email['email'] in request.form))
        print('REQUEST: ' + str(request.form.__dict__))

        # email_urls = list()
        sentEmail = False

        for email in emails:
            if email['email'] in request.form:
                for aTmp in articles:
                    if aTmp['doi'] == email['doi']:
                        article = aTmp
                sentEmail = True
                url_id = str(now) + str(hash(email['email']))
                revision = 1
                cur.execute(
                    'SELECT * FROM email_url WHERE email = %s AND doi = %s ORDER BY revision DESC LIMIT 1', (email['email'], doi,)
                )
                emUrl = cur.fetchone()
                cur = db.cursor()
                if not emUrl is None:
                    revision = int(emUrl['revision']) + 1
                # email_url_tmp = email_url(email = author['email'], url_param_id = url_id, doi = doi, revision = '1', completed_timestamp = '')
                sql = ''' INSERT INTO email_url(email,url_param_id,doi,revision)
                VALUES(%s,%s,%s,%s) '''
                email_url_tmp = (email['email'], url_id, doi, revision)
                cur = db.cursor()
                cur.execute(sql, email_url_tmp)
                db.commit()
                error = cur.lastrowid

                message_text = """\
                <html>
                    <body>
                        <p>Hello,<br/> You have been registered to enter in publication information for the Hughey Lab publication pipeline project! Here is the paper you were registered to enter:<br/>
                        DOI: """ + doi + """<br/>
                        Title: """ + article['title'] + """<br/>
                        Here is your unique URL: http://3.142.187.194/:5000/enter/""" + url_id + """</p>
                    </body>
                </html>
                """

                send_email(receiver_email = email['email'], message_text = message_text, subject = ('Hughey Lab Publication Path Entry For DOI ' + doi), db = db)

                # email_urls.append(email_url_tmp)
        if sentEmail == True:
            return redirect(url_for('thanks.thanks', thanks_type = 'registration'))
        else:
            error = 'No emails selected, please select at least one email to send url to.'






        flash(error)

    
    return render_template('auth/confirm.html', doi = doi, articles = articles, authors = authors, emails = emails)

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
  def __init__(self, email, url_param_id, doi, revision, completed_timestamp):
    self.email = email
    self.url_param_id = url_param_id
    self.doi = doi
    self.revision = revision
    self.completed_timestamp = completed_timestamp
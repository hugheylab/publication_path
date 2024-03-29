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
from c3po.db import pg_query
from c3po.email_handler import send_email
import hashlib

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=('GET', 'POST'))
def register():

    if request.method == 'GET':
        url_doi = request.args.get('doi')
        email = request.args.get('email')
        if email != None and email != '':
            return render_template('auth/register.html', doi = email, search_type = 'email')
        elif url_doi != None and url_doi != '':
            return render_template('auth/register.html', doi = url_doi, search_type = 'doi')

    if request.method == 'POST':
        db = get_db()
        error = None
        doi_val = request.form['doi']
        print('doi_val: '+doi_val)
        doi_val = doi_val.replace('   ', '')
        doi_val = doi_val.replace('  ', '')
        doi_val = doi_val.replace(' ', '')
        doi_val = doi_val.replace('\r\n', '')
        doi_val = doi_val.replace('\n', '')
        doi_val = doi_val.replace('\r', '')
        email_val = ''
        author_val = ''
        query_val = str(doi_val.split(',')).replace('[', '(').replace(']', ')')
        search_type = request.form['search_type']
        if search_type == 'email':
            email_val = doi_val
            query_emails = query_val
            print('query_emails: ' + query_emails)

            emails = pg_query(db, 'fetchall', 'SELECT * FROM email_doi_tables WHERE email IN ' + query_emails,())
            if emails == None or len(emails) == 0:
                error = "No articles found associated to supplied email(s). Please check your search and try again."
                flash(error)
                return render_template('auth/register.html', doi = request.form['doi'], search_type = search_type)
            dois = []
            for email in emails:
                print(email['dois'])
                for doi_tmp in email['dois']:
                    dois.append(doi_tmp)
            query_dois = str(dois).replace('[', '(').replace(']', ')')
            print(query_dois)
        # elif search_type == 'pmid':
        #     query_pmids = '('
        #     for pmid in doi_val.split(','):
        #         if not pmid.isnumeric():
        #             error = "One or more value(s) supplied are not numeric PubMed IDs. Please check your search and try again."
        #             flash(error)
        #             return render_template('auth/register.html', doi = request.form['doi'], search_type = search_type)
        #         query_pmids = query_pmids + pmid + ','
            
        #     query_pmids = query_pmids[:-1] + ')'
        #     print('query_pmids: ' + query_pmids)
        #     pmid_dois = pg_query(db, 'fetchall', 'SELECT * FROM pmid_doi WHERE pmid IN ' + query_pmids,())
        #     if pmid_dois == None or len(pmid_dois) == 0:
        #         error = "No articles found associated to supplied pmid(s). Please check your search and try again."
        #         flash(error)
        #         return render_template('auth/register.html', doi = request.form['doi'], search_type = search_type)
        #     dois = []
        #     for pmid_doi in pmid_dois:
        #         dois.append(pmid_doi['doi'])
        #     query_dois = str(dois).replace('[', '(').replace(']', ')')
        #     print(query_dois)
        elif search_type == 'author':
            author_val = request.form['doi']

            query_authors = query_val
            print('query_authors: ' + query_authors)
        else:
            query_dois = query_val
            if 'doi.org' in doi_val:
                doi_val = doi_val.replace('http://www.', '')
                doi_val = doi_val.replace('https://www.', '')
                doi_val = doi_val.replace('https://', '')
                doi_val = doi_val.replace('http://', '')
                doi_val = doi_val.replace('www.doi.org/', '')
                doi_val = doi_val.replace('doi.org/', '')
                query_dois = str(doi_val.split(',')).replace('[', '(').replace(']', ')')
                print(query_dois)
            pmids = '('
            dois = ''
            for s in doi_val.split(','):
                if s.isnumeric():
                    pmids = pmids + s + ','
                else:
                    dois = dois + s + ','
            if pmids != '(':
                query_pmids = pmids[:-1] + ')'
                pmid_dois = pg_query(db, 'fetchall', 'SELECT * FROM pmid_doi WHERE pmid IN ' + query_pmids,())
                if pmid_dois != None and len(pmid_dois) > 0:
                    for pmid_doi in pmid_dois:
                        dois = dois + pmid_doi['doi'] + ','
            if dois == '':
                error = "No article(s) found with supplied DOI(s)/Pubmed ID(s). Please try searching again."
                flash(error)
                return render_template('auth/register.html', doi = request.form['doi'], search_type = search_type)
            query_dois = str(dois.split(',')).replace('[', '(').replace(']', ')')

        articles = pg_query(db, 'fetchall', 'SELECT * FROM article_info WHERE doi IN ' + query_dois,())
        if articles is None or len(articles) == 0:
            error = "No article(s) found with supplied DOI(s)/Pubmed ID(s). Please try searching again."
            flash(error)
            return render_template('auth/register.html', doi = request.form['doi'], search_type = search_type)
        db.close()
        doi_val = query_dois.replace('(', '').replace(')', '').replace('\'', '').replace(' ', '')
        return redirect(url_for('auth.confirm', doi = doi_val, email = email_val))
    
    return render_template('auth/register.html')

@bp.route('/confirm', methods=('GET', 'POST'))
def confirm():

    url_doi = request.args.get('doi')
    dois = url_doi.split(',')
    query_val = str(dois).replace('[', '(').replace(']', ')')
    email = request.args.get('email')
    if request.method == 'POST' and 'back' in request.form:
        return redirect(url_for('auth.register', doi = url_doi, email = email))
    email_list = []
    if email != None and email != '':
        email_list = email.split(',')
    db = get_db()

    # cur.execute(
    #     'SELECT * FROM article_info WHERE doi = %s', (doi,)
    # )
    # articles = cur.fetchall()
    articles = pg_query(db, 'fetchall', 'SELECT * FROM article_info WHERE doi IN ' + query_val + ' ORDER BY pub_date DESC', ())
    print(articles)
    print(articles[0])
    print(articles[0]["title"])

    article_infos = []

    all_email_ids = '('

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
        emails = None
        if email_ids != '()':
            all_email_ids = all_email_ids + str(doi_child['email_ids']).replace('[', '').replace(']', '') + ',' 
            emails = pg_query(db, 'fetchall', 'SELECT * FROM email_doi WHERE id IN ' + email_ids, ())
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

    error = None
    if request.method == 'POST':
        all_email_ids = all_email_ids[:-1] + ')'
        all_emails = pg_query(db, 'fetchall', 'SELECT * FROM email_doi WHERE id IN ' + all_email_ids, ())

        now = datetime.now().timestamp()
        now = round(now)

        for email in all_emails:
            doi_email_str = email['doi'] + '---' + email['email']
            print(doi_email_str + ' found in form: ' + str(doi_email_str in request.form))
        print('REQUEST: ' + str(request.form))

        # email_urls = list()
        sentEmail = False

        for email in all_emails:
            doi_email_str = email['doi'] + '---' + email['email']
            if doi_email_str in request.form:
                for aTmp in articles:
                    if aTmp['doi'] == email['doi']:
                        article = aTmp
                sentEmail = True
                url_id = str(now) + str(hash(email['email'])) + str(hash(email['doi']))
                revision = 1
                # cur.execute(
                #     'SELECT * FROM email_url WHERE email = %s AND doi = %s ORDER BY revision DESC LIMIT 1', (email['email'], doi,)
                # )
                # emUrl = cur.fetchone()
                emUrl = pg_query(db, 'fetchone', 'SELECT * FROM email_url WHERE email = %s AND doi = %s ORDER BY revision DESC LIMIT 1', (email['email'], email['doi'],))
                if not emUrl is None:
                    revision = int(emUrl['revision']) + 1
                # email_url_tmp = email_url(email = author['email'], url_param_id = url_id, doi = doi, revision = '1', completed_timestamp = '')
                sql = ''' INSERT INTO email_url(email,url_param_id,doi,revision)
                VALUES(%s,%s,%s,%s) '''
                email_url_tmp = (email['email'], url_id, email['doi'], revision)
                # cur = db.cursor()
                # cur.execute(sql, email_url_tmp)
                # db.commit()
                pg_query(db, 'insert', sql, email_url_tmp)
                # error = cur.lastrowid

                url_base = 'http://18.116.73.233:5000'

                message_text = """\
                <html>
                    <body>
                        <p>Hello,<br/> Here is your unique URL to enter the submission path for \"""" + article['title'] + """\":<br/>
                        """ + url_base + """/enter/""" + url_id + """<br/>
                        Thank you in advance!<br/>
                        If you didn't request this email, please let us know at hugheylab.publishing.pipeline@gmail.com.</p>
                    </body>
                </html>
                """

                send_email(receiver_email = email['email'], message_text = message_text, subject = ('Submission Path Entry For DOI ' + article['doi']), db = db)

                # email_urls.append(email_url_tmp)
        if sentEmail == True:
            db.close()
            return redirect(url_for('thanks.thanks', thanks_type = 'registration'))
        else:
            error = 'No emails selected, please select at least one email to send url to.'






        flash(error)

    db.close()
    return render_template('auth/confirm.html', article_infos = article_infos, email_list = email_list, all_has_emails = all_has_emails)

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
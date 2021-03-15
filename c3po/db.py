import psycopg2
from psycopg2.extras import DictCursor
from configparser import ConfigParser
from google.cloud import bigquery

import click
from flask import current_app, g
from flask.cli import with_appcontext
import time
from datetime import datetime


def get_db():
    if 'db' not in g:
        params = config()
        g.db = psycopg2.connect(**params)

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db(schema_file):
    db = get_db()
    cur = db.cursor()

    with current_app.open_resource(schema_file) as f:
        cur.execute(f.read().decode('utf8'))
        db.commit()

def get_pg_authors_and_emails():
    db = get_db()
    cur = db.cursor()

    # Perform a query.
    query = (
        "select CONCAT(author.fore_name, ' ', author.last_name) as author_name, article_id.id_value as doi, ARRAY_TO_STRING((SELECT REGEXP_MATCHES(author_affiliation.affiliation, '([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\\.[a-zA-Z0-9_-]+)')), ',') as email, author_affiliation.affiliation as affiliation "
        "from author_affiliation as author_affiliation "
        "left join author as author on "
        "author_affiliation.pmid = author.pmid and author_affiliation.author_pos = author.author_pos "
        "left join article_id as article_id on author_affiliation.pmid = article_id.pmid "
        "where article_id.id_type = 'doi';")
    bqStart = time.time()
    cur.execute(query)
    rows = cur.fetchall()
    bqEnd = time.time()
    queryA = 'INSERT INTO author_doi(author_name, author_affiliation, doi) VALUES(%s,%s,%s)'
    queryE = 'INSERT INTO email_doi(email, doi) VALUES(%s,%s)'
    cur = db.cursor()
    cur.execute('INSERT INTO timings(query, start_time, stop_time, seconds) VALUES(%s,%s,%s,%s)', ('bigquery get authors and emails', str(datetime.fromtimestamp(bqStart)), str(datetime.fromtimestamp(bqEnd)), (bqEnd - bqStart)))
    emailDoiList = []
    i = 0
    iAuth = 0
    iStart = time.time()
    for row in rows:
        if row['author_name'] != None and row['author_name'] != '':
            authName = row['author_name']
        else:
            authName = 'Unknown Author'
        iAuth = iAuth + 1
        cur.execute(queryA, (authName, row['affiliation'], row['doi'],))
        if row['email'] != None and row['email'] != '' and row['email'] != '}':
            if ',' in row['email']:
                for email in row['email'].split(','):
                    emDoi = email + row['doi']
                    if emDoi not in emailDoiList:
                        cur.execute(queryE, (email, row['doi'],))
                        emailDoiList.append(emDoi)
                        i = i + 1
            else:
                emDoi = row['email'] + row['doi']
                if emDoi not in emailDoiList:
                    cur.execute(queryE, (row['email'], row['doi'],))
                    emailDoiList.append(emDoi)
                    i = i + 1
        if i >= 100:
            iEnd = time.time()
            cur.execute('INSERT INTO timings(query, start_time, stop_time, seconds) VALUES(%s,%s,%s,%s)', ('save ' + str(iAuth) + ' authors and ' + str(i) + ' emails', str(datetime.fromtimestamp(iStart)), str(datetime.fromtimestamp(iEnd)), (iEnd - iStart)))
            db.commit()
            db = get_db()
            cur = db.cursor()
            i = 0
            iAuth = 0
            iStart = time.time()

    db.commit()

def get_pg_article_info():
    db = get_db()
    cur = db.cursor()
    # Perform a query.
    query = (
        'insert into article_info(pmid, title, journal_name, doi, pub_date) (select article.pmid as pmid, article.title as title, journal.journal_name as journal_name, article_id.id_value as doi, article.pub_date as pub_date '
        'from article as article '
        'left join article_id as article_id '
        'on article.pmid = article_id.pmid '
        'left join journal as journal '
        'on article.pmid = journal.pmid '
        'left join author as author on '
        'article.pmid = author.pmid '
        'where article_id.id_type = "doi");')
    cur.execute(query)  # Query

    db.commit()

def get_journals():
    # Perform a query.
    db = get_db()
    cur = db.cursor()
    query = 'DROP TABLE journal_name;'
    cur.execute(query,)
    query = 'CREATE TABLE journal_name AS SELECT DISTINCT(journal_name) AS journal_name FROM article_info;'
    cur.execute(query,)
    db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db('schema.sql')
    click.echo('Initialized the database.')

@click.command('init-db-postgres')
@with_appcontext
def init_db_postgres_command():
    """Clear the existing data and create new tables."""
    init_db('schema.sql')
    # get_pg_authors_and_emails()
    get_pg_article_info()
    get_journals()
    click.echo('Initialized the database.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(init_db_postgres_command)

def config(filename='c3po/database.ini', section='postgresql'):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db
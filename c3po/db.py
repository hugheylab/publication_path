import sqlite3
from google.cloud import bigquery

import click
from flask import current_app, g
from flask.cli import with_appcontext
import time


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db(schema_file):
    db = get_db()

    with current_app.open_resource(schema_file) as f:
        db.executescript(f.read().decode('utf8'))

def get_bq_authors_and_emails():
    client = bigquery.Client()

    # Perform a query.
    query = (
        'select CONCAT(author.fore_name, " ", author.last_name) as author_name, article_id.id_value as doi, ARRAY_TO_STRING(REGEXP_EXTRACT_ALL(author_affiliation.affiliation, r"([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\\.[a-zA-Z0-9_-]+)"), ",") as email, author_affiliation.affiliation as affiliation '
        'from pmdb-bq.pmdb.author_affiliation as author_affiliation '
        'left join pmdb-bq.pmdb.author as author on '
        'author_affiliation.pmid = author.pmid and author_affiliation.author_pos = author.author_pos '
        'left join pmdb-bq.pmdb.article_id as article_id on author_affiliation.pmid = article_id.pmid '
        'where article_id.id_type = "doi";')
    bqStart = time.time()
    query_job = client.query(query)  # API request
    rows = query_job.result()  # Waits for query to finish
    bqEnd = time.time()
    queryA = 'INSERT INTO author_doi(author_name, author_affiliation, doi) VALUES(?,?,?)'
    queryE = 'INSERT INTO email_doi(email, doi) VALUES(?,?)'
    db = get_db()
    cur = db.cursor()
    cur.execute('INSERT INTO timings(query, start_time, stop_time, seconds) VALUES(?,?,?,?)', ('bigquery get authors and emails', str(bqStart), str(bqEnd), str(bqEnd - bqStart)))
    emailDoiList = []
    for row in rows:
        cur.execute(queryA, (row.author_name, row.affiliation, row.doi,))
        if row.email != None and row.email != '' and row.email != '}':
            if ',' in row.email:
                for email in row.email.split(','):
                    emDoi = email + row.doi
                    if emDoi not in emailDoiList:
                        cur.execute(queryE, (email, row.doi,))
                        emailDoiList.append(emDoi)
            else:
                emDoi = row.email + row.doi
                if emDoi not in emailDoiList:
                    cur.execute(queryE, (row.email, row.doi,))
                    emailDoiList.append(emDoi)

    db.commit()

def get_bq_article_info():
    client = bigquery.Client()

    # Perform a query.
    query = (
        'select article.pmid as pmid, article.title as title, journal.journal_name as journal_name, article_id.id_value as doi, article.pub_date as pub_date '
        'from pmdb-bq.pmdb.article as article '
        'left join pmdb-bq.pmdb.article_id as article_id '
        'on article.pmid = article_id.pmid '
        'left join pmdb-bq.pmdb.journal as journal '
        'on article.pmid = journal.pmid '
        'left join pmdb-bq.pmdb.author as author on '
        'article.pmid = author.pmid '
        'where article_id.id_type = "doi";')
    query_job = client.query(query)  # API request
    rows = query_job.result()  # Waits for query to finish
    # TODO: Figure out why my insert statement is treating the inputs as out of order (see the journal_name and doi variables and values....?)
    query2 = 'INSERT INTO article_info(pmid, title, journal_name, doi, pub_date) VALUES(?,?,?,?,?)'
    db = get_db()
    cur = db.cursor()
    for row in rows:
        cur.execute(query2, (row.pmid, row.title, row.journal_name, row.doi, row.pub_date))

    db.commit()

def get_journals():
    # Perform a query.
    db = get_db()
    cur = db.cursor()
    query = 'DROP TABLE journal;'
    cur.execute(query,)
    query = 'CREATE TABLE journal AS SELECT DISTINCT(journal_name) AS journal_name FROM article_info;'
    cur.execute(query,)
    db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db('schema.sql')
    click.echo('Initialized the database.')

@click.command('init-db-bigquery')
@with_appcontext
def init_db_bigquery_command():
    """Clear the existing data and create new tables."""
    init_db('schema.sql')
    get_bq_authors_and_emails()
    get_bq_article_info()
    get_journals()
    click.echo('Initialized the database.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(init_db_bigquery_command)
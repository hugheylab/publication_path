import psycopg2
from psycopg2.extras import DictCursor
from configparser import ConfigParser

import click
from flask import current_app, g
from flask.cli import with_appcontext
import time
from datetime import datetime


def get_db():
    if 'db' not in g:
        params = config()
        g.db = psycopg2.connect(**params,
                              cursor_factory=DictCursor)

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
        "INSERT INTO author_doi(author_name, author_affiliation, doi) (select CONCAT(author.fore_name, ' ', author.last_name) as author_name, author_affiliation.affiliation as author_affiliation, article_id.id_value as doi "
        "from author_affiliation as author_affiliation "
        "left join author as author on "
        "author_affiliation.pmid = author.pmid and author_affiliation.author_pos = author.author_pos "
        "left join article_id as article_id on author_affiliation.pmid = article_id.pmid "
        "where article_id.id_type = 'doi');")
    authStart = time.time()
    cur.execute(query)
    authEnd = time.time()
    db.commit()
    cur.execute('INSERT INTO timings(query, start_time, stop_time, seconds) VALUES(%s,%s,%s,%s);', ('author_doi insert by query', str(datetime.fromtimestamp(authStart)), str(datetime.fromtimestamp(authEnd)), (authEnd - authStart)))
    db.commit()
    
    query = (
        "INSERT INTO email_doi(doi, email) (select article_id.id_value as doi, unnest(regexp_matches(author_affiliation.affiliation, '([a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z0-9_-]+)', 'g')) as email "
        "from author_affiliation as author_affiliation "
        "left join article_id as article_id on author_affiliation.pmid = article_id.pmid "
        "where article_id.id_type = 'doi');")
    emStart = time.time()
    cur.execute(query)
    emEnd = time.time()
    db.commit()
    cur = db.cursor()
    cur.execute('INSERT INTO timings(query, start_time, stop_time, seconds) VALUES(%s,%s,%s,%s);', ('email_doi insert by query', str(datetime.fromtimestamp(emStart)), str(datetime.fromtimestamp(emEnd)), (emEnd - emStart)))
    

    db.commit()

def get_pg_article_info():
    db = get_db()
    cur = db.cursor()
    # Perform a query.
    query = (
        "insert into article_info(pmid, title, journal_name, doi, pub_date) (select article.pmid as pmid, article.title as title, journal.journal_name as journal_name, article_id.id_value as doi, article.pub_date as pub_date "
        "from article as article "
        "left join article_id as article_id "
        "on article.pmid = article_id.pmid "
        "left join journal as journal "
        "on article.pmid = journal.pmid "
        "where article_id.id_type = 'doi');")
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
    get_pg_authors_and_emails()
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
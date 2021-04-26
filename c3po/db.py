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
        "INSERT INTO author_doi(author_pos, author_name, affiliation_pos, author_affiliation, doi) (select author.author_pos as author_pos, CONCAT(author.fore_name, ' ', author.last_name) as author_name, author_affiliation.affiliation_pos as affiliation_pos, author_affiliation.affiliation as author_affiliation, article_id.id_value as doi "
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
        "INSERT INTO email_doi(doi, email, source) (select article_id.id_value as doi, unnest(regexp_matches(author_affiliation.affiliation, '([a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z0-9_-]+)', 'g')) as email, 'pmdb' as source "
        "from author_affiliation as author_affiliation "
        "left join article_id as article_id on author_affiliation.pmid = article_id.pmid "
        "where article_id.id_type = 'doi');")
    query2 = (
        "with email_rank AS "
        "(SELECT id, "
        "RANK () OVER ( "
        "PARTITION BY email, doi "
        "ORDER BY  id DESC NULLS LAST "
        ") rank_number  "
        "FROM email_doi ) "
        "delete from email_doi where id in (select id from email_rank where rank_number > 1);")
    emStart = time.time()
    cur.execute(query)
    cur.execute(query2)
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
        "with article_tmp as "
        "(select article.pmid as pmid, article.title as title, journal.journal_name as journal_name, article_id.id_value as doi, pub_history.pub_date as pub_date  "
        "from article as article  "
        "left join pub_history as pub_history  "
        "on article.pmid = pub_history.pmid  "
        "left join article_id as article_id  "
        "on article.pmid = article_id.pmid  "
        "left join journal as journal  "
        "on article.pmid = journal.pmid  "
        "where article_id.id_type = 'doi' and article_id.id_value != '' and article_id.id_value != ' ' and article_id.id_value IS NOT NULL and pub_history.pub_status = 'pubmed') "
        ", article_rank AS "
        "( "
            "SELECT "
            "*, "
            "RANK () OVER (  "
                "PARTITION BY doi "
                "ORDER BY  pub_date DESC NULLS LAST, pmid DESC NULLS LAST "
            ") rank_number  "
        "FROM "
            "article_tmp "
        ") "
        "insert into article_info(pmid, title, journal_name, doi, pub_date) (SELECT  "
            "pmid, title, journal_name, doi, pub_date "
        "FROM article_rank "
        "WHERE rank_number = 1);")
    cur.execute(query)  # Query

    query2 = (
        "insert into doi_child_tables(doi, email_ids, author_ids) "
	    "(select article_info.doi, "
	 	"array_remove(array_agg(distinct(email_doi.id)), NULL) as email_ids, "
	    "array_agg(distinct(author_doi.id)) as author_ids "
	    "from article_info "
	    "left join email_doi on article_info.doi = email_doi.doi "
	    "left join author_doi on article_info.doi = author_doi.doi "
	    "group by article_info.doi);")
    cur.execute(query2)  # Query

    query3 = (
        "insert into email_doi_tables(email, dois) "
	    "(select email, "
	 	"array_agg(doi) as dois "
	    "from email_doi "
	    "group by email);")
    cur.execute(query3)  # Query

    query4 = (
        "insert into pmid_doi(pmid, doi) "
	    "(select pmid, "
	 	"max(id_value) as doi "
	    "from article_id "
	    "where id_type = 'doi' "
		"group by pmid);")
    cur.execute(query4)  # Query

    db.commit()
    cur.close()

def get_journals():
    # Perform a query.
    db = get_db()
    cur = db.cursor()
    query = 'DROP TABLE journal_name;'
    cur.execute(query,)
    query = 'CREATE TABLE journal_name AS SELECT DISTINCT(journal_name) AS journal_name FROM article_info;'
    cur.execute(query,)
    db.commit()

def add_email(email, doi):
    db = get_db()

    # Perform a query.
    pg_query(db, 'insert', 'INSERT INTO email_doi(doi, email, automated) values(%s, %s, FALSE)',(doi, email))
    pg_query(db, 'delete', 'DELETE FROM doi_child_tables where doi = %s ', (doi,))
    pg_query(db, 'delete', 'DELETE FROM email_doi_tables where email = %s ', (email,))

    query2 = (
        "insert into doi_child_tables(doi, email_ids, author_ids) "
	    "(select article_info.doi, "
	 	"array_remove(array_agg(distinct(email_doi.id)), NULL) as email_ids, "
	    "array_agg(distinct(author_doi.id)) as author_ids "
	    "from article_info "
	    "left join email_doi on article_info.doi = email_doi.doi "
	    "left join author_doi on article_info.doi = author_doi.doi "
        "where article_info.doi = %s "
	    "group by article_info.doi);")
    pg_query(db, 'insert', query2, (doi,))

    query3 = (
        "insert into email_doi_tables(email, dois) "
	    "(select email, "
	 	"array_agg(doi) as dois "
	    "from email_doi "
	    "where email = %s "
	    "group by email);")
    pg_query(db, 'insert', query3, (email,))

    db.commit()
    db.close()


def pg_query(db = None, qType = 'fetchone', query = '', arguments = None, commit = True, closeDb = False):
    if db is None :
        db = get_db()
        closeDb = True
    cur = db.cursor()
    cur.execute(query, arguments)
    if qType == 'fetchone':
        retVal = cur.fetchone()
    elif qType == 'fetchall':
        retVal = cur.fetchall()
    else:
        if commit:
            db.commit()
        retVal = 'Executed'

    cur.close()
    if closeDb:
        db.close()
    return retVal


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db('schema.sql')
    click.echo('Initialized the database.')

@click.command('add-email')
@click.argument('email')
@click.argument('doi')
@with_appcontext
def add_email_command(email, doi):
    """Add email to specific doi."""
    add_email(email, doi)
    click.echo('Added email.')

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
    app.cli.add_command(add_email_command)

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
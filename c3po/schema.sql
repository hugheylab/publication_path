DROP TABLE IF EXISTS author_doi;
DROP TABLE IF EXISTS article_info;
DROP TABLE IF EXISTS journal_name;
DROP TABLE IF EXISTS timings;
DROP TABLE IF EXISTS post;
DROP TABLE IF EXISTS doi_child_tables;
DROP TABLE IF EXISTS email_doi_tables;
DROP TABLE IF EXISTS pmid_doi;
DROP TABLE IF EXISTS pmdb_email;



CREATE TABLE IF NOT EXISTS email_address (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  password TEXT NOT NULL,
  active BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS accept_email (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE author_doi (
  id SERIAL PRIMARY KEY,
  author_pos INTEGER,
  author_name TEXT NOT NULL,
  affiliation_pos INTEGER,
  author_affiliation TEXT,
  doi TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_doi (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  automated BOOLEAN DEFAULT TRUE NOT NULL,
  doi TEXT NOT NULL,
  source TEXT NOT NULL
);

DELETE FROM email_doi WHERE source IS NULL OR source = 'pmdb';

CREATE TABLE article_info (
  id SERIAL,
  pmid TEXT NOT NULL,
  title TEXT NOT NULL,
  journal_name TEXT NOT NULL,
  doi TEXT PRIMARY KEY,
  pub_date DATE
);

CREATE TABLE doi_child_tables (
  doi TEXT PRIMARY KEY,
  email_ids INTEGER[],
  author_ids INTEGER[]
);

CREATE TABLE email_doi_tables (
  email TEXT PRIMARY KEY,
  dois TEXT[]
);

CREATE TABLE pmid_doi (
  pmid INTEGER PRIMARY KEY,
  doi TEXT
);

CREATE TABLE If NOT EXISTS email_url (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  url_param_id TEXT UNIQUE NOT NULL,
  doi TEXT NOT NULL,
  revision INTEGER NOT NULL,
  completed_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_path (
  id SERIAL PRIMARY KEY,
  step INTEGER NOT NULL,
  submission_date DATE,
  journal TEXT NOT NULL,
  url_param_id TEXT NOT NULL,
  FOREIGN KEY (url_param_id) REFERENCES email_url (url_param_id)
);

CREATE TABLE journal_name (
  id SERIAL PRIMARY KEY,
  journal_name TEXT NOT NULL
);

CREATE TABLE timings (
  id SERIAL PRIMARY KEY,
  query TEXT NOT NULL,
  start_time TIMESTAMP,
  stop_time TIMESTAMP,
  seconds INTEGER
);

CREATE TABLE IF NOT EXISTS pmc_email (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  pmc TEXT NOT NULL,
  doi TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pmdb_email (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  pmid TEXT NOT NULL,
  doi TEXT NOT NULL
);
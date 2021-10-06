DROP TABLE IF EXISTS author_doi;
DROP TABLE IF EXISTS article_info;
DROP TABLE IF EXISTS journal_name;
DROP TABLE IF EXISTS timings;
DROP TABLE IF EXISTS post;
DROP TABLE IF EXISTS doi_child_tables;
DROP TABLE IF EXISTS author_doi_tables;
DROP TABLE IF EXISTS author_list;
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
  author_last_name TEXT,
  author_fore_name TEXT,
  collective BOOLEAN NOT NULL,
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

CREATE TABLE author_doi_tables (
  author_last_name TEXT,
  author_fore_name TEXT,
  author_name TEXT,
  dois TEXT[]
);

CREATE INDEX author_index ON author_doi_tables (author_last_name, author_fore_name);

CREATE TABLE author_list (
  author_last_name TEXT,
  author_fore_name TEXT,
  author_name TEXT
);

CREATE INDEX author_index2 ON author_list (author_last_name, author_fore_name);

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
  author_id INTEGER,
  author_name TEXT,
  completed_timestamp TIMESTAMP
);

CREATE TABLE If NOT EXISTS path_entry_event (
  id SERIAL PRIMARY KEY,
  user_orcid TEXT NOT NULL,
  doi TEXT NOT NULL,
  event_version INTEGER NOT NULL,
  author_id INTEGER,
  author_name TEXT,
  completed_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_path (
  id SERIAL PRIMARY KEY,
  step INTEGER NOT NULL,
  submission_date DATE,
  journal TEXT NOT NULL,
  peer_review TEXT,
  times_submitted TEXT,
  path_entry_event INTEGER NOT NULL,
  FOREIGN KEY (path_entry_event) REFERENCES path_entry_event (id)
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

CREATE TABLE IF NOT EXISTS user_orcid (
  orcid_id TEXT PRIMARY KEY,
  orcid_access_token TEXT NOT NULL,
  orcid_refresh_token TEXT NOT NULL,
  orcid_name TEXT NOT NULL,
  orcid_scope TEXT,
  initialized BOOLEAN DEFAULT FALSE,
  raw_text TEXT,
  full_name TEXT,
  email TEXT,
  birthday DATE,
  gender TEXT,
  ethnicity TEXT,
  career_stage TEXT,
  highest_education TEXT,
  current_institution TEXT,
  previous_institutions TEXT[]
);

CREATE TABLE IF NOT EXISTS orcid_keys (
  key_type TEXT,
  client_id TEXT,
  client_secret TEXT,
  read_public_key TEXT
);

CREATE TABLE IF NOT EXISTS user_papers (
  orcid_id TEXT PRIMARY KEY,
  dois TEXT[]
);
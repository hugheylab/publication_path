import functools
import json
from json import JSONEncoder
import datetime
from datetime import datetime
from datetime import date
import psycopg2
from psycopg2.extras import DictCursor
import sys


from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import (
    get_db, pg_query, close_db
)

from c3po.auth import author_affiliations

bp = Blueprint('enter', __name__, url_prefix='/enter')

@bp.route('path/<doi>', methods=('GET', 'POST'))
def path(doi):
    close_db()
    doi = doi.replace('%2F', '/')
    print(doi)

    db = get_db()

    allow_enter = True
    link_author_sel = ''
    error = ''
    # cur.execute(
    #     'SELECT * FROM email_url WHERE url_param_id = %s', (url_id,)
    # )
    # email_url = cur.fetchone()

    # cur.execute(
    #     'SELECT * from paper_path WHERE url_param_id = (SELECT url_param_id from email_url WHERE completed_timestamp IS NOT NULL and doi = %s ORDER BY completed_timestamp DESC LIMIT 1) ORDER BY step ASC;', (email_url['doi'],)
    # )
    # completed_paths = cur.fetchall()
    sql_completed_paths = '''SELECT * from paper_path WHERE 
        path_entry_event = (SELECT id from path_entry_event WHERE 
            doi = %s and 
            user_orcid = %s 
            ORDER BY event_version DESC LIMIT 1) 
        ORDER BY step ASC;'''
    completed_paths = pg_query(db, 'fetchall', sql_completed_paths, (doi, g.user['orcid_id']))
    

    sql_saved_event = '''SELECT id from path_entry_event WHERE 
        doi = %s and 
        user_orcid = %s and
        completed = False
        ORDER BY event_version DESC LIMIT 1;'''
    saved_event = pg_query(db, 'fetchone', sql_saved_event, (doi, g.user['orcid_id']))
    has_saved = False
    if saved_event is not None:
        has_saved = True
    sql_completed_event = '''SELECT id from path_entry_event WHERE 
        doi = %s and 
        user_orcid = %s and
        completed = True
        ORDER BY event_version DESC LIMIT 1;'''
    completed_event = pg_query(db, 'fetchone', sql_completed_event, (doi, g.user['orcid_id']))
    has_completed = False
    if completed_event is not None:
        has_completed = True

    # cur.execute(
    #     'SELECT * FROM author_doi WHERE doi = %s', (email_url['doi'],)
    # )
    # author_doi = cur.fetchall()
    doi_child = pg_query(db, 'fetchone', 'SELECT * FROM doi_child_tables WHERE doi = %s', (doi,))
    print(doi_child)
    auth_ids = str(doi_child['author_ids']).replace('[', '(').replace(']', ')')
    authors = pg_query(db, 'fetchall', 'SELECT * FROM author_doi WHERE id IN ' + auth_ids + ' ORDER BY author_pos ASC NULLS LAST, affiliation_pos ASC ', ())
        
    auth_aff_list = []
    affiliation_list = []
    for author in authors:
        if author['author_affiliation'] in affiliation_list:
            aff_num = affiliation_list.index(author['author_affiliation']) + 1
        else:
            affiliation_list.append(author['author_affiliation'])
            aff_num = len(affiliation_list)
        if len(auth_aff_list) > 0 and auth_aff_list[len(auth_aff_list) - 1].author['author_pos'] == author['author_pos']:
            auth_aff_list[len(auth_aff_list) - 1].affiliation_nums.append(aff_num)
        else:
            auth_aff = author_affiliations(author, [aff_num])
            auth_aff_list.append(auth_aff)

    # cur.execute(
    #     'SELECT * FROM article_info WHERE doi = %s', (email_url["doi"],)
    # )
    # article_info = cur.fetchone()
    article_info = pg_query(db, 'fetchone', 'SELECT * FROM article_info WHERE doi = %s', (doi,))

    # cur.execute(
    #     'SELECT * FROM journal_name', ()
    # )
    # journal_opts = cur.fetchall()
    journal_opts = pg_query(db, 'fetchall', 'SELECT * FROM journal_name ORDER BY journal_name ASC', ())
    
    confirm = False
    show_error = False
    

    if request.method == 'GET' and allow_enter == True:
        if completed_paths is not None and len(completed_paths) > 0:
            path_list_tmp = []
            sql_prev_path_entry_event = '''SELECT * FROM path_entry_event WHERE id = %s;'''
            prev_path_entry_event = pg_query(db, 'fetchone', sql_prev_path_entry_event, (completed_paths[0]['path_entry_event'],))
            link_author_sel = prev_path_entry_event['author_id']
            for completed_path in completed_paths:
                path_list_tmp.append(paper_path(
                    idx = completed_path['step'] - 1,
                    paper_path_id = completed_path['id'],
                    path_entry_event = (None if prev_path_entry_event['completed'] == True else prev_path_entry_event['id']),
                    step = completed_path['step'],
                    journal = completed_path['journal'],
                    peer_review = completed_path['peer_review'],
                    times_submitted = completed_path['times_submitted'],
                    submit_date = completed_path['submission_date'],
                    error = '',
                    show_error = False).__dict__)
        else:
            path_list_tmp = [paper_path(idx = 0, paper_path_id = None, path_entry_event = None, step = 1, journal = '', peer_review = '', times_submitted = '', submit_date = '', error = '', show_error = False).__dict__]
            path_list_tmp.append(paper_path(idx = 1, paper_path_id = None, path_entry_event = None, step = 2, journal = article_info["journal_name"], peer_review = 'Yes', times_submitted = '', submit_date = '', error = '', show_error = False).__dict__)
        session["path_list"] = path_list_tmp

    elif request.method == 'POST' and allow_enter == True:
        error = None
        print(request.form)
        print(request.form.getlist('journal'))

        link_author_sel = request.form.get('link_author_sel')
        idxs = request.form.getlist('idx')
        path_item_ids = request.form.getlist('paper_path_id')
        steps = request.form.getlist('step')
        journals = request.form.getlist('journal')
        submit_dates = request.form.getlist('submit_date')
        peer_reviews = []
        times_submitteds = []
        for step in steps:
            peer_reviews.append(request.form.get('peer_review' + step))
            times_submitteds.append(request.form.get('times_submitted' + step))
        del_item = request.form.getlist('del_item')
        last = len(idxs) - 1

        path_list_tmp = []
        isDel = False
        delMod = 0
        addMod = 0
        prior_date = ''
        max_date = article_info['pub_date']
        prev_journal = ''
        is_submit = ('submit' in request.form)
        has_error = False
        up_idx = None
        down_idx = None
        for i in range(0, last + 1):
            del_item_name = 'del_item'+str(steps[i])
            add_item_name = 'add_item'+str(steps[i])
            up_item_name = 'up_item'+str(steps[i])
            down_item_name = 'down_item'+str(steps[i])
            if not (del_item_name in request.form):
                if up_item_name in request.form:
                    up_idx = i
                if down_item_name in request.form:
                    down_idx = i
                if add_item_name in request.form:
                    path_list_tmp.append(paper_path(i + delMod + addMod, None, None, (i + 1) + delMod + addMod, '', '', '', '', '', is_submit).__dict__)
                    addMod = addMod + 1
                path_item_tmp = paper_path(i + delMod + addMod, path_item_ids[i], None, (i + 1) + delMod + addMod, journals[i], peer_reviews[i], times_submitteds[i], submit_dates[i], '', is_submit)
                path_item_tmp.validate(prior_date, max_date, prev_journal)
                prev_journal = path_item_tmp.journal
                if not path_item_tmp.error == '':
                    has_error = True
                
                if not 'Submission date' in path_item_tmp.error and path_item_tmp.submit_date is not None and path_item_tmp.submit_date != '':
                    prior_date = path_item_tmp.submit_date
                path_list_tmp.append(path_item_tmp.__dict__)

            else:
                delMod = delMod - 1
        if up_idx != None:
            print(up_idx)
            up_path_tmp = path_list_tmp.pop(up_idx)
            up_path_tmp["step"] = up_path_tmp["step"] - 1
            up_path_tmp["idx"] = up_path_tmp["idx"] - 1
            prev_path_tmp = path_list_tmp.pop(up_idx - 1)
            prev_path_tmp["step"] = prev_path_tmp["step"] + 1
            prev_path_tmp["idx"] = prev_path_tmp["idx"] + 1
            path_list_tmp.insert(up_idx - 1, up_path_tmp)
            path_list_tmp.insert(up_idx, prev_path_tmp)
        if down_idx != None:
            print(down_idx)
            next_path_tmp = path_list_tmp.pop(down_idx + 1)
            next_path_tmp["step"] = next_path_tmp["step"] - 1
            next_path_tmp["idx"] = next_path_tmp["idx"] - 1
            down_path_tmp = path_list_tmp.pop(down_idx)
            down_path_tmp["step"] = down_path_tmp["step"] + 1
            down_path_tmp["idx"] = down_path_tmp["idx"] + 1
            path_list_tmp.insert(down_idx, next_path_tmp)
            path_list_tmp.insert(down_idx + 1, down_path_tmp)
        print(path_list_tmp)

        if 'add_item' in request.form:
            final_path = path_list_tmp.pop(len(path_list_tmp) - 1)
            if last == 0:
                path_list_tmp = [paper_path(idx = 0, paper_path_id = None, path_entry_event = None, step = 1, journal = '', peer_review = '', times_submitted = '', submit_date = '', error = '', show_error = False).__dict__]
            else:
                newIdx = int(idxs[last])
                newStep = int(steps[last])
                path_list_tmp.append(paper_path(newIdx, path_item_ids[i], None, newStep, journal = '', peer_review = '', times_submitted = '', submit_date = '', error = '', show_error = False).__dict__)
            final_path["idx"] = final_path["idx"] + 1
            final_path["step"] = final_path["step"] + 1
            path_list_tmp.append(final_path)
        elif 'submit' in request.form:
            error = ''
            if link_author_sel is None or link_author_sel == '':
                show_error = True
                has_error = True
                error = 'No author selected. '
            if last == -1:
                error = error + 'You must have at least one item before submitting.'
            elif has_error == True:
                error = error + 'Errors in form, please review and fix issues.'
            else:
                confirm = True
        elif 'save_progress' in request.form:
            author_id = link_author_sel
            savePathEvent(db, author_id, g.user, doi, path_list_tmp, confirm = False)
            db.close()
            return redirect(url_for('home.orcid'))
        elif 'confirm' in request.form:
            author_id = link_author_sel
            savePathEvent(db, author_id, g.user, doi, path_list_tmp, confirm = True)
            db.close()
            return redirect(url_for('thanks.thanks', thanks_type = 'submission'))

        if error != None:
            flash(error)

        session["path_list"] = path_list_tmp
    elif allow_enter == False:
        cur = db.cursor()
        cur.execute(
            'SELECT * FROM paper_path WHERE url_param_id = %s', (url_id,)
        )
        path_list_entered = cur.fetchall()
        cur.close()
        path_list_tmp = []
        for path_list_item in path_list_entered:
            path_list_tmp.append(paper_path(idx = (path_list_item['step'] - 1), url_param_id = url_id, step = path_list_item['step'], journal = path_list_item['journal'], times_submitted = path_list_item['times_submitted'], submit_date = path_list_item['submission_date'], error = '', show_error = False).__dict__)

    
    db.close()

    return render_template('enter/path.html', doi=doi, journal_opts = journal_opts, article_info = article_info, author_doi = auth_aff_list, affiliation_list = affiliation_list, confirm = confirm, allow_enter = allow_enter, completed_paths = completed_paths, has_completed = has_completed, has_saved = has_saved, link_author_sel = link_author_sel, error = error, show_error = show_error)

def savePathEvent(db, author_id, session_user, doi, path_list_tmp, confirm):
    print(author_id)
    author_sel = pg_query(db, 'fetchall', 'SELECT * FROM author_doi WHERE id = %s;', (author_id,))
    sql_prev_path_entry_event = '''SELECT * FROM path_entry_event WHERE 
        doi = %s AND user_orcid = %s 
        ORDER BY event_version DESC;'''
    prev_path_entry_event = pg_query(db, 'fetchone', sql_prev_path_entry_event, (doi, session_user['orcid_id']))
    if prev_path_entry_event is not None:
        print('Found previous path for session_user ' + session_user['orcid_id'] + ' on doi ' + doi + ' as ' + str(prev_path_entry_event))
    else:
        print('Found no previous path for session_user ' + session_user['orcid_id'] + ' on doi ' + doi)
    event_version = 1
    print('event_version defaulted')
    update = False
    if prev_path_entry_event is not None and prev_path_entry_event['event_version'] is not None:
        if prev_path_entry_event['completed'] == True:
            event_version = prev_path_entry_event['event_version'] + 1
        else:
            event_version = prev_path_entry_event['event_version']
            update = True
    if confirm:
        cur = db.cursor()
        sql = ''' INSERT INTO path_entry_event(user_orcid,doi,event_version,author_id,author_name,completed_timestamp,completed)
            VALUES (%s, %s, %s, %s, %s, %s, %s); '''
        vals = (session_user['orcid_id'], doi, event_version, author_id, '', datetime.now(), True)
        if update:
            sql = ''' UPDATE path_entry_event SET (user_orcid,doi,event_version,author_id,author_name,completed_timestamp,completed) =
                 (%s, %s, %s, %s, %s, %s, %s) 
                WHERE id = %s; '''
            vals = (session_user['orcid_id'], doi, event_version, author_id, '', datetime.now(), True, prev_path_entry_event['id'])
        cur.execute(sql, vals)
    else:
        cur = db.cursor()
        sql = ''' INSERT INTO path_entry_event(user_orcid,doi,event_version,author_id,author_name,completed)
            VALUES (%s, %s, %s, %s, %s, %s); '''
        vals = (session_user['orcid_id'], doi, event_version, author_id, '', False)
        if update:
            sql = ''' UPDATE path_entry_event SET (user_orcid,doi,event_version,author_id,author_name,completed) =
                (%s, %s, %s, %s, %s, %s) 
                WHERE id = %s; '''
            vals = (session_user['orcid_id'], doi, event_version, author_id, '', False, prev_path_entry_event['id'])
        cur.execute(sql, vals)
    db.commit()
    paper_path_entry = pg_query(db, 'fetchone', 'SELECT * FROM path_entry_event WHERE user_orcid = %s AND doi = %s ORDER BY event_version DESC LIMIT 1', (session_user['orcid_id'], doi))
    print(paper_path_entry)
    paper_path_entry_id = paper_path_entry['id']
    for path_item in path_list_tmp:
        sql = ''' INSERT INTO paper_path(step,submission_date,journal,peer_review,times_submitted,path_entry_event)
            VALUES(%s,%s,%s,%s,%s,%s) '''
        path_vals = (path_item["step"], path_item["submit_date"], path_item["journal"], path_item["peer_review"], path_item["times_submitted"], paper_path_entry_id)
        if path_item["paper_path_id"] is not None and path_item["paper_path_id"] != '':
            sql = ''' UPDATE paper_path SET (step,submission_date,journal,peer_review,times_submitted,path_entry_event) =
                (%s,%s,%s,%s,%s,%s) 
                WHERE id = %s;'''
            path_vals = (path_item["step"], path_item["submit_date"], path_item["journal"], path_item["peer_review"], path_item["times_submitted"], paper_path_entry_id, path_item["paper_path_id"])
        cur = db.cursor()
        if path_item["submit_date"] == '':
            sql = ''' INSERT INTO paper_path(step,journal,peer_review,times_submitted,path_entry_event)
                VALUES(%s,%s,%s,%s,%s) '''
            path_vals = (path_item["step"], path_item["journal"], path_item["peer_review"], path_item["times_submitted"], paper_path_entry_id)
            if path_item["paper_path_id"] is not None and path_item["paper_path_id"] != '':
                sql = ''' UPDATE paper_path SET (step,journal,peer_review,times_submitted,path_entry_event) =
                    (%s,%s,%s,%s,%s) 
                WHERE id = %s;'''
                path_vals = (path_item["step"], path_item["journal"], path_item["peer_review"], path_item["times_submitted"], paper_path_entry_id, path_item["paper_path_id"])
        cur.execute(sql, path_vals)
        db.commit()
        cur.close()

class paper_path:
    def __init__(self, idx, paper_path_id, path_entry_event, step, journal, peer_review, times_submitted, submit_date, error, show_error):
        self.idx = idx
        self.paper_path_id = paper_path_id
        self.path_entry_event = path_entry_event
        self.step = step
        self.journal = journal
        self.peer_review = peer_review
        self.times_submitted = times_submitted
        self.submit_date = submit_date
        self.error = error
        self.show_error = show_error
        
    
    def validate(self, previous_date, max_date, previous_journal):
        self.error = ''
        if self.submit_date == '':
            # self.error = 'Submitt date cannot be empty. '
            self.error = ''
        else:
            if not previous_date == '':
                if '-' in self.submit_date:
                    s_date = datetime.strptime(self.submit_date, '%Y-%m-%d').date()
                else:
                    s_date = datetime.strptime(self.submit_date, '%m/%d/%Y').date()
                
                if '-' in previous_date:
                    p_date = datetime.strptime(previous_date, '%Y-%m-%d').date()
                else:
                    p_date = datetime.strptime(previous_date, '%m/%d/%Y').date()

                if p_date >= s_date:
                    self.error = self.error + 'Submission Date cannot be prior or equal to previous step date. '

            if (not max_date == '') and (not max_date == None):
                if '-' in self.submit_date:
                    s_date = datetime.strptime(self.submit_date, '%Y-%m-%d').date()
                else:
                    s_date = datetime.strptime(self.submit_date, '%m/%d/%Y').date()
                

                if s_date > max_date:
                    self.error = self.error + 'Submission Date cannot be after the publication date. '
        
        if self.journal == '':
            self.error = self.error + 'Journal cannot be empty. '
        elif self.journal == previous_journal:
            self.error = self.error + 'Journal cannot be equal to the previous journal. '
        if self.peer_review == '' or self.peer_review == None:
            self.error = self.error + 'Sent out for peer review cannot be empty. '
        if self.times_submitted == '' or self.times_submitted == None:
            self.error = self.error + 'Times submitted cannot be empty. '




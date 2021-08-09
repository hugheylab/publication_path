import functools
import json
from json import JSONEncoder
import datetime
from datetime import datetime
from datetime import date
import psycopg2
from psycopg2.extras import DictCursor


from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db
from c3po.db import pg_query
from c3po.auth import author_affiliations

bp = Blueprint('enter', __name__, url_prefix='/enter')

@bp.route('/<url_id>', methods=('GET', 'POST'))
def enter(url_id):

    db = get_db()

    allow_enter = True
    # cur.execute(
    #     'SELECT * FROM email_url WHERE url_param_id = %s', (url_id,)
    # )
    # email_url = cur.fetchone()
    email_url = pg_query(db, 'fetchone', 'SELECT * FROM email_url WHERE url_param_id = %s', (url_id,))
    print('email_url debug start')
    print(email_url)
    print(email_url['completed_timestamp'])
    print(email_url['completed_timestamp'] != '')
    print(email_url['completed_timestamp'] is not None)
    print('email_url debug end')

    if email_url['completed_timestamp'] is not None:
        error = 'Path already entered for this unique URL, please re-register if you wish to enter a new publication path!'
        allow_enter = False

    # cur.execute(
    #     'SELECT * from paper_path WHERE url_param_id = (SELECT url_param_id from email_url WHERE completed_timestamp IS NOT NULL and doi = %s ORDER BY completed_timestamp DESC LIMIT 1) ORDER BY step ASC;', (email_url['doi'],)
    # )
    # completed_paths = cur.fetchall()
    completed_paths = pg_query(db, 'fetchall', 'SELECT * from paper_path WHERE url_param_id = (SELECT url_param_id from email_url WHERE completed_timestamp IS NOT NULL and doi = %s ORDER BY completed_timestamp DESC LIMIT 1) ORDER BY step ASC;', (email_url['doi'],))
    

    # cur.execute(
    #     'SELECT * FROM author_doi WHERE doi = %s', (email_url['doi'],)
    # )
    # author_doi = cur.fetchall()
    doi_child = pg_query(db, 'fetchone', 'SELECT * FROM doi_child_tables WHERE doi = %s', (email_url["doi"],))
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
    article_info = pg_query(db, 'fetchone', 'SELECT * FROM article_info WHERE doi = %s', (email_url["doi"],))

    # cur.execute(
    #     'SELECT * FROM journal_name', ()
    # )
    # journal_opts = cur.fetchall()
    journal_opts = pg_query(db, 'fetchall', 'SELECT * FROM journal_name ORDER BY journal_name ASC', ())
    
    confirm = False
    


    if request.method == 'GET' and allow_enter == True:
        path_list_tmp = [paper_path(idx = 0, url_param_id = url_id, step = 1, journal = '', submit_date = '', error = '', show_error = False).__dict__]
        path_list_tmp.append(paper_path(idx = 1, url_param_id = url_id, step = 2, journal = article_info["journal_name"], submit_date = '', error = '', show_error = False).__dict__)
        session["path_list"] = path_list_tmp

    elif request.method == 'POST' and allow_enter == True:
        error = None
        print(request.form)
        print(request.form.getlist('journal'))

        idxs = request.form.getlist('idx')
        steps = request.form.getlist('step')
        journals = request.form.getlist('journal')
        submit_dates = request.form.getlist('submit_date')
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
                    path_list_tmp.append(paper_path(i + delMod + addMod, url_id, (i + 1) + delMod + addMod, '', '', '', is_submit).__dict__)
                    addMod = addMod + 1
                path_item_tmp = paper_path(i + delMod + addMod, url_id, (i + 1) + delMod + addMod, journals[i], submit_dates[i], '', is_submit)
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
                path_list_tmp = [paper_path(idx = 0, url_param_id = url_id, step = 1, journal = '', submit_date = '', error = '', show_error = False).__dict__]
            else:
                newIdx = int(idxs[last])
                newStep = int(steps[last])
                path_list_tmp.append(paper_path(newIdx, url_id, newStep, journal = '', submit_date = '', error = '', show_error = False).__dict__)
            final_path["idx"] = final_path["idx"] + 1
            final_path["step"] = final_path["step"] + 1
            path_list_tmp.append(final_path)
        elif 'submit' in request.form:
            if last == -1:
                error = 'You must have at least one item before submitting.'
            elif has_error == True:
                error = 'Errors in form, please review and fix issues.'
            else:
                confirm = True
        elif 'confirm' in request.form:
            for path_item in path_list_tmp:
                sql = ''' INSERT INTO paper_path(step,submission_date,journal,url_param_id)
                    VALUES(%s,%s,%s,%s) '''
                cur = db.cursor()
                if path_item["submit_date"] != '':
                    cur.execute(sql, (path_item["step"], path_item["submit_date"], path_item["journal"], path_item["url_param_id"]))
                else:
                    sql = ''' INSERT INTO paper_path(step,journal,url_param_id)
                    VALUES(%s,%s,%s) '''
                    cur.execute(sql, (path_item["step"], path_item["journal"], path_item["url_param_id"]))
                db.commit()
                cur.close()
            sql = ''' UPDATE email_url
                SET completed_timestamp = %s
                WHERE url_param_id = %s '''
            cur = db.cursor()
            cur.execute(sql, (datetime.now(), url_id))
            db.commit()
            cur.close()
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
            path_list_tmp.append(paper_path(idx = (path_list_item['step'] - 1), url_param_id = url_id, step = path_list_item['step'], journal = path_list_item['journal'], submit_date = path_list_item['submission_date'], error = '', show_error = False).__dict__)

    
    db.close()
    return render_template('enter.html', email_url = email_url, journal_opts = journal_opts, article_info = article_info, author_doi = auth_aff_list, affiliation_list = affiliation_list, confirm = confirm, allow_enter = allow_enter, completed_paths = completed_paths, has_completed = (len(completed_paths) > 0))

class paper_path:
    def __init__(self, idx, url_param_id, step, journal, submit_date, error, show_error):
        self.idx = idx
        self.url_param_id = url_param_id
        self.step = step
        self.journal = journal
        self.submit_date = submit_date
        self.error = error
        self.show_error = show_error
    
    def validate(self, previous_date, max_date, previous_journal):
        self.error = ''
        if self.submit_date == '':
            # self.error = 'Submission date cannot be empty. '
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


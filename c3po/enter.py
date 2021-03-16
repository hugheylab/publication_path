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

bp = Blueprint('enter', __name__, url_prefix='/enter')

@bp.route('/<url_id>', methods=('GET', 'POST'))
def enter(url_id):

    db = get_db()

    allow_enter = True
    email_url = db.execute(
        'SELECT * FROM email_url WHERE url_param_id = %s', (url_id,)
    ).fetchone()

    if email_url['completed_timestamp'] != '':
        error = 'Path already entered for this unique URL, please re-register if you wish to enter a new publication path!'
        allow_enter = False

    completed_paths = db.execute(
        'SELECT * from paper_path WHERE url_param_id = (SELECT url_param_id from email_url WHERE completed_timestamp != "" and doi = %s ORDER BY completed_timestamp DESC LIMIT 1) ORDER BY step ASC;', (email_url['doi'],)
    ).fetchall()
    

    author_doi = db.execute(
        'SELECT * FROM author_doi WHERE doi = %s', (email_url['doi'],)
    ).fetchall()

    article_info = db.execute(
        'SELECT * FROM article_info WHERE doi = %s', (email_url["doi"],)
    ).fetchone()

    journal_opts = db.execute(
        'SELECT * FROM journal_name', ()
    ).fetchall()
    
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
        prior_date = ''
        max_date = article_info['pub_date']
        prev_journal = ''
        is_submit = ('submit' in request.form)
        has_error = False
        for i in range(0, last + 1):
            del_item_name = 'del_item'+str(steps[i])
            if not (del_item_name in request.form):
                path_item_tmp = paper_path(i + delMod, url_id, (i + 1) + delMod, journals[i], submit_dates[i], '', is_submit)
                path_item_tmp.validate(prior_date, max_date, prev_journal)
                prev_journal = path_item_tmp.journal
                if not path_item_tmp.error == '':
                    has_error = True
                
                if not 'Submission date' in path_item_tmp.error:
                    prior_date = path_item_tmp.submit_date
                path_list_tmp.append(path_item_tmp.__dict__)

            else:
                delMod = delMod - 1
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
                cur.execute(sql, (path_item["step"], path_item["submit_date"], path_item["journal"], path_item["url_param_id"]))
                db.commit()
                sql = ''' UPDATE email_url
                    SET completed_timestamp = ?
                    WHERE url_param_id = %s '''
                cur = db.cursor()
                cur.execute(sql, (datetime.now(), url_id))
                db.commit()
            return redirect(url_for('thanks.thanks', thanks_type = 'submission'))

        if error != None:
            flash(error)

        session["path_list"] = path_list_tmp
    elif allow_enter == False:
        path_list_entered = db.execute(
            'SELECT * FROM paper_path WHERE url_param_id = %s', (url_id,)
        ).fetchall()
        path_list_tmp = []
        for path_list_item in path_list_entered:
            path_list_tmp.append(paper_path(idx = (path_list_item['step'] - 1), url_param_id = url_id, step = path_list_item['step'], journal = path_list_item['journal'], submit_date = path_list_item['submission_date'], error = '', show_error = False).__dict__)

    
    return render_template('enter.html', email_url = email_url, journal_opts = journal_opts, article_info = article_info, author_doi = author_doi, confirm = confirm, allow_enter = allow_enter, completed_paths = completed_paths, has_completed = (len(completed_paths) > 0))

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
            self.error = 'Submission date cannot be empty. '
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
                    self.error = self.error + 'Submission Date cannot be after the puiblication date. '
        
        if self.journal == '':
            self.error = self.error + 'Journal cannot be empty. '
        elif self.journal == previous_journal:
            self.error = self.error + 'Journal cannot be equal to the previous journal. '


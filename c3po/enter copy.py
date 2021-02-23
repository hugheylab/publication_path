import functools
import json
from json import JSONEncoder
import datetime
from datetime import datetime
from datetime import date


from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db

bp = Blueprint('enter', __name__, url_prefix='/enter')

@bp.route('/<url_id>', methods=('GET', 'POST'))
def enter(url_id):

    db = get_db()

    email_url = db.execute(
        'SELECT * FROM email_url WHERE url_param_id = ?', (url_id,)
    ).fetchone()

    article_info = db.execute(
        'SELECT * FROM article_info WHERE doi = ?', (email_url["doi"],)
    ).fetchone()

    journal_opts = db.execute(
        'SELECT * FROM journal', ()
    ).fetchall()
    
    # The submitted request from the client-side is request with the following variables:
    # method (values = GET or POST) - The request method of either simply navigating to the page without submitting a form (GET) or the request sent once you click a button on the page to submit the form (POST)
    # form - The form you submit. Comes back as a list of key-avalue pairs ex.- ('input1', 'hello'), ('name', 'Josh')


    if request.method == 'GET':
        path_list_tmp = [paper_path(idx = 0, url_param_id = url_id, step = 1, journal = '', submit_date = '', error = '', show_error = False).__dict__]
        path_list_tmp.append(paper_path(idx = 1, url_param_id = url_id, step = 2, journal = article_info["journal_name"], submit_date = '', error = '', show_error = False).__dict__)
        session["path_list"] = path_list_tmp

    elif request.method == 'POST':
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
        max_date = ''
        is_submit = ('submit' in request.form)
        has_error = False
        for i in range(0, last + 1):
            del_item_name = 'del_item'+str(steps[i])
            if not (del_item_name in request.form):
                path_item_tmp = paper_path(i + delMod, url_id, (i + 1) + delMod, journals[i], submit_dates[i], '', is_submit)
                path_item_tmp.validate(max_date)
                if not path_item_tmp.error == '':
                    has_error = True
                
                if not 'Submission date' in path_item_tmp.error:
                    max_date = path_item_tmp.submit_date
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
                for path_item in path_list_tmp:
                    sql = ''' INSERT INTO paper_path(step,submission_date,journal,url_param_id)
                        VALUES(?,?,?,?) '''
                    cur = db.cursor()
                    cur.execute(sql, (path_item["step"], path_item["submit_date"], path_item["journal"], path_item["url_param_id"]))
                    db.commit()
                sql = ''' UPDATE email_url
                    SET completed_timestamp = ?
                    WHERE url_param_id = ? '''
                cur = db.cursor()
                cur.execute(sql, (datetime.now(), url_id))
                db.commit()
                return redirect(url_for('thanks.thanks', thanks_type = 'submission'))
        
        if error != None:
            flash(error)

        session["path_list"] = path_list_tmp


    return render_template('enter.html', email_url = email_url, journal_opts = journal_opts)

class paper_path:
    def __init__(self, idx, url_param_id, step, journal, submit_date, error, show_error):
        self.idx = idx
        self.url_param_id = url_param_id
        self.step = step
        self.journal = journal
        self.submit_date = submit_date
        self.error = error
        self.show_error = show_error
    
    def validate(self, previous_date):
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

                if p_date > s_date:
                    self.error = self.error + 'Submission Date cannot be prior to previous step date. '
        
        if self.journal == '':
            self.error = self.error + 'Journal cannot be empty.'


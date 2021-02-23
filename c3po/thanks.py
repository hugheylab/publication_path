import functools


from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db

bp = Blueprint('thanks', __name__, url_prefix='/thanks')

@bp.route('/<thanks_type>', methods=('GET', 'POST'))
def thanks(thanks_type):

    text = 'Thank you for registering to participate, all applicable authors should receive emails with links shortly!'
    if thanks_type == "submission":
        text = 'Thank you for submitting your publication information!'

    return render_template('thanks.html', text = text)

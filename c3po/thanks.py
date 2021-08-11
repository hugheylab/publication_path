import functools


from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db

bp = Blueprint('thanks', __name__, url_prefix='/thanks')

@bp.route('/<thanks_type>', methods=('GET', 'POST'))
def thanks(thanks_type):

    text = 'Thank you for registering to participate! All applicable authors should soon receive an email for each specified article. Each email will contain a unique URL to enter that article\'s submission path.'
    if thanks_type == "submission":
        text = 'Thank you for contributing your paper\'s submission path!'

    if request.method == 'POST':
        return redirect(url_for('author.register'))

    return render_template('thanks.html', text = text, thanks_type = thanks_type)

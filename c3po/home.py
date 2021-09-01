from c3po.auth import login_required
import functools
import re
import psycopg2
from psycopg2.extras import DictCursor

from datetime import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify
)
import requests
from werkzeug.security import check_password_hash, generate_password_hash

from c3po.db import get_db
from c3po.db import pg_query
from c3po.email_handler import send_email
import c3po.orcid_api
import hashlib

bp = Blueprint('home', __name__, url_prefix='/home')

@bp.route('/landing', methods=('GET', 'POST'))
@login_required
def landing():
    return render_template('home/landing.html')
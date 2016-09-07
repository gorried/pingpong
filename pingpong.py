import atexit
import math
import os
import sqlite3
import time

from dateutil import parser as date_parser
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash

#mortality
mortals = ['ben']

# the number of days of inactivity after which we begin to decay
DECAY_AFTER = 3

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'pingpong.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print 'Initialized the database.'

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/')
def game():
    db = get_db()
    cur = db.execute('select first_name, last_name from users order by first_name')
    users = cur.fetchall()
    cur = db.execute('select first_name, last_name, elo, won, lost from users order by elo desc, first_name')
    rankings = cur.fetchall()
    return render_template('game.html', users=users, rankings=rankings)

@app.route('/add_user', methods=['POST'])
def add_user():
    db = get_db()
    # check for dupes
    cur = db.execute('select id from users where first_name=? and last_name=?', (request.form['fn'], request.form['ln']))
    if len(cur.fetchall()) == 0:
        db.execute(
            'insert into users (first_name, last_name, updated_at) values (?, ?, ?)',
            [request.form['fn'], request.form['ln'], str(datetime.now())])
        db.commit()
        flash('New entry was successfully posted')

    return redirect(url_for('game'))

@app.route('/add_game', methods=['POST'])
def add_game():
    K_VALUE = 32
    STD_DEV = 400
    SCORE_FLOOR = 100

    # code for updating elo score goes here
    db = get_db()
    winner = request.form['winner'].split(' ')
    loser = request.form['loser'].split(' ')

    # get the id's from the winner and loser
    winner_id, winner_elo = db.execute('select id, elo from users where first_name = ? and last_name = ?', (winner[0], winner[1])).fetchone()
    loser_id, loser_elo = db.execute('select id, elo from users where first_name = ? and last_name = ?', (loser[0], loser[1])).fetchone()

    # sanity check: if scores or id's are the same, fail silently
    if winner_id != loser_id:
        # adjust the scores of the players
        e_winner = 1.0 / (1 + 10.0 ** (float(loser_elo - winner_elo) / STD_DEV))
        e_loser = 1.0 / (1 + 10.0 ** (float(winner_elo - loser_elo) / STD_DEV))

        new_winner_elo = int(max(winner_elo + K_VALUE * (1 - e_winner), SCORE_FLOOR))
        new_loser_elo = int(max(loser_elo - K_VALUE * e_loser, SCORE_FLOOR))

        winner_is_mortal = len([winner[0] for x in mortals if winner[0].lower() in x.lower()]) > 0

        if not winner_is_mortal:
            # update winner
            db.execute('update users set won = won + 1, elo = ?, updated_at = ? where id = ?', (new_winner_elo, str(datetime.now()), winner_id))

        # update loser
        db.execute('update users set lost = lost + 1, elo = ?, updated_at = ? where id = ?', (new_loser_elo, str(datetime.now()), loser_id))

        db.commit()

    return redirect(url_for('game'))

"""
Implements a decay function in three phases

returns positive number representing the decay

phase 0 - don't decay for a week
phase 1 - polynomial decay to -200 over the course of two weeks
phase 2 - negative logarithmic decay to -300 over the course of two weeks
phase 3 - linear decay over two weeks to -600
"""
def decay_fn(day):
    # cannot decay more than this
    P1_MAX_DECAY = 200
    P2_MAX_DECAY = 100
    P3_MAX_DECAY = 300

    DURATION = 14

    P1_END = DURATION
    P2_END = P1_END + DURATION

    norm_day = day - DECAY_AFTER

    if day < P1_END:
        return P1_MAX_DECAY * poly_fn(DURATION, day)
    elif day < P2_END:
        return sum([P1_MAX_DECAY, P2_MAX_DECAY * log_fn(DURATION, day - P1_END)])
    else:
        max_decay = sum([P1_MAX_DECAY, P2_MAX_DECAY, P3_MAX_DECAY])
        curr_decay = sum([P1_MAX_DECAY, P2_MAX_DECAY, P3_MAX_DECAY * linear_fn(DURATION, day - P2_END)])
        return min(max_decay, curr_decay)

"""
Decay functions for the different phases.

Return a number in [0,1]
"""

# polynomial
def poly_fn(duration, day):
    return float(day ** 2) / float(duration ** 2)

# log
def log_fn(duration, day):
    return math.log(day + 1) / math.log(duration + 1)

# linear
def linear_fn(duration, day):
    return (1.0 / duration) * day

def decay_for(day):
    return -abs(decay_fn(day-1) - decay_fn(day))

def decay_elo():
    with app.app_context():
        db = get_db()
        cur = db.execute('select id, elo, updated_at from users')
        entries = cur.fetchall()
        for entry in entries:
            days = (datetime.now() - date_parser.parse(entry[2])).days
            if days > DECAY_AFTER:
                db.execute('update users set elo = ? where id = ?', (int(entry[1]) + int(decay_fn(days)), entry[0]))

        db.commit()

# schedule our decay function
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=decay_elo,
    trigger=IntervalTrigger(hours=24),
    id='elo_decay',
    name='Decay Elo every day',
    replace_existing=True)
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

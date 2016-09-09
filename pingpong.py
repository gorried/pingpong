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

from pyslack import SlackClient
slack_client = SlackClient(os.environ['SLACK_API_TOKEN'])

# the number of days of inactivity after which we begin to decay
DECAY_AFTER = 3

# Utility functions
def is_ben(first, last):
    return first == 'Ben' and last == 'Gilbert'

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
    first_name = request.form['fn']
    last_name = request.form['ln']
    # check for dupes
    cur = db.execute(
        'select id from users where first_name=? and last_name=?',
        (first_name, last_name)
        )
    if len(cur.fetchall()) == 0:
        db.execute(
            'insert into users (first_name, last_name, updated_at) values (?, ?, ?)',
            (first_name, last_name, str(datetime.now()))
            )
        if is_ben(first_name, last_name):
            db.execute(
                'update users set catchphrase=? where first_name=? and last_name=?',
                ('test test test', first_name, last_name)
                )
        db.commit()

    return redirect(url_for('game'))

@app.route('/add_catchphrase', methods=['POST'])
def add_catchphrase():
    db = get_db()
    first_name, last_name = request.form['name'].split(' ')
    if not is_ben(first_name, last_name):
        db.execute(
            'update users set catchphrase=? where first_name=? and last_name=?',
            (request.form['phrase'], first_name, last_name)
            )
        db.commit()
    return redirect(url_for('game'))

@app.route('/add_game', methods=['POST'])
def add_game():

    STD_DEV = 400
    SCORE_FLOOR = 100

    # define the slack interface
    si = SlackInterface()

    db = get_db()
    winner = request.form['winner'].split(' ')
    loser = request.form['loser'].split(' ')

    # get the id's from the winner and loser
    winner_id, winner_elo, winner_won, winner_lost = db.execute('select id, elo, won, lost from users where first_name = ? and last_name = ?', (winner[0], winner[1])).fetchone()
    loser_id, loser_elo, loser_won, loser_lost = db.execute('select id, elo, won, lost from users where first_name = ? and last_name = ?', (loser[0], loser[1])).fetchone()

    winner_games = winner_lost + winner_won
    loser_games = loser_lost + loser_won

    # sanity check: if scores or id's are the same, fail silently
    if winner_id != loser_id:
        # adjust the scores of the players
        e_winner = 1.0 / (1 + 10.0 ** (float(loser_elo - winner_elo) / STD_DEV))
        e_loser = 1.0 / (1 + 10.0 ** (float(winner_elo - loser_elo) / STD_DEV))

        new_winner_elo = int(max(winner_elo + get_k(winner_elo, winner_games) * (1 - e_winner), SCORE_FLOOR))
        new_loser_elo = int(max(loser_elo - get_k(loser_elo, loser_games) * e_loser, SCORE_FLOOR))

        # get old rankings
        cur = db.execute('select id, first_name, last_name, elo from users order by elo desc, first_name')
        old_rankings = cur.fetchall()

        # update winner
        db.execute('update users set won = won + 1, elo = ?, updated_at = ? where id = ?', (new_winner_elo, str(datetime.now()), winner_id))

        # update loser
        db.execute('update users set lost = lost + 1, elo = ?, updated_at = ? where id = ?', (new_loser_elo, str(datetime.now()), loser_id))

        # get new rankings
        cur = db.execute('select id, first_name, last_name, elo from users order by elo desc, first_name')
        new_rankings = cur.fetchall()

        si.test(
            (winner_id, winner[0], winner[1], winner_elo),
            (loser_id, loser[0], loser[1], loser_elo),
            old_rankings,
            new_rankings
            )

        db.commit()

    return redirect(url_for('game'))

def get_k(elo, games):
    K_VALUE = 32
    K_BEGINNER = 60
    K_MASTER = 10

    if games < 10:
        return K_BEGINNER
    elif elo > 2000:
        return K_MASTER
    else:
        return K_VALUE

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

'''
Skeleton code for slack events
'''

def stdev(arr):
    if len(arr) < 2:
        raise ValueError("To calculate stdev, length ")
    mean = float(sum(arr)) / len(arr)
    deltas = [abs(a - mean)**2 for a in arr]
    return math.sqrt(float(sum(deltas)) / len(deltas))

class SlackInterface:
    def __init__(self):
        self.channel = '#pong'

    def send_to_slack(self, title, message, name, id_for_phrase):
        slack_client.chat_post_message(self.channel, title+'\n'+message, username='pongbot')
        phrase = self.get_phrase(id_for_phrase)
        if phrase:
            self.send_to_slack_as(name, phrase)

    def send_to_slack_as(self, name, message):
        slack_client.chat_post_message(self.channel, message, username=name)

    def get_phrase(self, _id):
        with app.app_context():
            db = get_db()
            phrase = db.execute('select catchphrase from users where id=?', [_id]).fetchone()[0]
            print phrase
            return phrase

    '''
    winner - (id, first, last, elo)
    loser - (id, first, last, elo)
    old_rankings - [(id, first, last, elo) ...]
    new_rankings - [(id, first, last, elo) ...]
    '''
    def test(self, winner, loser, old_rankings, new_rankings):
        return (
            self.leader_changed(old_rankings, new_rankings) or
            self.upset(winner, loser, old_rankings) or
            self.position_swap(old_rankings, new_rankings)
            )

    def leader_changed(self, old_rankings, new_rankings):
        old_id, old_first, old_last, old_elo = old_rankings[0]
        new_id, new_first, new_last, new_elo = new_rankings[0]

        if old_id != new_id:
            # query for phrase
            self.send_to_slack(
                'New Leader!',
                '{} has overtaken {} as the leader of PSL ping pong!'.format(
                    '{} {}'.format(new_first, new_last),
                    '{} {}'.format(old_first, old_last)
                    ),
                new_first,
                new_id
                )
            phrase = self.get_phrase(new_id)
            if phrase:
                self.send_to_slack_as(new_first, phrase)
            return True
        return False

    def upset(self, winner, loser, rankings):
        elos = [r[3] for r in rankings]
        sd = stdev(elos)

        winner_id, winner_first, winner_last, winner_elo = winner
        loser_id, loser_first, loser_last, loser_elo = loser

        if loser_elo - winner_elo > 1.5 * sd:
            self.send_to_slack(
                'Get Rekd!',
                '{}, ({}) has upset {} ({}). How embarrassing for {}!'.format(
                    '{} {}'.format(winner_first, winner_last),
                    winner_elo,
                    '{} {}'.format(loser_first, loser_last),
                    loser_elo,
                    loser_first,
                    ),
                winner_first,
                winner_id
                )
            return True
        return False

    def position_swap(self, old_rankings, new_rankings):
        if len(old_rankings) != len(new_rankings):
            raise ValueError("Rankings of different length")

        for i in xrange(len(old_rankings)):
            old_id, old_first, old_last, old_elo = old_rankings[i]
            new_id, new_first, new_last, new_elo = new_rankings[i]

            if old_id != new_id:
                place = i + 1

                suffix = 'th'
                if place == 1:
                    suffix = 'st'
                elif place == 2:
                    suffix = 'nd'
                elif place == 3:
                    suffix = 'rd'

                self.send_to_slack(
                    '{} has passed {} to take {} place!'.format(
                        '{} {}'.format(old_first, old_last),
                        '{} {}'.format(new_first, new_last),
                        '{}{}'.format(place, suffix)
                        ),
                    '',
                    new_first,
                    new_id
                    )
                return True
        return False



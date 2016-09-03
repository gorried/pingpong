import os
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash

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

@app.route('/games')
def games():
    db = get_db()
    # get the games joining with users and fetching the names
    cur = db.execute('select * from games')
    entries = cur.fetchall()
    cur = db.execute('select id, first_name, last_name from users')
    users = cur.fetchall()
    return render_template('games.html', entries=(entries, users))

@app.route('/rankings')
def rankings():
    db = get_db()
    cur = db.execute('select first_name, last_name, score, won, lost from users order by score desc')
    entries = cur.fetchall()
    return render_template('rankings.html', entries=entries)

@app.route('/')
def game():
    db = get_db()
    cur = db.execute('select first_name, last_name from users order by first_name')
    entries = cur.fetchall()
    return render_template('game.html', entries=entries)

@app.route('/add_user')
def add_user():
    db = get_db()
    return render_template('add_user.html')

@app.route('/add_user_method', methods=['POST'])
def add_user_method():
    db = get_db()
    db.execute(
        'insert into users (first_name, last_name) values (?, ?)',
        [request.form['fn'], request.form['ln']])
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
    winner_id, winner_score = db.execute('select id, score from users where first_name = ? and last_name = ?', (winner[0], winner[1])).fetchone()
    loser_id, loser_score = db.execute('select id, score from users where first_name = ? and last_name = ?', (loser[0], loser[1])).fetchone()

    s1 = request.form['score1']
    s2 = request.form['score2']

    # sanity check: if scores or id's are the same, fail silently
    if winner_id != loser_id and s1 != s2 and s1.isdigit() and s2.isdigit():
        if s1 < s2:
            s1, s2 = (s2, s1)

        # adjust the scores of the players
        e_winner = 1.0 / (1 + 10.0 ** (float(loser_score - winner_score) / STD_DEV))
        e_loser = 1.0 / (1 + 10.0 ** (float(winner_score - loser_score) / STD_DEV))

        new_winner_score = max(winner_score + K_VALUE * (1 - e_winner), SCORE_FLOOR)
        new_loser_score = max(loser_score - K_VALUE * e_loser, SCORE_FLOOR)

        # update winner
        db.execute('update users set won = won + 1, score = ? where users.first_name = ? and users.last_name = ?', (new_winner_score, winner[0], winner[1]))

        # update loser
        db.execute('update users set lost = lost + 1, score = ? where users.first_name = ? and users.last_name=?', (new_loser_score, loser[0], loser[1]))

        # log the game
        db.execute(
            'insert into games (winner_id, winner_name, loser_id, loser_name, winner_score, loser_score) values (?, ?, ?, ?, ?, ?)',
            (winner_id, request.form['winner'], loser_id, request.form['loser'], s1, s2))

        db.commit()

    return redirect(url_for('game'))

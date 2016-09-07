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


@app.route('/')
def game():
    db = get_db()
    cur = db.execute('select first_name, last_name from users order by first_name')
    users = cur.fetchall()
    cur = db.execute('select first_name, last_name, elo, won, lost from users order by elo desc')
    rankings = cur.fetchall()
    return render_template('game.html', users=users, rankings=rankings)

@app.route('/add_user', methods=['POST'])
def add_user():
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
    winner_id, winner_elo = db.execute('select id, elo from users where first_name = ? and last_name = ?', (winner[0], winner[1])).fetchone()
    loser_id, loser_elo = db.execute('select id, elo from users where first_name = ? and last_name = ?', (loser[0], loser[1])).fetchone()

    # sanity check: if scores or id's are the same, fail silently
    if winner_id != loser_id:
        # adjust the scores of the players
        e_winner = 1.0 / (1 + 10.0 ** (float(loser_elo - winner_elo) / STD_DEV))
        e_loser = 1.0 / (1 + 10.0 ** (float(winner_elo - loser_elo) / STD_DEV))

        new_winner_elo = max(winner_elo + K_VALUE * (1 - e_winner), SCORE_FLOOR)
        new_loser_elo = max(loser_elo - K_VALUE * e_loser, SCORE_FLOOR)

        # update winner
        db.execute('update users set won = won + 1, elo = ? where id = ?', (new_winner_elo, winner_id))

        # update loser
        db.execute('update users set lost = lost + 1, elo = ? where id = ?', (new_loser_elo, loser_id))

        db.commit()

    return redirect(url_for('game'))

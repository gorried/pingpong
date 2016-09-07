pip install flask
pip install apscheduler

export FLASK_APP=pingpong.py
export FLASK_DEBUG=0

# If this is your first time running, uncomment the next line
flask initdb

flask run

pip install flask

export FLASK_APP=pingpong.py
export FLASK_DEBUG=0

flask initdb
flask run

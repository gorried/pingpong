pip install flask
pip install apscheduler
pip install pyslack-real
pip install python-dateutil

export FLASK_APP=pingpong.py
export FLASK_DEBUG=1

# If this is your first time running, uncomment the next line
if [ $1 == "init" ]
then
  touch pingpong.db
  chmod 777 pingpong.db
  flask initdb
fi

flask run

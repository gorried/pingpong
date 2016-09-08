pip install flask
pip install apscheduler
pip install pyslack-real

export FLASK_APP=pingpong.py
export FLASK_DEBUG=1

# If this is your first time running, uncomment the next line
if [ $1 == "init" ]
then
  flask initdb
fi

flask run

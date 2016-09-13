# pingpong
Yo so to run this thing hit that clone button then cd until deploy.sh is in your working directory. then run `./deploy.sh init` if it is your first time (so database gets created), otherwise run `./deploy.sh`

## SLACK API Integration
Â
to get slack to working set the bash env. variable `export SLACK_API_TOKEN="<key goes here>"`


### Useful debugging commands:

1. View apache logs
```
sudo tail -100 /var/log/apache2/error.log
```
2. Restart apache
```
sudo service apache2 restart
```

I followed [this](http://www.datasciencebytes.com/bytes/2015/02/24/running-a-flask-app-on-aws-ec2/) tutorial to get flask up and running on EC2.

Softwares it is hosted at:

http://ec2-54-175-163-132.compute-1.amazonaws.com/


Note: One stupid thing that took forever to figure out, apache uses the `www-data` user to access the files, and the `pingpong.db` AND the directory it is in must be owned by `www-data`. So, when you do `ls -la` in the `~/pingpong` dir, make sure it looks like this:

```
ubuntu@ip-172-31-16-218:~/pingpong$ ls -la
total 76
drwxrwxr-x 5 www-data ubuntu    4096 Sep 13 09:13 .
drwxr-xr-x 6 ubuntu   ubuntu    4096 Sep 13 09:11 ..
-rwxrwxr-x 1 ubuntu   ubuntu     307 Sep 13 08:45 deploy.sh
drwxrwxr-x 8 ubuntu   ubuntu    4096 Sep 13 08:24 .git
-rw-rw-r-- 1 ubuntu   ubuntu      11 Sep 13 07:56 .gitignore
-rwxrwxrwx 1 www-data www-data  3072 Sep 13 09:13 pingpong.db
-rw-rw-r-- 1 ubuntu   ubuntu   12459 Sep 13 09:11 pingpong.py
-rw-rw-r-- 1 ubuntu   ubuntu   12621 Sep 13 09:11 pingpong.pyc
-rw-rw-r-- 1 ubuntu   ubuntu      97 Sep 13 08:01 pingpong.wsgi
-rw-rw-r-- 1 ubuntu   ubuntu     343 Sep 13 07:56 README.md
-rw-rw-r-- 1 ubuntu   ubuntu     301 Sep 13 07:56 schema.sql
drwxrwxr-x 2 ubuntu   ubuntu    4096 Sep 13 07:56 static
drwxrwxr-x 2 ubuntu   ubuntu    4096 Sep 13 07:56 templates
```

Note2: the `deploy.sh` doesn't really work on the server (setting env variables, etc.) //TODO.



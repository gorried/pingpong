drop table if exists users;
drop table if exists games;
create table users (
  id integer primary key autoincrement,
  first_name text not null,
  last_name text not null,
  score integer not null default 1500,
  won integer not null default 0,
  lost integer not null default 0
);

create table games (
  id integer primary key autoincrement,
  winner_id integer not null,
  winner_name text not null,
  loser_id integer not null,
  loser_name text not null,
  winner_score integer not null,
  loser_score integer not null
);

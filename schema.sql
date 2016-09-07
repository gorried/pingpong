drop table if exists users;
drop table if exists games;
create table users (
  id integer primary key autoincrement,
  first_name text not null,
  last_name text not null,
  elo integer not null default 1500,
  won integer not null default 0,
  lost integer not null default 0
);

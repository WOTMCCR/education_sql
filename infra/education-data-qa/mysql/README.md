# MySQL Init Directory

This directory is mounted to `/docker-entrypoint-initdb.d` for the Iteration 01
local MySQL service.

Business DDL is intentionally applied by `data_ge/edu-data/init_db.py`, not by
Docker entrypoint SQL files, so the data generator remains the single owner of
the education schema initialization flow.

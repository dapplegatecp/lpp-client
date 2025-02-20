#!/bin/bash
. ./.env
cppython webapp.py &
cppython main.py
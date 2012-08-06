#!/bin/sh
pip install virtualenvwrapper
export WORKON_HOME=~/Documents/Envs
export PROJECT_HOME=~/Documents/Codebase
mkdir -p $WORKON_HOME
source /usr/local/bin/virtualenvwrapper.sh
mkvirtualenv star-slurper
setvirtualenvproject $WORKON_HOME/star-slurper $PROJECT_HOME/star-slurper
workon star-slurper
pip install -r requirements.txt

Tests to check stacklight

Prerequisites:
==============

Code requirements:
------------------
Install requirements with 'pip install -r requirements.txt'


Build and install as python package
===================================
Build dist with next command:
   python setup.py sdist

or:
   tox -e build

Run install on target machine:
   pip install dist/stacklight_tests-1.0.tar.gz --process-dependency-links

where "--process-dependency-links" flag is necessary.


Installing dependencies and system packages
===========================================
To install system packages run:
   apt install -y build-essential libssl-dev libffi-dev python-dev libyaml-dev python-dev python-pip

Create and activate virtualenv:
   pip install virtualenv
   virtualenv ../venv-stacklight-test
   source ../venv-stacklight-test/bin/activate

Install dependencies, if you aren't using this project as package:
   pip install -r requirements.txt

Run tests
=========

In case of using MK2x it worth generating config from mk env to run tests:
   PYTHONPATH=".:$PYTHONPATH" python stacklight_tests/config/mk_config.py

or run:
   stl-tests gen-config-mk

if you have stacklight_tests installed.

To view initial tests in test_alerts.py just type 'pytest'. They are using
default settings from deployment. Later it is going to be configured.


Notes
=====

The difference between our fixture "destructive"
with its method ".append(callable_recovery)" usage
and pytest built-in "request" with method ".addfinalizer(callable)
is in post conditions: "destructive" makes his work only on fail,
"finalizer" makes it in any case.
So, use destructive, when reverting of something broken is made in test itself,
and finalizer when it is not.
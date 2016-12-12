#!/usr/bin/env python

import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def get_requirements_list(requirements):
    all_requirements = read(requirements)
    all_requirements = all_requirements.splitlines()
    # Hack needed to packaging and tox,
    # because stable/mitaka version is not on PyPi server
    all_requirements.append("python-fuelclient>=9.0.0,<10.0.0")  # Apache-2.0
    return all_requirements

setup(
    name='stacklight_tests',
    version=1.0,
    description='Unified integration tests for StackLight platform',

    url='http://www.openstack.org/',
    author='Mirantis',
    author_email='openstack-dev@lists.openstack.org',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'stl-tests = stacklight_tests.shell:main'
        ]
    },
    package_data={
        'stacklight_tests': ['fixtures/*.*'],
    },
    include_package_data=True,
    classifiers=[
        'Environment :: Linux',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    dependency_links=[
        'git+git://github.com/openstack/python-fuelclient@stable/mitaka'
        '#egg=python-fuelclient-9.0.2',
    ],
    install_requires=get_requirements_list('./requirements.txt'),
)

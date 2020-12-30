# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

NAME = "orienteering_accounts"
VERSION = '0.0.1a'

setup(
    name=NAME,
    version=VERSION,
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ]
)

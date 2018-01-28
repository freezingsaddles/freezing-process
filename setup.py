# -*- coding: utf-8 -*-
import os.path
import re
import warnings

from pip.req import parse_requirements
from setuptools import setup, find_packages

version = '0.1.0'

long_description = """
freezing-sync is the component responsible for fetching activities, weather data, etc.
"""

# parse_requirements() returns generator of pip.req.InstallRequirement objects
install_reqs = parse_requirements(os.path.join(os.path.dirname(__file__), 'requirements.txt'), session=False)

# reqs is a list of requirement
# e.g. ['django==1.5.1', 'mezzanine==1.4.6']
reqs = [str(ir.req) for ir in install_reqs]

setup(
    name='freezing-sync',
    version=version,
    author='Hans Lellelid',
    author_email='hans@xmpl.org',
    url='http://github.com/freezingsaddles/freezing-sync',
    license='Apache',
    description='Freezing Saddles activity and metadata sync.',
    long_description=long_description,
    packages=[
        'freezing.sync',
        'freezing.sync.cli',
        'freezing.sync.data',
        'freezing.sync.wx',
        'freezing.sync.wx.wunder',
        'freezing.sync.wx.ncdc'
    ],
    # include_package_data=True,
    # package_data={'stravalib': ['tests/resources/*']},
    install_requires=reqs,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    entry_points="""
    [console_scripts]
    freezing-sync = freezing.sync.cli.sync_activities:main
    freezing-sync-detail = freezing.sync.cli.sync_details:main
    freezing-sync-streams = freezing.sync.cli.sync_streams:main
    #freezing-sync-photos = freezing.sync.cli.sync_photos:main
    #freezing-sync-weather = freezing.sync.cli.sync_ride_weather:main
    #freezing-sync-athletes = freezing.sync.cli.sync_athletes:main
    #freezing-fix-photo-urls = freezing.sync.cli.fix_photo_urls:main
    """,
    zip_safe=True
)

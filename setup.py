#!/usr/bin/env python

"""dcosdev project"""
from setuptools import find_packages, setup

REQUIRES = [
    'docker==4.2.0',
    'minio==5.0.8',
    'requests==2.23.0',
    'boto3==1.12.34',
    "click==7.1.1",
    "pyyaml==5.3.1",
]

setup(name='dcosdev',
      version='0.0.1',
      description='short description',
      long_description='long description',
      platforms=["Linux"],
      author="...",
      author_email="...",
      url="...",
      license="Apache 2",
      packages=find_packages(),
      entry_points={
        'console_scripts': [
            'dcosdev=dcosdev.commands:maingroup',
        ],
      },
      install_requires=REQUIRES,
      zip_safe=False,
      include_package_data=True,
      )

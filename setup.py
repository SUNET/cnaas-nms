import os
import setuptools


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

version = '0.1.0'

requires = open(os.path.join(here, 'requirements.txt'), 'r').read().split()


setuptools.setup(
    name='cnaas_nms',
    author='SUNET',
    author_email='',
    version=version,
    description='Campus Network as-a-Service - Network Management System (Campus network automation software)',
    long_description=README,
    long_description_content_type='text/markdown',
    url='https://github.com/sunet/cnaas-nms',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: Copyright (c) 2019, SUNET (BSD 2-clause license)',
        'Operating System :: UNIX/Linux',
    ],
    package_dir={'': 'src'},
    packages=setuptools.find_packages('src', exclude=['tests']),
    include_package_data=True,
    install_requires=requires,
)

import os
import setuptools

setuptools.setup(
    name='cnaas_nms',
    version="0.1.0",
    author="Johan Marcusson, Kristofer Hallin",
    author_email="johan@sunet.se, kristofer@sunet.se",
    description="Campus Network as-a-Service - Network Management System (Campus network automation software)",
    # long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sunet/cnaas-nms",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Copyright (c) 2019, SUNET (BSD 2-clause license)",
        "Operating System :: UNIX/Linux",
    ],
    package_dir={'': 'src'},
    packages=setuptools.find_packages("src", exclude=["tests"]),
    include_package_data=True,
)

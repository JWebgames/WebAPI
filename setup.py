from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'version'), encoding='utf-8') as f:
    version = f.read()

setup(
    name='julien-webapi',
    version=version,
    description='Webgames Web REST API',
    long_description=long_description,
    url='https://github.com/JWebgames/webapi',
    author='Julien Castiaux',
    author_email='Julien.castiaux@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        'Topic :: Games/Entertainment',
    ],
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
          "aioredis",
          "asyncpg",
          "pyjwt",
          "pytimeparse",
          "PyYAML",
          "sanic",
          "scrypt"
    ],
    extras_require={
        'test': ['pylint', 'coverage', 'codecov', 'aiohttp'],
    },
)
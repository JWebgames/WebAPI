from setuptools import setup

setup(name='webapi',
      version='0.1',
      description="Webgames Web API for managing games",
      url="https://git.julien00859.be/Webgames/WebAPI",
      author="Julien Castiaux",
      author_email="Julien.castiaux@gmail.com",
      license="MIT",
      packages=["webapi"],
      install_requires=[
          "aioredis",
          "asyncpg",
          "pyjwt",
          "PyYAML",
          "sanic"
      ],
      zip_safe=False)

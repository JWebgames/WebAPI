"""Test runner for config module"""

import sys
from collections import ChainMap
from os.path import join as pathjoin
from shutil import move
from subprocess import Popen, PIPE
from unittest import TestCase

from webapi.config import WebAPIConfig,\
                          PostgresConfig,\
                          triples,\
                          get_default,\
                          validate,\
                          merge_sources,\
                          export_default_config
from webapi.exceptions import ConfigMissingOptionError,\
                              ConfigOptionTypeError,\
                              ConfigUnknownOptionError
from webapi.tools import root

OUTPUT = """+------------------------------cli:webapi------------------------------+
| LOG_LEVEL                        |                             DEBUG |
+-----------------------------cli:postgres-----------------------------+
| HOST                             |                       192.168.0.3 |
+------------------------------env:webapi------------------------------+
| LOG_LEVEL                        |                              INFO |
+-----------------------------env:postgres-----------------------------+
| HOST                             |                       192.168.0.2 |
+------------------------------env:redis-------------------------------+
| DSN                              |        redis://192.168.0.1:6379/0 |
+------------------------------yml:docker------------------------------+
| HOST                             |       unix:///var/run/docker.sock |
+-----------------------------yml:messager-----------------------------+
| PUB_ADDRESS                      |             tcp://127.0.0.1:22550 |
| PULL_ADDRESS                     |             tcp://127.0.0.1:22549 |
+-----------------------------yml:postgres-----------------------------+
| DATABASE                         |                              None |
| DSN                              |                              None |
| HOST                             | /var/run/postgr...l/.s.PGSQL.5432 |
| PASSWORD                         |                              None |
| PORT                             |                              None |
| USER                             |                              None |
+------------------------------yml:redis-------------------------------+
| DSN                              |         /var/run/redis/redis.sock |
| PASSWORD                         |                              None |
+------------------------------yml:webapi------------------------------+
| HOST                             |                         localhost |
| JWT_EXPIRATION_TIME              |                               12h |
| JWT_SECRET                       |             super-secret-password |
| LOG_LEVEL                        |                           WARNING |
| PORT                             |                             22548 |
| PRODUCTION                       |                             False |
| SSL_CERT_PATH                    |                              None |
| SSL_KEY_PATH                     |                              None |
| SSL_KEY_PASS                     |                              None |
| GROUP_URL                        |  http://localhost:22548/v1/groups |
| MSGQUEUES_URL                    | http://localhos...48/v1/msgqueues |
| PULL_ADDRESS                     |             tcp://127.0.0.1:22549 |
| PUB_ADDRESS                      |             tcp://127.0.0.1:22550 |
| GAME_HOST                        |                         localhost |
| GAME_PORT_RANGE_START            |                             23000 |
| GAME_PORT_RANGE_STOP             |                             24000 |
+----------------------------merged:webapi-----------------------------+
| HOST                             |                         localhost |
| PORT                             |                             22548 |
| JWT_SECRET                       |             super-secret-password |
| JWT_EXPIRATION_TIME              |                               12h |
| LOG_LEVEL                        |                             DEBUG |
| PRODUCTION                       |                             False |
| SSL_CERT_PATH                    |                              None |
| SSL_KEY_PATH                     |                              None |
| SSL_KEY_PASS                     |                              None |
| GROUP_URL                        |  http://localhost:22548/v1/groups |
| MSGQUEUES_URL                    | http://localhos...48/v1/msgqueues |
| GAME_HOST                        |                         localhost |
| GAME_PORT_RANGE_START            |                             23000 |
| GAME_PORT_RANGE_STOP             |                             24000 |
+---------------------------merged:messager----------------------------+
| PULL_ADDRESS                     |             tcp://127.0.0.1:22549 |
| PUB_ADDRESS                      |             tcp://127.0.0.1:22550 |
+----------------------------merged:docker-----------------------------+
| HOST                             |       unix:///var/run/docker.sock |
+---------------------------merged:postgres----------------------------+
| HOST                             |                       192.168.0.3 |
| PORT                             |                              None |
| USER                             |                              None |
| DATABASE                         |                              None |
| PASSWORD                         |                              None |
+-----------------------------merged:redis-----------------------------+
| DSN                              |        redis://192.168.0.1:6379/0 |
| PASSWORD                         |                              None |
+----------------------------------------------------------------------+"""

class TestValidateConfig(TestCase):
    """Test case for config.validate_cofig"""

    default_config = get_default()

    def test_default_values(self):
        """Validate against default values"""
        for name, _, block in triples:
            self.assertIsNone(
                validate(name, block, self.default_config[name]))

    def test_missing_option(self):
        """Should fail for any missing field"""
        self.assertRaises(
            ConfigMissingOptionError, validate, "webapi", WebAPIConfig, {})

    def test_invalid_option_type(self):
        """Should fail for invalid type (without Union/Optionnal)"""
        config = ChainMap({"HOST": 5}, self.default_config["webapi"])
        self.assertRaises(
            ConfigOptionTypeError, validate, "webapi", WebAPIConfig, config)

    def test_invalid_option_type_typing(self):
        """Should fail for invalid type (with Union/Optionnal)"""
        config = ChainMap({"HOST": 5}, self.default_config["postgres"])
        self.assertRaises(
            ConfigOptionTypeError, validate, "postgres", PostgresConfig, config)

    def test_unknown_option(self):
        """Should fail for unknow field"""
        config = ChainMap({"foo": None}, self.default_config["webapi"])
        self.assertRaises(
            ConfigUnknownOptionError, validate, "webapi", WebAPIConfig, config)

class TestMergeSources(TestCase):
    """Test case for config.get_default and config.merge_sources"""
    def test_merged_default_is_default(self):
        """Get default config and merge it, should be the same"""
        gen = merge_sources(get_default(), {})
        for *_, block in triples:
            _, mblock = next(gen)
            self.assertEqual(mblock, block())

class ConfigIntegrationTest(TestCase):
    """Test the entire module"""

    def test_showconfig(self):
        """Run webapi with showconfig command and verify the output"""

        config_path = pathjoin(root(), "config.yml")
        move(config_path, "/tmp/webagmes_webapi_config.yml")

        old_stdout = sys.stdout
        with open(config_path, "w") as tmpconfig:
            sys.stdout = tmpconfig
            export_default_config()
        sys.stdout = old_stdout

        env = {
            "WEBAPI_LOG_LEVEL": "INFO",
            "REDIS_DSN": "redis://192.168.0.1:6379/0",
            "PGHOST": "192.168.0.2"
        }

        command = [
            sys.executable,
            "-m",
            "webapi",
            "showconfig",
            "--webapi_log_level",
            "DEBUG",
            "--postgres_host",
            "192.168.0.3"
        ]
        process = Popen(command, env=env, stdout=PIPE)
        process.wait()
        move("/tmp/webagmes_webapi_config.yml", config_path)
        process_output = process.stdout.read().decode()
        process.stdout.close()
        self.assertEqual(process.returncode, 0)

        hard_blc = {}
        proc_blc = {}
        for blocks, source in ((hard_blc, OUTPUT), (proc_blc, process_output)):
            for line in source.splitlines():
                if line.startswith("+"):
                    block_name = line.replace("+", "").replace("-", "")
                    if block_name:
                        blocks[block_name] = []
                else:
                    blocks[block_name].append(line)

        for block_name, lines in proc_blc.items():
            for line in lines:
                self.assertIn(line, hard_blc[block_name])

import os
import time
import random
import logging
import subprocess

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

POSTGRES_FILE='/cnaas.sql'

logging.basicConfig(level=logging.DEBUG)


class PostgresTemporaryInstance(object):
    """ Manage temporary Docker instance.

    The instance should be automatically destroyed
    at the end of the program.

    Also generate a random port number to avoid potential
    colission when running multiple tests in parallel.
    """

    def __init__(self, user='cnaas', passwd='cnaas', database='cnaas'):
        #self._port = random.randint(40000, 50000)
        self._user = user
        self._passwd = passwd
        self._database = database
        self._postgres = None
        self._port = 5432
        self._process = None

        if 'CNAAS_UNITTEST_DOCKER' not in os.environ:
            return

        conn_str = self.uri

        # Invoke docker run to start a progres container,
        # we will use the random port as part of the name to
        # make it unique.
        self._postgres = subprocess.Popen(['docker', 'run', '--rm',
                                           '-p', '{!s}:5432'.format(self._port),
                                           '-e', 'POSTGRES_USER={!s}'.format(self._user),
                                           '-e', 'POSTGRES_PASSWD={!s}'.format(self._passwd),
                                           '-e', 'POSTGRES_DB={!s}'.format(self._database),
                                           '--name', 'postgres_{!s}'.format(self._port),
                                           '--rm',
                                           'postgres:latest'],
                                          stdout=open('/tmp/docker_run.log', 'wb'),
                                          stderr=subprocess.STDOUT)

        for i in range(100):
            time.sleep(0.2)
            try:
                engine = create_engine(conn_str)
                connection = engine.connect()
            except:
                logging.debug('Connection to postgres failed')
                continue
            else:
                logging.debug('Connection to postgres was successful')
                break
        else:
            self.shutdown()
            logging.debug('Failed to start postgres')
            assert(False, 'Could not start postgres')

        # Copy the database dump to the container.
        subprocess.call(['docker', 'cp', 'cnaas.sql',
                          'postgres_{!s}:/'.format(self._port)],
                         stdout=open('/tmp/docker_cp.log', 'wb'),
                         stderr=subprocess.STDOUT)

        # Use the dump we copied in the previous step to restore
        # the database.
        subprocess.call(['docker', 'exec',
                          'postgres_{!s}'.format(self._port), 'psql',
                          '-U', 'cnaas',
                          '-d', 'cnaas',
                          '-f', POSTGRES_FILE],
                         stdout=open('/tmp/docker_psql.log', 'wb'),
                         stderr=subprocess.STDOUT)

    def shutdown(self):
        if self._postgres:
            self._postgres.terminate()
            self._postgres.kill()
            self._postgres = None

    @property
    def port(self):
        return self._port

    @property
    def container(self):
        return 'postgres_{!s}'.format(self._port)

    @property
    def uri(self):
        return(f'postgres://{self._user}:{self._passwd}@localhost:{self._port}/{self._database}')


if __name__ == '__main__':
    db = PostgresTemporaryInstance()
    # db.shutdown()

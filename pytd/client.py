import os
import six
import logging

from pytd.version import __version__
from pytd.writer import SparkWriter
from pytd.query_engine import PrestoQueryEngine, HiveQueryEngine

logger = logging.getLogger(__name__)


class Client(object):

    def __init__(self, apikey=None, endpoint=None, database='sample_datasets', default_engine='presto', header=True):
        if apikey is None:
            if 'TD_API_KEY' not in os.environ:
                raise ValueError("either argument 'apikey' or environment variable 'TD_API_KEY' should be set")
            apikey = os.environ['TD_API_KEY']

        if endpoint is None:
            if 'TD_API_SERVER' not in os.environ:
                raise ValueError("either argument 'endpoint' or environment variable 'TD_API_SERVER' should be set")
            endpoint = os.environ['TD_API_SERVER']

        self._connect_query_engines(apikey, endpoint, database)

        self.apikey = apikey
        self.endpoint = endpoint
        self.database = database
        self.default_engine = default_engine
        self.header = header

        self.writer = None

    def close(self):
        self.presto.close()
        self.hive.close()
        if self.writer is not None:
            self.writer.close()

    def query(self, sql, engine=None):
        if engine is None:
            engine = self.default_engine
        cur = self.get_cursor(engine)
        sql = self._create_header("Client#query(engine={0})".format(engine)) + sql
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return {'data': rows, 'columns': columns}

    def load_table_from_dataframe(self, df, table, if_exists='error'):
        if self.writer is None:
            self.writer = SparkWriter(self.apikey, self.endpoint)

        destination = table
        if '.' not in table:
            destination = self.database + '.' + table

        self.writer.write_dataframe(df, destination, if_exists)

    def get_cursor(self, engine=None):
        if engine is None:
            engine = self.default_engine

        if engine == 'presto':
            return self.presto.cursor()
        elif engine == 'hive':
            return self.hive.cursor()
        else:
            raise ValueError('`engine` should be "presto" or "hive"')

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.close()

    def _connect_query_engines(self, apikey, endpoint, database):
        self.presto = PrestoQueryEngine(apikey, endpoint.replace('api', 'api-presto'), database)
        self.hive = HiveQueryEngine(apikey, endpoint, database)

    def _create_header(self, extra_rows=None):
        if self.header is False:
            header = ''
        elif isinstance(self.header, six.string_types):
            header = "-- {0}\n".format(self.header)
        else:
            header = "-- client: pytd/{0}\n".format(__version__)

        if isinstance(extra_rows, six.string_types):
            header += "-- {0}\n".format(extra_rows)
        elif isinstance(extra_rows, (list, tuple)):
            header += ''.join(["-- {0}\n".format(row) for row in extra_rows])

        return header

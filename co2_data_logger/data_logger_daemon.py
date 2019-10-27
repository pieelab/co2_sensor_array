import datetime
import mysql.connector
import logging
import time
import numpy as np
from .remote_credentials import remote_credentials

N_SENSORS = 5
PUSH_PERIOD = 5#s, how often to aggredate and publish data on local mysql


class SerialDataFetcher(object):
    def __init__(self):
        self._data = list()
    def fetch(self):
        mock_data = np.random.rand(N_SENSORS)*1000.0 + 430
        self._data.append(mock_data)
        #self._data.append([None, time.time(), ])
    def aggregate(self, t):
        data = np.array(self._data)
        self._data = []
        timestamp = datetime.datetime.fromtimestamp(t).utcnow().strftime('%Y-%m-%d %H:%M:%S')
        data = np.median(data, 0).tolist()
        out = []
        for sensor_id, sensor_value in enumerate(data):
           out.append([0, timestamp, sensor_id, sensor_value])
        return out


class LocalDatabaseConnector(object):
    _db_host = "localhost"
    _fields = ["id INT  NOT NULL AUTO_INCREMENT PRIMARY KEY",
               "T DATETIME",
               "SENSOR TINYINT",
               "PPM_10X SMALLINT UNSIGNED"]
    def __init__(self, db_credentials, table_name):
        db_credentials["host"] = self._db_host
        self._db = mysql.connector.connect(**db_credentials)
        self._table_name = table_name
        command =  "CREATE TABLE IF NOT EXISTS %s (%s) KEY_BLOCK_SIZE=16;" % (table_name, ", ".join(self._fields))
        c = self._db.cursor()
        c.execute(command)
    @property
    def db(self):
        return self._db
    def write_line(self, value_list):
        c = self._db.cursor()
        for v in value_list:
            command = "INSERT INTO %s VALUES %s" % (self._table_name, str(tuple(v)))
            c.execute(command)
        self._db.commit()

class RemoteDbMirror(LocalDatabaseConnector):
    _db_host = "remotemysql.com"

    def mirror(self, local_db):
        remote_c = self._db.cursor()
        local_c = local_db.db.cursor()
        self._incremental_sync(local_c, remote_c, self._table_name)
        remote_c.execute("SHOW TABLES;")
        tables_to_sync_from_remote = []
        for c in remote_c:
            table = c[0].decode()
            if table != self._table_name:
                tables_to_sync_from_remote.append(table)
        for t in tables_to_sync_from_remote:
            self._incremental_sync(remote_c, local_c, t)

    def _incremental_sync(self, src_c, dst_c, table_name):
        try:
            dst_command = "SELECT MAX(id) FROM %s" % table_name
            dst_c.execute(dst_command)
        except Exception as e:
            logging.warning("Remote unavailable", e)

        last_id_in_dst = 0
        for c in dst_c:
            if c[0] is None:
                last_id_in_dst = -1
            else:
                last_id_in_dst = c[0]
        src_command = "SELECT * FROM %s WHERE id > %d" % (table_name, last_id_in_dst)
        src_c.execute(src_command)

        to_insert = []
        i = 0

        for lc in src_c:
            i += 1
            tp = tuple([str(v) for v in lc])
            to_insert.append(str(tp))
            if len(to_insert) > 100: # fixme number of rws to send at the same time
                value_string = ",".join(to_insert)
                dst_command = "INSERT INTO %s VALUES %s" % (table_name, value_string)
                dst_c.execute(dst_command)
                self._db.commit() # update remote
                to_insert = []

        if len(to_insert) > 0:
            value_string = ",".join(to_insert)
            dst_command = "INSERT INTO %s VALUES %s" % (table_name, value_string)
            dst_c.execute(dst_command)
            self._db.commit()  # update remote


# 1 ret
# 1 retreive last index on remote for current local table
# 2 send all new data
# 3 list all tables on remote
# get all non current tables last index
# get new data for each


if __name__ == "__main__":

    local_credential = {"database": "co2_sensors",
                   "user": "co2_logger",
                   "password": "co2_logger",
                   }

    TABLE_NAME = "pi_000002"
    local_db_con = LocalDatabaseConnector(local_credential, TABLE_NAME)
    sf = SerialDataFetcher()
    start = time.time()
    last_push = start
    while True:
        now = time.time()
        sf.fetch()
        time.sleep(1)
        if now - last_push >= PUSH_PERIOD:
            aggregate = sf.aggregate(now)
            last_push = now
            local_db_con.write_line(aggregate)
            try:
                remote_db = RemoteDbMirror(remote_credentials, TABLE_NAME)
                remote_db.mirror(local_db_con)

            except mysql.connector.errors.InterfaceError:
                logging.warning("No connection to remote db")
            except Exception as e:
                logging.error("Unknown remote db error", e)
                
# mysql -p -h remotemysql.com -u rgDubOKpGu rgDubOKpGu
# mysql -u root -p
# CREATE USER 'co2_logger'@'localhost' IDENTIFIED BY 'co2_logger';
# CREATE DATABASE co2_sensors;
# GRANT ALL PRIVILEGES ON co2_sensors.* TO 'co2_logger'@'localhost';
# FLUSH PRIVILEGES;

import datetime

import mysql.connector
import logging
import time
import numpy as np

N_SENSORS = 5
PUSH_PERIOD = 5#s, how often to aggredate and publish data on local mysql

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
        print(command)
        c = self._db.cursor()
        c.execute(command)
    def write_line(self, value_list):
        c = self._db.cursor()
        for v in value_list:
            command = "INSERT INTO %s VALUES %s" % (self._table_name, str(tuple(v)))
            c.execute(command)
        self._db.commit()

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
class RemoteDbMirror(object):
    pass

if __name__ == "__main__":
    credentials = {"database": "co2_sensors",
                   "user": "co2_logger",
                   "password": "co2_logger",
                   }
    local_db_con = LocalDatabaseConnector(credentials, "pi_000001")
    sf = SerialDataFetcher()
    start = time.time()
    last_push = start
    while True:
        now = time.time();
        sf.fetch()
        time.sleep(1)
        if now - last_push >= PUSH_PERIOD:
            aggregate = sf.aggregate(now)
            last_push = now
            local_db_con.write_line(aggregate)
# mysql -u root -p
# CREATE USER 'co2_logger'@'localhost' IDENTIFIED BY 'co2_logger';
# CREATE DATABASE co2_sensors;
# GRANT ALL PRIVILEGES ON co2_sensors.* TO 'co2_logger'@'localhost';
# FLUSH PRIVILEGES;

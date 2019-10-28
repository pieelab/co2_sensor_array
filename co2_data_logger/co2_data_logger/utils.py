import datetime
import mysql.connector
import logging
import numpy as np
import serial
import glob
import sys

N_SENSORS = 5

class SerialDataFetcher(object):
    def __init__(self, sensor_lut, baud):
        self._sensor_lut = sensor_lut
        self._data = list()
        self._port = None
        self._serial_port = self._serial_ports(baud)

    def _serial_ports(self, baud):
        if sys.platform.startswith('win'):
            ports = ['COM' + str(i + 1) for i in range(256)]

        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this is to exclude your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')

        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')

        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        if len(ports) == 0:
            raise Exception("No serial port found. "
                            "Ensure your device is plugged.")
        elif len(ports) > 2:
            logging.warning("%i serial ports found:\n %s" % (len(ports), "\n\t".join(ports)))

        return  serial.Serial(ports[0], baud, timeout=2)

    def fetch(self):

        line = self._serial_port.readline()
        if not line:
            return
        line = line.rstrip()
        values = [float(v) for v in line.split(b',') if v]
        if len(values) != N_SENSORS:
            Exception("Wrong number of values for the number of sensors")
        # mock_data = np.random.rand(N_SENSORS)*1000.0 + 430
        self._data.append(values)
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


class DummySerialDataFetcher(SerialDataFetcher):
    def _serial_ports(self, baud):
        return None
    def fetch(self):
        values = np.random.rand(N_SENSORS)*1000.0 + 430
        self._data.append(values)

class LocalDatabaseConnector(object):
    _fields = ["id INT  NOT NULL AUTO_INCREMENT PRIMARY KEY",
               "T DATETIME",
               "SENSOR TINYINT",
               "PPM_10X SMALLINT UNSIGNED"]

    def __init__(self, db_credentials, table_name):
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


# mysql -p -h remotemysql.com -u rgDubOKpGu rgDubOKpGu
# mysql -u root -p
# CREATE USER 'co2_logger'@'localhost' IDENTIFIED BY 'co2_logger';
# CREATE DATABASE co2_sensors;
# GRANT ALL PRIVILEGES ON co2_sensors.* TO 'co2_logger'@'localhost';
# FLUSH PRIVILEGES;

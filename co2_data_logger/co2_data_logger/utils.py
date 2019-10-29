import datetime
import mysql.connector
import logging
import numpy as np
import serial
import glob
import sys

class SerialDataFetcher(object):
    def __init__(self, baud,  sensor_lut = (0,1,2,3,4)):
        self._sensor_lut = sensor_lut
        if sensor_lut:
            logging.debug("sensor LUT: %s" % str(sensor_lut))
        self._data = list()
        self._port = None
        self._serial_port = self._serial_ports(baud)

    def _serial_ports(self, baud):
        logging.debug("scanning ports")
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
            logging.debug(port)
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
        logging.info("Receiving %s" % str(values))

        if len(values) != len(self._sensor_lut):
            logging.warning("wrong number of values %s" % str(values))
            return
        filtered = []
        for v in values:
            if v < 300 or v > 5000:
                logging.warning("Some values are not in expected range: %s" % v)
                filtered.append(np.NaN)
            else:
                filtered.append(v)

        self._data.append(values)

    def aggregate(self, t):
        if len(self._data) < 3:
            logging.warning("Less than 3 data point, not aggregrating")
            return None
        logging.info("Aggregating %i data points" % len(self._data))
        data = np.array(self._data)
        data = data * 10
        self._data = []
        timestamp = datetime.datetime.fromtimestamp(t).utcnow().strftime('%Y-%m-%d %H:%M:%S')

        data = np.round(np.median(data, 0)).astype(np.int).tolist()
        logging.debug(data)
        out = []
        for sensor_id, sensor_value in enumerate(data):
            if not np.isnan(sensor_value):
                row = [0, timestamp, self._sensor_lut[sensor_id], sensor_value]
                logging.info("Row %i: %s" % (sensor_id, str(row)))
                out.append(row)

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
        logging.info("%s on %s" % (command, self.__class__.__name__))
        c = self._db.cursor()
        c.execute(command)
    @property
    def db(self):
        return self._db
    def write_line(self, value_list):

        c = self._db.cursor()
        for v in value_list:
            command = "INSERT INTO %s VALUES %s" % (self._table_name, str(tuple(v)))
            logging.info("writing to local DB. Command: %s" % command)
            c.execute(command)
        self._db.commit()

class RemoteDbMirror(LocalDatabaseConnector):

    def mirror(self, local_db):
        remote_c = self._db.cursor()
        local_c = local_db.db.cursor()

        logging.info("Syncing local table %s to remote" % self._table_name)
        self._incremental_sync(local_c, remote_c, self._table_name)
        remote_c.execute("SHOW TABLES;")
        tables_to_sync_from_remote = []
        for c in remote_c:
            table = c[0].decode()
            if table != self._table_name:
                tables_to_sync_from_remote.append(table)
        logging.info("Target tables to sync from remote: %s" % str(tables_to_sync_from_remote))

        for t in tables_to_sync_from_remote:
            logging.info("Syncing table %s" % t)
            self._incremental_sync(remote_c, local_c, t)
            logging.info("%s synced" % t)

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
            if len(to_insert) > 100: # fixme number of rows to send at the same time
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

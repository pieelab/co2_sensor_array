from co2_data_logger.utils import *
import time
import mysql.connector
import logging
import configparser
import os

if __name__ == "__main__":
    config = configparser.ConfigParser()
    global_conf = config.read(['/etc/co2_data_logger.conf'])
    if not global_conf:
        logging.error("No system wide configuration file")

    config.read([os.path.join(os.path.expanduser("~"), '.co2_data_logger.conf'), 'co2_data_logger.conf'])

    env = dict(config["Env"])
    if env["env"] == "dev_dummy_serial":
        FetcherClass = DummySerialDataFetcher
    else:
        FetcherClass = SerialDataFetcher

    if env["env"] != "production":
        logger = logging.getLogger()
        logger.setLevel(level=logging.DEBUG)
        logging.info("Running in dev mode")


    local_credentials = dict(config["Local"])
    remote_credentials = dict(config["Remote"])
    device_info = dict(config["Device"])
    local_db_con = LocalDatabaseConnector(local_credentials, device_info['name'])
    sensor_lut = tuple(int(i) for i in device_info['sensor_lut'].split(','))

    sf = FetcherClass(int(device_info['baud']), sensor_lut)

    start = time.time()
    logging.debug("Starting at %i" % int(start))
    last_push = start
    while True:
        now = time.time()
        sf.fetch()
        time.sleep(1)
        if now - last_push >= int(device_info['publish_period']):
            aggregate = sf.aggregate(now)
            last_push = now
            if aggregate:
                local_db_con.write_line(aggregate)
            try:
                #todo this should be run first off at boot
                remote_db = RemoteDbMirror(remote_credentials, device_info['name'])
                remote_db.mirror(local_db_con)

            except mysql.connector.errors.InterfaceError:
                logging.warning("No connection to remote db")
            except Exception as e:
                logging.error("Unknown remote db error", e)

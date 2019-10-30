#!/usr/bin/env bash


if [[ $* == *--enable-service* ]]
then
echo "[Unit]
Description=CO2 Logger
Wants=mysqld.service

[Service]
Type=simple
ExecStart=$(which co2_logger_daemon.sh)
RestartSec=5
Restart=always

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/co2_logger.service
    systemctl daemon-reload
    systemctl enable co2_logger.service
    systemctl restart co2_logger.service
    echo "restarting services"
else


# Make sure that NOBODY can access the server without a password
#mysql -e "UPDATE mysql.user SET Password = PASSWORD('CHANGEME') WHERE User = 'root'"

    mysql -e "DROP USER  IF EXISTS ''@'localhost';"
    mysql -e "DROP USER  IF EXISTS ''@'$(hostname)';"
    mysql -e "DROP DATABASE IF EXISTS test;"
    mysql -e "FLUSH PRIVILEGES;"
    mysql -e "CREATE DATABASE IF NOT EXISTS co2_sensors;"
    mysql -e "CREATE USER IF NOT EXISTS 'co2_logger'@'localhost' IDENTIFIED BY 'co2_logger';"
    mysql -e "GRANT ALL PRIVILEGES ON co2_sensors.* TO 'co2_logger'@'localhost';"
    mysql -e "FLUSH PRIVILEGES;"

    co2_logger_daemon.py
fi




#!/usr/bin/env bash


if [[ $* == *--enable-service* ]]
then
echo "[Unit]
Description=Pitally server
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
    echo "restarting pitally services"
else
    python3 co2_logger_daemon.py
fi




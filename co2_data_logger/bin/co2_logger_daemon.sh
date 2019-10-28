#!/usr/bin/env bash


if [[ $* == *--enable-service* ]]
then
echo "[Unit]
Description=Pitally server

[Service]
Type=simple
ExecStart=$(which co2_logger_daemon.sh)
RestartSec=5
Restart=always

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/co2_logger.service
    systemctl daemon-reload
    systemctl enable pitally.service
    systemctl enable pitally_backup.service
    systemctl restart pitally.service
    systemctl restart pitally_backup.service
    echo "restarting pitally services"
else
    python3 co2_logger_daemon.py
fi




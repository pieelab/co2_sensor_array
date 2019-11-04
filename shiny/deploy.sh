rsync -avP -e ssh co2_sensors/ root@${LINODE}:/srv/shiny-server/co2_sensors/ && sleep 5 &&  xdg-open http://${LINODE}/co2_sensors/


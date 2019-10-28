#!/usr/bin/env bash

GIT_REPO=https://github.com/qgeissmann/co2_sensor_array
ZIP_IMG=2019-09-26-raspbian-buster-lite.zip
RASPBIAN_URL=https://downloads.raspberrypi.org/raspbian_lite/images/raspbian_lite-2019-09-30/$ZIP_IMG

OS_IMG_NAME=$(date "+%Y-%m-%d")_os_image.img
MOUNT_DIR=/mnt/pitally_root


# if not in chroot
if [ $(systemd-detect-virt) = 'none' ]
then
    set -e
    wget $RASPBIAN_URL -nc
    unzip -o $ZIP_IMG
    mv *raspbian*.img $OS_IMG_NAME
    IMG_FILE=$(ls *.img)
    DEV="$(losetup --show -f -P "$OS_IMG_NAME")"

    mkdir -p $MOUNT_DIR
    mount ${DEV}p2 $MOUNT_DIR
    mount ${DEV}p1 $MOUNT_DIR/boot

    cp $(which qemu-arm-static) ${MOUNT_DIR}/usr/bin
    cp make_image.sh ${MOUNT_DIR}/root/
    chmod +x ${MOUNT_DIR}/root/make_image.sh

    set +e
    systemd-nspawn  --directory ${MOUNT_DIR} /root/make_image.sh

    umount ${DEV}p1
    umount ${DEV}p2
    losetup -d $DEV

else
    touch /boot/ssh
    apt-get update
    apt-get upgrade --assume-yes
    #fixme hack around small image size
    apt-get clean
    apt-get install tree ipython3 tcpdump nmap  python3-pip iputils-ping mariadb-server git lftp npm --assume-yes
    #fixme hack around small image size
    apt-get clean

    SKIP_WARNING=1 rpi-update

    pip3 install --upgrade pip
    apt-get remove python3-pip --assume-yes

    ## the camera and network are enabled when the machine boots for the first time
mysql -e "CREATE USER 'co2_logger'@'localhost' IDENTIFIED BY 'co2_logger';"
# CREATE DATABASE co2_sensors;
# GRANT ALL PRIVILEGES ON co2_sensors.* TO 'co2_logger'@'localhost';
# FLUSH PRIVILEGES;

    ###
    ## stack
    git clone $GIT_REPO
    cd co2_sensor_array
    pip install -e co2_data_logger

    cd -
    co2_logger_daemon.sh --enable-service
    rm -rf pitally
    exit
fi
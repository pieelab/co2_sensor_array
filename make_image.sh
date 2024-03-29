#!/usr/bin/env bash

GIT_REPO=https://github.com/qgeissmann/co2_sensor_array
ZIP_IMG=2019-09-26-raspbian-buster-lite.zip
RASPBIAN_URL=https://downloads.raspberrypi.org/raspbian_lite/images/raspbian_lite-2019-09-30/$ZIP_IMG


#ZIP_IMG=2019-07-10-raspbian-buster-lite.zip
#RASPBIAN_URL=http://director.downloads.raspberrypi.org/raspbian_lite/images/raspbian_lite-2019-07-12/$ZIP_IMG


OS_IMG_NAME=$(date "+%Y-%m-%d")_os_image.img
MOUNT_DIR=/mnt/pitally_root
MOUNT_DIR_LARGE=/mnt/large_pitally_root


# if not in chroot
if [ $(systemd-detect-virt) = 'none' ]
then
    set -e
    wget $RASPBIAN_URL -nc
    unzip -o $ZIP_IMG
    mv *raspbian*.img $OS_IMG_NAME
    DEV="$(losetup --show -f -P "$OS_IMG_NAME")"
    LARGE_OS_IMG=large_$OS_IMG_NAME
    dd bs=1M count=5200 if=/dev/zero of=$LARGE_OS_IMG
    DEV_LARGE="$(losetup --show -f -P "$LARGE_OS_IMG")"
    dd if=$DEV of=$DEV_LARGE bs=64K conv=noerror,sync status=progress
    losetup -d $DEV

fdisk $DEV_LARGE << EOF
d
2
n
p
532480

N
w
EOF
    e2fsck -f ${DEV_LARGE}p2
    resize2fs ${DEV_LARGE}p2
    mkdir -p $MOUNT_DIR
    mount ${DEV_LARGE}p2 $MOUNT_DIR
    mount ${DEV_LARGE}p1 $MOUNT_DIR/boot

    cp $(which qemu-arm-static) ${MOUNT_DIR}/usr/bin
    cp make_image.sh ${MOUNT_DIR}/root/
    chmod +x ${MOUNT_DIR}/root/make_image.sh

    set +e
    systemd-nspawn  --directory ${MOUNT_DIR} /root/make_image.sh

    umount ${DEV_LARGE}p1
    umount ${DEV_LARGE}p2
    losetup -d $DEV_LARGE

else
    mv /etc/ld.so.preload /etc/bak-ld.so.preload
    touch /boot/ssh
    apt-get update
    apt-get upgrade --assume-yes
    apt-get install tree ipython3 libatlas-base-dev tcpdump nmap python3-pip iputils-ping  git lftp npm  mariadb-server watchdog --assume-yes
    SKIP_WARNING=1 rpi-update

    pip3 install --upgrade pip
    apt-get remove python3-pip --assume-yes


    ###
    ## stack
    git clone $GIT_REPO
    cd co2_sensor_array
    pip install -e co2_data_logger

    cd -

    cp watchdog.conf  /etc/watchdog.conf # test internet
    systemctl enable watchdog

    cp co2_sensor_array/co2_data_logger.conf  /etc/co2_data_logger.conf
    nano /etc/co2_data_logger.conf


    cp co2_sensor_array/wpa_supplicant-wlan0.conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
    nano /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
#    cat /etc/systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service | sed s/nl80211,//g > /tmp/wpa_supplicant@wlan0.service && mv /tmp/wpa_supplicant@wlan0.service /etc/systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service
    cat /lib/systemd/system/wpa_supplicant@.service | sed s/nl80211,//g > /tmp/wpa_supplicant@wlan0.service && mv /tmp/wpa_supplicant@wlan0.service  /lib/systemd/system/wpa_supplicant@.service

    systemctl disable  wpa_supplicant
    systemctl enable  wpa_supplicant@wlan0.service

    co2_logger_daemon.sh --enable-service

#    rm -rf pitally
    exit

    #todo
    #* set wifi
    #* edit /etc/co2_data_logger.conf:
      #* Env => production
      #* lut change
      #* device name change

fi

#eduroam





# eduroam does not work with the new wpa driver
#sudo systemctl enable wpa_supplicant@.service
## keep only the wext driver
#sudo nano /etc/systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service


#to clone: dd if=/dev/sda   bs=64K conv=noerror,sync status=progress | gzip -c  > ./2019-10-29_pi_clone.img.gz
# to restore: gunzip -c ./2019-10-29_pi_clone.img.gz | dd of=/dev/sda bs=64K conv=noerror,sync status=progress



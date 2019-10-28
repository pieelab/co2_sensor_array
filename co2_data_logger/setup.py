from setuptools import setup, find_packages
exec(open('co2_data_logger/_version.py').read())

setup(
    name='co2_data_logger',
    version=__version__,
    long_description=__doc__,
    packages=find_packages(),
    scripts=['bin/co2_logger_daemon.sh', 'bin/co2_logger_daemon.py'],
    include_package_data=True,
    zip_safe=False,
    install_requires=["numpy", "mysql-connector", "pyserial", "configparser"],
    extras_require={
        # 'production': ['mysql'],
        # 'server': ['Flask', "netifaces", 'flask_cors', "scapy~=2.4.3rc1"],
        # 'hardware': ['pyserial']
    },
)
"""
This a small python program to collect, save and visualise data from the serial port in real time.
Each data point is a scalar number.
Consecutive data points result in a time series that is assumed to be irregular (i.e. heterogeneous).
"""

__author__ = "Quentin Geissmann, [http://github.com/qgeissmann]"


import os
import time
# In order to read from serial port
import serial
# Command line argument parsing
import argparse
# For basic linear algebra
import numpy as np
# To have a queue (FIFO) of values
from collections import deque
# Plotting the data
import pygame

import sys
import glob



_N_POINTS = 200
_COLOUR_MAP = [(255, 255, 0),
               (0, 255, 255),
               (255, 0, 255),
               (0, 0, 255),
               (0, 255, 0),
               (255, 0, 0),
               ]
DISPLAY_WIDTH, DISPLAY_HEIGHT = 1200, 520


def plot(screen, time_queue, value_queue, window_size):
    """
    The function to draw new data on a window.
    Calling repetitively this function, with new data, will display a dynamic "scrolling" plot.
    The y axis if for the values (value_queue) and the x axis is for time.
    The most recent values are plotted on the right most part of the window, whilst the
    oldest ones are on the left (until they eventually "leave" the screen)

    :param screen: The display window to draw on
    :param time_queue: A collection of time stamps
    :param value_queue:  A collection of y values matching time stamps.
    :param window_size:  The duration (in seconds) corresponding to the width of the window.

    """
    # time
    t = np.array(list(time_queue))
    # y values
    values = np.array(list(value_queue), dtype=np.float32)
    # We scale the signal so that all values lie between 0 and 1

    new_y = values - np.min(values,0)
    # the maximal value in y
    mmax = np.max(new_y, 0)
    # we ensure no division by 0 can happen

    if np.any(mmax == 0):
        print("avoiding div by 0; not plotting")
        return
    # after that new_y is between 0 and 1
    new_y /= np.max(new_y, 0)

    # flip
    new_y = 1. - new_y

    ncols = new_y.shape[1]
    # Now, we scale new_y to the fit int the plotting window
    new_y *= DISPLAY_HEIGHT / ncols
    new_y += DISPLAY_HEIGHT * np.arange(ncols)/ncols



    #we express time as a proportion of the window size
    new_t = t - t[0]
    new_t *= (DISPLAY_WIDTH/float(window_size))

    # Clear the window (filling with black)
    screen.fill((0, 0, 0))
    # Display some text
    font = pygame.font.Font(None, 36)

    for c in range(ncols):
        y = new_y[:, c]
        # Creating points (i.e. `x,y` tuples of int values)
        pts = [(int(x), int(y)) for x,y in zip(new_t, y)]
        # Then drawing in yellow

        ymin = c * DISPLAY_HEIGHT/ncols

        p1, p2 = (0, ymin), (DISPLAY_WIDTH, ymin)
        pygame.draw.aalines(screen, (128, 128, 128), False, [p1, p2])
        pygame.draw.lines(screen, _COLOUR_MAP[c], False, pts, 3)

        mean_y = round(np.mean(values[:, c]), 3)
        sd_y = round(np.std(values[:, c]), 3)

        text = font.render(str((value_queue[-1],mean_y, sd_y)), 1, (255, 255, 255))

        screen.blit(text, (0,ymin))

    pygame.display.flip()



def serial_ports():
    """Lists serial ports, from:
    http://stackoverflow.com/questions/12090503/listing-available-com-ports-with-python

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
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
    return result


if __name__ == "__main__":
    
    program_start = time.time()
    # parsing command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', help='port', type=str, default=None)
    parser.add_argument('--set-datetime', help='Set the datetime in the arduino RTC', type=int, default=program_start)
    parser.add_argument('--vws', help='The duration of the viewing window (s)', type=int, default=20)
    parser.add_argument('--out', help='An optional output file', type=str, default=os.devnull)
    parser.add_argument('--baud', help='The baud rate of the serial port', type=int, default=57600)

    args = parser.parse_args()
    arg_dict = vars(args)
    window_size = arg_dict["vws"]
    out_file = arg_dict["out"]
    baud = arg_dict["baud"]
    print(arg_dict)
    set_datetime = arg_dict["set_datetime"]

    # Here we open the serial port
    port = arg_dict["port"]
    if port is None:
        print("Scanning serial ports...")
        ports = serial_ports()
        if len(ports) == 0:
            raise Exception("No serial port found. "
                            "Ensure your device is plugged. You ab also explicitly use the option `--port`")
        elif len(ports) > 2:
            print("%i serial ports found:\n %s" % (len(ports), "\n\t".join(ports)))
        port = ports[0]
        print("Using %s " % port)


    serial_port = serial.Serial(port, baud, timeout=2)
    # while serial_port.readline().rstrip() == "":
    #     time.sleep(1)
    #     print("Waiting for loop")

    # We start a timer using the real time from the operating system
    start = 0
    
    # Then we make two queues (FIFO containers); one for the values and one for the time stamps
    time_queue, value_queue = deque(), deque()

    # We need to initialise pygame
    pygame.init()

    # We build the pygame window before we can start painting inside
    display = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT))
    # Let us set the window name as well
    pygame.display.set_caption('Smart trap Monitor')
    
    # The `with statement` will ensure the file is closed properly, should any exception happen
    with open(out_file, "w") as f:
        try:
            # Header of a csv like file
            # f.write("t, y\n")

            # Infinite loop
            while True:
                # we read a line from serial port and remove any `\r` and `\n` character
                line = serial_port.readline()

                if not line:
                    continue
                line = line.rstrip()
                print(line)

                if line.startswith(b"#") or line.startswith(b"t"):
                    print(line)
                    continue

                # continue
            # Just after, we get a time stamp
                now = time.time()
                # we try to convert the line to an integer value
                try:
                    values = [float(v) for v in line.split(b',') if v]
                   # value = float(line)
                   #  now = float(values.pop(0)) / 1e3
                   #  temperature = float(values.pop(0))
                   #  rel_humidity = float(values.pop(0))
                # If something goes wrong, we do not stop, but we print the error message
                except ValueError as e:
                    print(e)
                    continue
                except IndexError as e:
                    print(e)
                    continue
                # The relative time from the start of the program is `dt`
                dt = now - start

                # We write a formatted line to the end of the result file
                f.write("%f,%s\n" % (now, line))

                # We append relative time and value to their respective queues
                time_queue.append(dt)
                value_queue.append(values)

                # We wait to have at least five points AND three seconds of data
               # print((now, values))
                if time_queue[-1] < 3 or len(time_queue) < 5:
                    continue

                # Now, we remove/forget from the queues any value older than the window size
                # This way. we will only plot the last n (default 20) seconds of data
                while time_queue[-1] - time_queue[0] > window_size:
                    time_queue.popleft()
                    value_queue.popleft()

                # Now we plot the values
                plot(display, time_queue, value_queue, window_size)

                # So that the program stops if we close the window
                for et in pygame.event.get():
                    if et.type == pygame.QUIT:
                        raise KeyboardInterrupt

        except KeyboardInterrupt:
            print("Interrupting program...")

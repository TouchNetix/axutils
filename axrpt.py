#!/usr/bin/env python3
################################################################################
#                                    NOTICE
#
# Copyright (c) 2010 - 2021 TouchNetix Limited
# ALL RIGHTS RESERVED.
#
# The source  code contained  or described herein  and all documents  related to
# the source code ("Material") are owned by TouchNetix Limited ("TouchNetix") or
# its suppliers  or licensors. Title to the Material  remains with TouchNetix or
# its   suppliers  and  licensors. The  Material  contains  trade  secrets   and
# proprietary  and confidential information  of TouchNetix or its  suppliers and
# licensors.  The  Material  is  protected  by  worldwide  copyright  and  trade
# secret  laws and  treaty  provisions.  No part  of the Material  may be  used,
# copied,  reproduced,  modified,   published,  uploaded,  posted,  transmitted,
# distributed or disclosed in any way without TouchNetix's prior express written
# permission.
#
# No  license under any  patent, copyright,  trade secret or other  intellectual
# property  right is granted to or conferred upon you by disclosure or  delivery
# of  the Materials, either  expressly, by implication, inducement, estoppel  or
# otherwise.  Any  license  under  such  intellectual  property rights  must  be
# expressly approved by TouchNetix in writing.
#
################################################################################

import sys
import argparse
from axiom_tc import axiom

U34_TARGET_ADDRESS = 0x0800
U34_READ_LENGTH = 58

def axiom_init(args, verbose=False):
    if args.i == "i2c":
        if args.i2c_bus == None or args.i2c_address == None:
            print("The I2C bus and the I2C address arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.I2C_Comms import I2C_Comms
            comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    elif args.i == "spi":
        if args.spi_bus == None or args.spi_device == None:
            print("The SPI bus and the SPI device arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.SPI_Comms import SPI_Comms
            comms = SPI_Comms(args.spi_bus, args.spi_device)

    elif args.i == "usb":
        from axiom_tc.USB_Comms import USB_Comms
        comms = USB_Comms(verbose)

    ax = axiom(comms, verbose=verbose)

    # Dummy read to purge anything left in the u34 FIFO buffer
    comms.read_page(U34_TARGET_ADDRESS, U34_READ_LENGTH)

    return ax, comms

def decode_and_process_report(report):
    if report[1] == 0x01:
        decode_u01(report[2:])
    elif report[1] == 0x41:
        decode_u41(report[2:])
    elif report[1] == 0x4C:
        decode_u4C(report[2:])
    elif report[1] == 0x45:
        decode_u45(report[2:])

def gpio_interrupt(channel):
    decode_and_process_report(comms.read_page(U34_TARGET_ADDRESS, U34_READ_LENGTH))

def decode_u41(report):
    #print "Touch Report"
    #print(" ".join("{:02x}".format(num) for num in report))
    #pass
    target_status = (report[0]) + ((report[1] & 0x03) << 8)
    ae_error = (report[1] & 0x80) >> 7

    for t in range(0,10):
        # X & Y
        offset = (t * 4) + 2
        x = report[offset + 0] + (report[offset + 1] << 8)
        y = report[offset + 2] + (report[offset + 3] << 8)

        # Z
        offset = (t * 1) + 42
        z = report[offset]

        if target_status & (1 << t) != 0:
            print("(T{0}: {1:>5},{2:>5},{3:>4}) ".format(t, x, y, z), end='')
        elif target_status != 0:
            print("                       ", end='')

    if target_status != 0:
        print("")

    timestamp = report[52] + (report[53] << 8)
    checksum  = report[54] + (report[55] << 8)

    #print(str(timestamp))

def decode_u01(report):
    #print "Heartbeat Report"
    #print(" ".join("{:02x}".format(num) for num in report))
    pass

def decode_u4C(report):
    #print("u4C Report")
    #print(" ".join("{:02x}".format(num) for num in report))
    pass

def decode_u45(report):

    hotspot_number = report[0]
    contact_number = report[1]
    qualification_number = report[2]
    reason = report[3]
    decoded_reason = "invalid"

    match reason:
        case 0:
            decoded_reason = "ENTERED"
        case 1:
            decoded_reason = "EXITED"
        case 2:
            decoded_reason = "PRESSED"
        case 3:
            decoded_reason = "RELEASED"
        case 4:
            decoded_reason = "MOVED"
        case 5:
            decoded_reason = "ENTERED AND PRESSED"
        case 6:
            decoded_reason = "EXITED AND RELEASED"
        case 7:
            decoded_reason = "APPROACHED"
        case 8:
            decoded_reason = "RETREATED"
    
    print(f"Contact {contact_number} has {decoded_reason} hotspot {hotspot_number}, qualification {qualification_number}")
    print("")
        

def main_loop_polled(comms):
    try:
        while True:
            # Poll for reports (not great, but the best we can do without an
            # interrupt from nIRQ). Extract the report, and remove the first 2
            # bytes and send it onto a function to decode accordingly
            # TODO: Read out u34 TA and max report length
            decode_and_process_report(comms.read_page(U34_TARGET_ADDRESS, U34_READ_LENGTH))

    except KeyboardInterrupt:
        # Attempt to exit safely
        ax.close()
        sys.exit(0)

def main_loop_interrupts():
    try:
        while True:
            # Do nothing.... wait for CTRL+C
            pass
    except KeyboardInterrupt:
        pass

    GPIO.cleanup()
    ax.close()
    sys.exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Utility to load aXiom config files onto a device')
    parser.add_argument("-i", help='Comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    parser.add_argument("--gpioint", help='RPi only. If not specified, the reports will be polled, otherwise a GPIO interrupt will be used instead', required=False, action='count', default=0)
    args = parser.parse_args()

    ax, comms = axiom_init(args)

    # Check to see if we are going to be polling for report or using a GPIO interrupt
    if args.gpioint > 0:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(24, GPIO.FALLING, callback=gpio_interrupt, bouncetime=1)

    if args.gpioint > 0:
        main_loop_interrupts()
    else:
        main_loop_polled(comms)

    # Finally, close the connection if it is still open
    ax.close()
    sys.exit(0)

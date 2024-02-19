# Copyright (c) 2024 TouchNetix
# 
# This file is part of [Project Name] and is released under the MIT License: 
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import argparse
from version import __version__
from axiom_tc.USB_Comms import USB_Comms

BridgeMode_TBPBasic = 0
BridgeMode_TBPDigitizer = 1
BridgeMode_TBPAbsoluteMouse = 2

TBP_MODES = {
    'tbp'   : BridgeMode_TBPBasic,
    'digi'  : BridgeMode_TBPDigitizer,
    'mouse' : BridgeMode_TBPAbsoluteMouse
}

TBP_MODE_PID = dict(zip(USB_Comms.PRODUCT_ID, TBP_MODES.keys()))

description_string = 'Utility to change the operating mode of a TNx USB Protocol Bridge.\nIf no argument given program prints the current mode.'
help_string = 'mode to set the Protocol Bridge into.'

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=description_string)
    parser.add_argument("-m", help=help_string, choices=TBP_MODES.keys(), \
                        required=False, default='', type=str)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    comms = USB_Comms()
    print("Current TNx USB Bridge mode: " + TBP_MODE_PID[comms.pid])
    current_mode = TBP_MODES[TBP_MODE_PID[comms.pid]]

    try:
        requested_mode = TBP_MODES[args.m]
        if (requested_mode != current_mode):
            OutBuffer = list(USB_Comms.EMPTY_PKT)
            if requested_mode == BridgeMode_TBPBasic:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFA
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x00
            elif requested_mode == BridgeMode_TBPDigitizer:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFE
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x00
            elif requested_mode == BridgeMode_TBPAbsoluteMouse:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFF
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x01
                OutBuffer[4] = 0x01  # X scaling multiplier low byte
                OutBuffer[5] = 0x00  # X scaling multiplier high byte
                OutBuffer[6] = 0x01  # X scaling divisor low byte
                OutBuffer[7] = 0x00  # X scaling divisor high byte
                OutBuffer[8] = 0x01  # Y scaling multiplier low byte
                OutBuffer[9] = 0x00  # Y scaling multiplier high byte
                OutBuffer[10] = 0x01  # Y scaling divisor low byte
                OutBuffer[11] = 0x00  # Y scaling divisor high byte

            comms.stop_bridge()
            comms.write_device(bytes(OutBuffer))
            buffer = []
            while (len(buffer) != 0):
                buffer = comms.read_device()
            print("Changed bridge mode to " + args.m)

    except(KeyError):
        print("TNx USB Bridge in mode: " + TBP_MODE_PID[comms.pid])





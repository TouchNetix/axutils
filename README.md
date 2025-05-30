# axutils - aXiom Utilities

Reference code in this section is provided to demonstrate how small tools can be created to handle different maintenance operations of an aXiom Device.

## Firmware Downloads

`axfw.py` uploads a new firmware image onto an aXiom device.

```console
python axfw.py -i usb ax112a_3D_rt_rMMmmpp_prod.axfw
```

## Configuration Updates

`axcfg.py` uploads a binary configuration file to an aXiom device. Binary configuration files are created by TouchHub2.

```console
python axcfg.py -i i2c --i2c-bus 1 --i2c-address 0x66 ax112a_loa.th2cfgbin
```

## View an aXiom Device's Usage Table

`axut.py` queries an aXiom device and reports firmware version information as well as the usage table. This is a useful check that aXiom is available without making changes to the device.

```console
python axut.py -i usb
```

## View aXiom reports

`axrpt.py` provides example code to read reports from aXiom in either a polled or interrupt driven scheme. A Raspberry Pi is required for this interrupt driven example to function.

Depending on the system this is being run on, the reports can be polled or interrupt driven (preferred).

This example uses a RPi GPIO 24 as an interrupt to read touch reports (u41) from aXiom
```console
python axrpt.py -i spi --spi-bus 0 --spi-device 0 --gpioint 24 --reports 0x41 
```

This is a polled example (typical for Windows systems):
```console
python axrpt.py -i usb 
```

## Extract factory data from an aXiom device

`axfactdata.py` reads out the aXiom device's factory data.

## Control a Protocol Bridge's Mode

`axtbp.py` can be used to change the mode (Basic, Digitizer, Absolute Mouse) of the provided USB protocol bridge.

## Interface options

`interface_arg_parser.py` helper functions to parse script arguments. Specifically, it handles the interface (I2C, SPI, USB) options so that all scripts have a consistent interface.

# Prerequisites

Requires Python 3.8 to be installed and accessible on the Path variable.

Prerequisites can be installed via the `requirements.txt`:

```console
pip install -r requirements.txt
```

### axiom_tc Package

This is the aXiom touch controller python package that provides access to core functionality and communication to the aXiom device. In conjunction with the `axiom_tc` package, the appropriate interface packages are expected to be available. These are described after this section.

Requires `axiom_tc` to be installed and accessible to your Python interpreter.

```console
pip install axiom_tc
```

### SPI Interface

Requires `spidev` to be installed and accessible to your Python interpreter.

```console
pip install spidev
```

See [spidev](https://pypi.org/project/spidev/) for more information.

### I2C Interface

Requires `smbus2` to be installed and accessible to your Python interpreter.

```console
pip install smbus2
```

See [smbus2](https://pypi.org/project/smbus2/) for more information.

### USB Interface

Requires `hid` to be installed and accessible to your Python interpreter.

```console
pip install hid==1.0.4
```

See [hid](https://pypi.org/project/hid/) for more information.

#### Linux

Using the `hid` package will access the TouchNetix protocol bridges via the `/dev/hidrawX` interface. This typically requires root access. This means the scripts will need to be run as `sudo`. Alternatively, `udev` can be used to give all users permissions to the `hidraw` devices.

Create the following `udev` rules file `/etc/udev/rules.d/99-axiom-hidraw-permissions.rules`:

```text
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="6f02", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2f04", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="03eb", ATTRS{idProduct}=="2f08", MODE="0666"

SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="6f02", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="2f04", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="2f08", MODE="0666"

SUBSYSTEM=="hidraw", ATTRS{idVendor}=="28e9", ATTRS{idProduct}=="6f02", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="28e9", ATTRS{idProduct}=="2f04", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="28e9", ATTRS{idProduct}=="2f08", MODE="0666"
```

The changes will apply on the next reboot. To apply the changes immediately:

```console
sudo udevadm control --reload-rules
sudo udevadm trigger
```

If this error message is observed:

```console
ImportError: Unable to load any of the following libraries:libhidapi-hidraw.so libhidapi-hidraw.so.0 libhidapi-libusb.so libhidapi-libusb.so.0 libhidapi-iohidmanager.so libhidapi-iohidmanager.so.0 libhidapi.dylib hidapi.dll libhidapi-0.dll
```

Run the following to install the `hidapi` library.

```console
sudo apt-get install libhidapi-hidraw0 libhidapi-libusb0
```

#### Windows

Windows requires the `hidapi.dll` files to reside in the same directory as Python (see more info [here](https://github.com/abcminiuser/python-elgato-streamdeck/issues/56))
The `.dll` files can be found [here](https://github.com/libusb/hidapi/releases)

### RPi.GPIO

When using `axrpt`, it can be configured to use a GPIO for interrupts. This will only work on a Raspberry Pi and will require the `RPi.GPIO` package to generate the interrupt based on a GPIO pin transition.

```console
pip install RPi.GPIO
```

## Usage

Each of the python scripts can be interrogated for correct usage. Use the `--help` option, e.g:

```console
axfw.py --help
```

## File Format Structures

### Firmware Files

There are two formats of the aXiom firmware files; `.axfw` and `.alc`. The `.axfw` format includes some additional meta data to identify the target device and what firmware version it contains. `.alc` is the old format that just includes the firmware.

The additional meta data in the `.axfw` can be used to ensure the new firmware is for the correct device. It also contains firmware version information which can be used to prevent unnecessary downloads.

#### axfw

This table describes the meta data stored in the header section of the `.axfw` files.

| Byte(s) | Description             | Notes                                                 |
| :---:   | :----                   | :---                                                  |
| 0-3     | File Signature          | ASCII `'AXFW'`                                        |
| 4-7     | .axfw CRC               | CRC32 value of the .axfw file from offset 8 onwards   |
| 8-9     | File Format Version     | Little Endian                                         |
| 10-11   | Device ID               | Little Endian, see list of Device IDs below           |
| 12      | Firmware Variant        | See list of Firmware Variants below                   |
| 13-14   | Firmware Version        | Little Endian                                         |
| 15      | Firmware Patch Number   | Patch Number of the Firmware Release                  |
| 16      | Firmware Status         | See list of Firmware Status below                     |
| 17-18   | Silicon Version         | See list of Silicon Versions below                    |
| 19      | Silicon Revision        | Revision of the silicon                               |
| 20-23   | Firmware CRC            | CRC of the firmware                                   |

The remaining content is the payload that needs to be chunked up before sending to the aXiom bootloader. All of the bytes specified below are located immediately after the meta data section (i.e. add 16 bytes to all the offsets specified).

| Byte(s)  | Description   | Notes                                         |
| :---:    | :----         | :---                                          |
| 0-7      | Chunk Header  | Bytes 6 and 7 contain the length of the chunk |
| 8-Length | Chunk Payload | Payload data                                  |

The data to be sent is the entire chunk, including the header. The information on extracting the length is to help identify where the next payload is located in the file.

#### List of Device IDs

* `0x0036` - AX54A
* `0x0050` - AX80A
* `0x0070` - AX112A
* `0x00C6` - AX198A

#### List of Firmware Variants

* `0` - 3D, fully featured
* `1` - 2D, only basic touch features
* `2` - Force, force only

#### List of Silicon Versions

* `0x001F` - AX112A
* `0x002F` - AX54A, AX80A
* `0x003F` - AX198A

#### List of Firmware Status

* `0` - Engineering
* `1` - Production

#### alc

`.alc` files are the same as `.axfw` files, just without the meta data section. See the axfw section for a description on how the payloads are structured.

### Configuration Files

aXiom config files are exported from TouchHub2 as `.th2cfgbin` files. The data structure for this file type is specified in the table below.

This table describes the meta data stored in the header section of the `.th2cfgbin` files.

| Byte(s) | Description             | Notes        |
| :---:   | :----                   | :---         |
| 0-3     | File Signature          | `0x20071969` |
| 4-5     | File Format Version     | `0x0001`     |
| 6-7     | TCP File Revision Major |              |
| 8-9     | TCP File Revision Minor |              |
| 10-11   | TCP File Revision Patch |              |
| 12      | TCP Version             |              |

The remaining content of the config file is the data that needs to be written to aXiom. The config data is split into usages. Each usage is packed contiguously, and can be navigated by reading the usage length fields.

| Byte(s)  | Description    | Notes                                     |
| :---:    | :----          | :---                                      |
| 0        | Usage Number   | The usage identifier                      |
| 1        | Usage Revision | The revision of the usage                 |
| 2        | Padding        | Reserved for future use                   |
| 3-4      | Usage Length   | Length of usage contents, *Little Endian* |
| 5-Length | Usage Content  | Binary content of the usage               |

*Note:* It is generally recommended to not write to u04 (Customer Data) as the intended purpose of this field is for customers to store data like serial numbers, part numbers etc. Writing to u04 will lose this information.

### Linux Kernel Module Driver Compatibility

The `axutils` scripts are meant to be used on a system running aXiom devices. However, depending on the software stack and communication interface used this may not always be completely possible, as detailed on the following table:

| Comms  | Driver Stack | Compatible            |
| :----: | :---         | :---                  |
| USB    | Linux Kernel | Yes                   |
| SPI    | Linux Kernel | Without driver loaded |
| I2C    | Linux Kernel | Without driver loaded |

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

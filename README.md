> A Python script to control this [bluetooth LED light strip](https://www.amazon.com/gp/product/B07BFWPGLW).

Tested with: Python 3.9 on Windows and Mac OS

## Requirements:

- bleak (https://github.com/hbldh/bleak) for bluetooth communication with the LED strip
- MSS (https://github.com/BoboTiG/python-mss) for screen capture
- Pillow (https://python-pillow.org/) for image processing
- colour (https://github.com/vaab/colour) for color manipulations

## Usage:

To discover the bluetooth address of the LED light strip, run:

```shell
python scanner.py
```

which will list the address and name of nearby devices.

To control the device, run:

```shell
python control.py  --address ADDRESS [--demo] [--interval INTERVAL]
```

where:

- `--address ADDRESS`, `-a ADDRESS`: bluetooth mac address of light strip
- `--demo`, `-d`: use in demo mode (cyclic rainbow)
- `--interval INTERVAL`, `-i INTERVAL`: color update interval (secs)

If `--demo` is not set, the script will capture the dominant screen color of the machine in which the script is being
invoked, and set that color to the light strip at the provided fixed time interval.

## Method

I followed the instructions
on [this post](https://www.instructables.com/Reverse-Engineering-Smart-Bluetooth-Low-Energy-Dev/) to discover the BLE
control characteristics of the light strip by using the official Android app and then checking the BLE communication
logs via Wireshark. 
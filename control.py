import argparse
import asyncio
import logging
import time
import mss
import itertools as it
import numpy as np
from typing import Tuple
from colour import Color
from PIL import Image
from bleak import BleakClient
from mss.base import MSSBase

POWER_ON_CODE = 'cc2333'
POWER_OFF_CODE = 'cc2433'
UUID_CONTROL_CHARACTERISTIC = '0000ffd9-0000-1000-8000-00805f9b34fb'

SCREEN_REDUCE_RATIO = 0.25  # ratio of screen pixels from which to compute border color
SCREEN_BORDER_PIXEL_RATIO = 0.1  # ratio of screen pixels used for color calculation

DEMO_BASE_COLORS = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'violet', 'red']
DEMO_BASE_COLORS = [Color(c) for c in DEMO_BASE_COLORS]
DEMO_UPDATE_INTERVAL = 0.5  # color change interval, in seconds
DEMO_TRANSITION_NUM_COLORS = 10  # number of colors to create the cycle
DEMO_COLORS = list(it.chain(*[list(DEMO_BASE_COLORS[i].range_to(DEMO_BASE_COLORS[i + 1], DEMO_TRANSITION_NUM_COLORS))
                              for i in range(len(DEMO_BASE_COLORS) - 1)]))

DEF_INTERVAL = 1  # update color in seconds


async def change_color(client: BleakClient, rgb_color: Tuple[int, int, int]):
    """
    Changes the color of the light strip.
    :param client: the Bleak client connected to the light strip.
    :param rgb_color: the RGB color to be set, in red, green, blue component format.
    """
    logging.info(f'Changing light strip color to: {rgb_color}')
    r, g, b = rgb_color
    hex_color = f'{r:02x}{g:02x}{b:02x}'
    data = bytes.fromhex(f'56{hex_color}00f0aa')
    await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, data, response=True)


async def change_power(client: BleakClient, status: bool):
    """
    Changes the power status of the light strip.
    :param client: the Bleak client connected to the light strip.
    :param status: the status to be set, `True` to turn on the light strip, `False` to turn it off.
    """
    logging.info(f'Turning light strip {"on" if status else "off"}')
    data = bytes.fromhex(POWER_ON_CODE if status else POWER_OFF_CODE)
    await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, data, response=True)


async def demo_mode(client: BleakClient):
    """
    Puts the light strip in demo mode, corresponding to changing the color cyclically.
    :param client: the Bleak client connected to the light strip.
    """
    logging.info('Entering DEMO mode...')
    for color in it.cycle(DEMO_COLORS):
        await change_color(client, color)
        time.sleep(DEMO_UPDATE_INTERVAL)


def _compute_screen_color(sct: MSSBase) -> Tuple[int, int, int]:
    logging.info('Computing screen color...')

    # get screenshot
    img = sct.grab(sct.monitors[1])
    img = Image.frombytes('RGB', img.size, img.bgra, 'raw', 'BGRX')

    # reduce image
    img = img.resize((int(img.width * SCREEN_REDUCE_RATIO), int(img.height * SCREEN_REDUCE_RATIO)))

    # get borders
    border_height = int(img.height * SCREEN_BORDER_PIXEL_RATIO)
    border_width = int(img.width * SCREEN_BORDER_PIXEL_RATIO)
    border = min(border_width, border_height)
    top_img = img.crop((0, 0, img.width, border))
    bottom_img = img.crop((0, img.height - border, img.width, img.height))
    left_img = img.crop((0, border, border, img.height - border))
    right_img = img.crop((img.width - border, border, img.width, img.height - border))

    # get mean color of all borders
    colors = [np.mean(i, axis=(0, 1), dtype=np.uint) for i in [top_img, bottom_img, left_img, right_img]]
    color = np.mean(colors, axis=0, dtype=np.uint)
    return tuple(color)


async def _update_color_from_screen(client: BleakClient, interval: float):
    with mss.mss() as sct:
        logging.info('Entering screen color mode...')
        _prev_color = None
        while True:
            color = _compute_screen_color(sct)
            if _prev_color != color:
                await change_color(client, color)
                _prev_color = color
            time.sleep(interval)


async def main():
    parser = argparse.ArgumentParser('Bluetooth LE light strip color changer')
    parser.add_argument('--address', '-a', type=str, required=True, help='Bluetooth mac address of light strip')
    parser.add_argument('--demo', '-d', action='store_true', help='Use in demo mode')
    parser.add_argument('--interval', '-i', type=float, default=DEF_INTERVAL, help='Color update interval (secs)')
    args = parser.parse_args()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler('bt_lights.log', mode='w+'), stream_handler])

    logging.info(f'Connecting to light strip at address: {args.address}...')
    async with BleakClient(args.address) as client:
        logging.info('Connected')
        if args.demo:
            await demo_mode(client)
        else:
            await _update_color_from_screen(client, args.interval)


if __name__ == '__main__':
    asyncio.run(main())

import argparse
import asyncio
import logging
import time
import bleak
import mss
import itertools as it
from bleak import BleakClient
from colour import Color
from PIL import Image
from mss.base import MSSBase

POWER_ON_CODE = 'cc2333'
POWER_OFF_CODE = 'cc2433'
UUID_CONTROL_CHARACTERISTIC = '0000ffd9-0000-1000-8000-00805f9b34fb'

SCREEN_REDUCE_RATIO = 0.1  # ratio of screen pixels from which to compute border color
SCREEN_NUM_COLORS = 16  # num colors for quantization

DEMO_BASE_COLORS = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'violet', 'red']
DEMO_BASE_COLORS = [Color(c) for c in DEMO_BASE_COLORS]
DEMO_TRANSITION_NUM_COLORS = 100  # number of colors to create the cycle
DEMO_COLORS = list(it.chain(*[list(DEMO_BASE_COLORS[i].range_to(DEMO_BASE_COLORS[i + 1], DEMO_TRANSITION_NUM_COLORS))
                              for i in range(len(DEMO_BASE_COLORS) - 1)]))

DEF_INTERVAL = 0.1  # update color in seconds
RETRY_INTERVAL = 5  # retry connection interval in seconds


async def change_color(client: BleakClient, color: Color):
    """
    Changes the color of the light strip.
    :param client: the Bleak client connected to the light strip.
    :param color: the RGB color to be set, in red, green, blue component format.
    """
    logging.debug(f'Changing light strip color to: {color}')
    color = list(color.rgb)
    r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
    hex_color = f'{r:02x}{g:02x}{b:02x}'
    data = bytes.fromhex(f'56{hex_color}00f0aa')
    await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, data, response=True)


async def change_power_status(client: BleakClient, status: bool):
    """
    Changes the power status of the light strip.
    :param client: the Bleak client connected to the light strip.
    :param status: the status to be set, `True` to turn on the light strip, `False` to turn it off.
    """
    logging.info(f'Turning light strip {"on" if status else "off"}')
    data = bytes.fromhex(POWER_ON_CODE if status else POWER_OFF_CODE)
    await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, data, response=True)


async def demo_mode(client: BleakClient, interval: float):
    """
    Puts the light strip in demo mode, corresponding to changing the color cyclically.
    :param client: the Bleak client connected to the light strip.
    :param interval: the time interval to update the color of the light strip, in seconds.
    """
    logging.info('Entering DEMO mode...')
    await change_power_status(client, status=True)  # make sure it's on
    for color in it.cycle(DEMO_COLORS):
        await change_color(client, color)
        time.sleep(interval)


async def ambient_mode(client: BleakClient, interval: float):
    """
    Puts the light strip in ambient mode, which updates the color of the LEDs according to the average color of the
    main screen's edges/border.
    :param client: the Bleak client connected to the light strip.
    :param interval: the time interval to update the color of the light strip, in seconds.
    """
    with mss.mss() as sct:
        logging.info('Entering screen color mode...')
        _prev_color = None
        while True:
            color = _get_dominant_screen_color(sct)
            if _prev_color != color:
                await change_color(client, color)
                _prev_color = color
            time.sleep(interval)


def _get_dominant_screen_color(sct: MSSBase) -> Color:
    logging.debug('Computing dominant screen color...')

    # get screenshot
    img = sct.grab(sct.monitors[1])
    img = Image.frombytes('RGB', img.size, img.bgra, 'raw', 'BGRX')

    # reduce image and colors, get most dominant color (see: https://stackoverflow.com/a/61730849/16031961)
    img.thumbnail((int(img.width * SCREEN_REDUCE_RATIO), int(img.height * SCREEN_REDUCE_RATIO)))
    img = img.convert('P', palette=Image.ADAPTIVE, colors=SCREEN_NUM_COLORS)
    palette = img.getpalette()
    color_counts = sorted(img.getcolors(), reverse=True)
    palette_index = color_counts[0][1]
    color = palette[palette_index * 3:palette_index * 3 + 3]

    # correct luminance for maximum color brightness
    color = Color(rgb=(color[0] / 255., color[1] / 255., color[2] / 255.))
    color = list(color.hsl)
    color[2] = 0.5
    color = Color(hsl=color)
    return color


async def main():
    parser = argparse.ArgumentParser('Bluetooth LE light strip color changer')
    parser.add_argument('--address', '-a', type=str, required=True, help='Bluetooth mac address of light strip')
    parser.add_argument('--demo', '-d', action='store_true', help='Use in demo mode')
    parser.add_argument('--interval', '-i', type=float, default=DEF_INTERVAL, help='Color update interval (secs)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Logging level, INFO if true, DEBUG if false')
    parser.add_argument('--log', '-l', action='store_true', help='Whether to log events to file')
    args = parser.parse_args()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    handlers = [stream_handler] + (logging.FileHandler('bt_lights.log', mode='w+') if args.log else [])
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s',
                        handlers=handlers)

    logging.info(f'Connecting to light strip at address: {args.address}...')
    while True:  # infinite loop unless terminated (eg via Ctrl+C)
        try:
            async with BleakClient(args.address) as client:
                logging.info('Connected')
                if args.demo:
                    await demo_mode(client, args.interval)
                else:
                    await ambient_mode(client, args.interval)
        except bleak.exc.BleakError as e:
            logging.info(e)
            logging.info(f'Retrying in {RETRY_INTERVAL} secs...')
            time.sleep(RETRY_INTERVAL)


if __name__ == '__main__':
    asyncio.run(main())

"""MSS/Pillow desktop pixels, kept in RAM. Upload is controlled by the rewrite module."""
import base64
import io
from PIL import Image
from Xlib import display
import mss


def monitor_for_pointer(monitors, x, y):
    for monitor in monitors:
        if monitor['left'] <= x < monitor['left'] + monitor['width'] and monitor['top'] <= y < monitor['top'] + monitor['height']:
            return monitor
    raise RuntimeError('无法确定鼠标所在的屏幕。')


def region_image(region):
    with mss.mss() as capture:
        shot = capture.grab(region)
        return Image.frombytes('RGB', shot.size, shot.rgb)


def current_monitor_image(max_size=1600):
    connection = display.Display()
    try:
        pointer = connection.screen().root.query_pointer()
        with mss.mss() as capture:
            monitor = monitor_for_pointer(capture.monitors[1:], pointer.root_x, pointer.root_y)
            shot = capture.grab(monitor)
            image = Image.frombytes('RGB', shot.size, shot.rgb)
    finally:
        connection.close()
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return image


def data_url(image):
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='JPEG', quality=75)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def capture_rewrite_context(cfg):
    if cfg.get('cleanup_mode', 'none') != 'light' or str(cfg.get('rewrite_use_screen', 'false')).lower() != 'true':
        return None
    return data_url(current_monitor_image())

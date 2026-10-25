"""Anonymous browser examples and nearby legitimate cases for both filter paths."""

from dataclasses import replace
from datetime import datetime, timezone

from mycount.entity.Visit import Visit


def browser_automation_cases():
    windows = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36')
    mac = windows.replace('Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7')
    linux = windows.replace('Windows NT 10.0; Win64; x64', 'X11; Linux x86_64')
    android = ('Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36')
    iphone = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) '
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Mobile/15E148 Safari/604.1')
    phone = dict(vendor='Google Inc.', platform='Linux x86_64', screen_width=375,
                 screen_height=812, device_memory=32, max_touch_points=3,
                 hardware_concurrency=192, webdriver=False)
    desktop = dict(vendor='Google Inc.', platform='Linux x86_64',
                   screen_width=1920, screen_height=1080, webdriver=False)
    viewport = dict(vendor='Google Inc.', platform='Win32', screen_width=800,
                    screen_height=600, viewport_width=1024, webdriver=False)
    preview = dict(vendor='Google Inc.', platform='Windows', screen_width=2000,
                   screen_height=2000, device_memory=32, webdriver=False)
    emulated_iphone = dict(vendor='Google Inc.', platform='Win32',
                           max_touch_points=1, webdriver=False)
    examples = [
        ('android_renderer', android, phone, None, True),
        ('iphone_renderer', iphone, phone, None, True),
        ('windows_on_linux', windows, desktop, None, True),
        ('mac_on_linux', mac, desktop, None, True),
        ('oversized_viewport', windows, viewport, None, True),
        ('facebook_renderer', windows, preview, 'www.facebook.com', True),
        ('iphone_on_windows', iphone, emulated_iphone, None, True),
        ('iphone_on_mac', iphone, {**emulated_iphone, 'platform': 'MacIntel'}, None, True),
        ('ordinary_windows_chrome151', windows, {**desktop, 'platform': 'Win32'}, None, False),
        ('ordinary_linux', linux, desktop, None, False),
        ('ordinary_iphone', iphone, dict(vendor='Apple Computer, Inc.', platform='iPhone',
                                       max_touch_points=5), None, False),
        ('ordinary_android', android, {**phone, 'platform': 'Linux armv8l',
                                      'hardware_concurrency': 8}, None, False),
        ('ordinary_qt', windows.replace('Chrome/', 'QtWebEngine/6.11.2 Chrome/'),
         {**desktop, 'platform': 'Win32'}, None, False),
        ('missing_metadata', windows, {}, None, False),
        ('vendor_only', windows, {'vendor': 'Google Inc.'}, None, False),
        ('same_size_viewport', windows, {**viewport, 'viewport_width': 800}, None, False),
        ('preview_without_facebook', windows, preview, None, False),
        ('preview_other_referrer', windows, preview, 'example.com', False),
        ('preview_on_win32', windows, {**preview, 'platform': 'Win32'}, 'www.facebook.com', False),
        ('preview_lower_memory', windows, {**preview, 'device_memory': 8}, 'www.facebook.com', False),
        ('iphone_desktop_without_touch_signal', iphone,
         {**emulated_iphone, 'max_touch_points': 5}, None, False),
    ]
    # Each required phone signal must be present, even when webdriver is false.
    for field in phone:
        if field == 'webdriver':
            continue
        examples.append(('phone_missing_' + field, android,
                         {key: value for key, value in phone.items() if key != field}, None, False))
    for field, value in [('screen_width', 390), ('screen_height', 844), ('device_memory', 8),
                         ('max_touch_points', 5), ('hardware_concurrency', 29)]:
        examples.append(('phone_other_' + field, android, {**phone, field: value}, None, False))
    examples.append(('phone_cpu_boundary', android, {**phone, 'hardware_concurrency': 30}, None, True))
    base = Visit(site='example', url='https://example.com/',
                 received_at=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
                 country_code='CA', country_name='Canada', city_name='Hamilton')
    return [(name, replace(base, user_agent=agent, client_details=tuple(details.items()),
                           referrer_host=referrer), agent, expected)
            for name, agent, details, referrer, expected in examples]

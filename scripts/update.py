#!/usr/bin/env python3
"""Updates images.

Exporting the images is too complicated/verbose for a Makefile.
"""
import os
import itertools
import subprocess

from PIL import Image

import build


def touch(filename):
    with open(filename, 'wb'):
        return True
    return False


def newest_file(path):
    t = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            t = max(t, os.path.getmtime(os.path.join(root, f)))
    return t


def path_helper(path, ext):
    """Because I'm lazy."""

    if not os.path.isdir(path):
        os.makedirs(path)

    def wrapper(name):
        return os.path.join(path, '%s.%s' % (name, ext))
    return wrapper


def main():
    if os.path.exists('.update') and \
            os.path.getmtime('.update') >= newest_file(build.source):
        return

    build.cli_main(['clean'])

    svg = path_helper(build.output_svg, 'svg')
    png = path_helper(build.output_png, 'png')
    src = path_helper(build.source, 'svg')
    splash = path_helper(os.path.join(build.base, '.meta'), 'png')
    splash_gif = path_helper(os.path.join(build.base, '.meta'), 'gif')

    images = {
        (svg('logo_light'),
         png('logo_light')): {
             'in': src('logo'),
             'base-color': '#333',
        },
        (svg('icon_light'),
         png('icon_light')): {
             'in': src('icon'),
             'base-color': '#333',
        },
        (svg('logo_dark'),
         png('logo_dark')): {
             'in': src('logo'),
             'base-color': '#333',
             'bg': '0',
        },
        (svg('icon_dark'),
         png('icon_dark')): {
             'in': src('icon'),
             'base-color': '#333',
             'bg': '0',
        },
        splash('splash1'): {
            'in': src('logo'),
            'base-color': '#333',
            'no-caret': '',
        },
        splash('splash2'): {
            'in': src('logo'),
            'base-color': '#333',
        },
    }

    # Create the preview images.
    previews = (
        ('light', '#333'),
        ('dark', '#333'),
        ('red', '#f00'),
        ('orange', '#ff7f00'),
        ('yellow', '#ff0'),
        ('green', '#0f0'),
        ('blue', '#00f'),
        ('indigo', '#4b0082'),
        ('violet', '#8b00ff'),
    )

    preview = path_helper(os.path.join(build.base, '.meta', 'preview'), 'png')

    for name, color in previews:
        for sub, bg in (('light', '255'), ('dark', '0')):
            for source in ('logo', 'icon'):
                if name in ('light', 'dark') and name != sub:
                    continue

                args = {
                    'in': src(source),
                    'base-color': color,
                    'height': '80',
                }

                if name != 'light':
                    args['bg'] = bg

                images[preview('%s_%s_%s' % (source, name, sub))] = args

    for k, v in images.items():
        args = list(itertools.chain(*[('--%s' % ak, av) for ak, av in v.items()]))
        if not isinstance(k, tuple):
            k = [k]

        for f in k:
            build.cli_main(['color'] + args + ['--out', f])

    def gif_frame(name):
        img1 = Image.open(splash(name))
        img2 = Image.new('RGBA', img1.size, 0xffffffff)
        img3 = Image.alpha_composite(img2, img1)
        img3.save(splash_gif(name))
        img1.close()
        img2.close()
        os.remove(splash(name))

    gif_frame('splash1')
    gif_frame('splash2')

    subprocess.call(['gifsicle', '-o', splash_gif('splash'), '-O3', '-l',
                     '--delay', '50', splash_gif('splash1'), splash_gif('splash2')])

    os.remove(splash_gif('splash1'))
    os.remove(splash_gif('splash2'))

    touch('.update')

if __name__ == '__main__':
    main()

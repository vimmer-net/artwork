#!/usr/bin/env python3
"""Utility script for dealing with the SVG artwork."""
import os
import re
import sys
import math
import argparse
import colorsys

import cairosvg

from lxml import etree, objectify
from cairosvg.colors import COLORS, color

base = os.getcwd()
source = os.path.join(base, 'source')
output_build = os.path.join(base, 'build')
output_svg = os.path.join(output_build, 'svg')
output_png = os.path.join(output_build, 'png')


class Color(object):
    def __init__(self, val):
        c = None

        if isinstance(val, (list, tuple)):
            c = val[:3]
        elif isinstance(val, Color):
            c = [val.r, val.g, val.b]
        elif isinstance(val, str):
            val = val.replace(' ', '')
            if val in COLORS:
                c = color(val)
            elif re.search(r'^#?[0-9a-f]{3,6}$', val, re.I):
                if len(val.lstrip('#')) in (3, 6):
                    c = color(val)

        if not c:
            raise ValueError('%s is not a parseable color' % val)

        self.r, self.g, self.b = c[:3]

    @property
    def hwb(self):
        """Hue, Whiteness, Blackness."""
        hsv = colorsys.rgb_to_hsv(self.r, self.g, self.b)
        h = hsv[0]
        w = (1.0 - hsv[1]) * hsv[2]
        b = 1.0 - hsv[2]
        return [h, w, b]

    @hwb.setter
    def hwb(self, val):
        h = val[0]
        s = 1.0
        if 1.0 - val[2]:
            s = 1.0 - (val[1] / (1.0 - val[2]))
        v = 1.0 - val[2]
        self.r, self.g, self.b = colorsys.hsv_to_rgb(h, s, v)

    @property
    def luma(self):
        return math.sqrt(self.r * self.r * 0.299 +
                         self.g * self.g * 0.587 +
                         self.b * self.b * 0.114)

    def invert_levels(self):
        """Invert white and black levels."""
        hwb = self.hwb
        hwb[1] = 1.0 - hwb[1]
        hwb[2] = 1.0 - hwb[2]

        out = Color((0, 0, 0))
        out.hwb = hwb
        return out

    def blend_hwb(self, other, amount=None):
        """Blend the whiteness and blackness of a color.

        'self' is the source color that retains its hue.
        """
        hwb1 = self.hwb
        hwb2 = other.hwb

        hwb1[1] = (hwb1[1] + hwb2[1]) / 2
        hwb1[2] = (hwb1[2] + hwb2[2]) / 2

        out = Color((0, 0, 0))
        out.hwb = hwb1
        return out

    @property
    def hex(self):
        """Hexadecimal representation of the color."""
        return '#%02x%02x%02x' % tuple(map(lambda x: min(255, x * 255),
                                           (self.r, self.g, self.b)))

    def __repr__(self):
        return '<Color %s>' % self.hex


class SVGFile(object):
    """Simple class for SVG files."""
    def __init__(self, filename):
        if not filename.endswith('.svg'):
            raise ValueError('%s is not an SVG file.')
        self.filename = filename
        self.tree = self._parse_xml(filename)
        self.box = list(map(int, self.tree.attrib.get('viewBox',
                                                      '0 0 0 0').split()))

    def iterwalk(self, *args, **kwargs):
        return etree.iterwalk(self.tree, *args, **kwargs)

    def _clean_attrs(self, e, strip_attrs=None):
        """Clean up element attributes."""
        cls = e.attrib.get('data-name', e.attrib.get('id'))
        if cls:
            m = re.search(r'(.+)_\d+_$', cls)
            if m:
                cls = m.group(1)

            if e.tag.endswith('linearGradient'):
                e.attrib['id'] = 'e_' + cls.lower()
            else:
                e.attrib['class'] = 'v_' + cls.lower()
                del e.attrib['id']

            if 'data-name' in e.attrib:
                del e.attrib['data-name']

        fill = e.attrib.get('fill')
        if fill:
            m = re.search(r'url\(#([^\)]+)\)', fill)
            if m:
                fill = m.group(1)
                m = re.search(r'(.+)_\d+_$', fill)
                if m:
                    fill = m.group(1)
                e.attrib['fill'] = 'url(#e_%s)' % fill

        for attr in ['x', 'y']:
            if attr not in e.attrib:
                continue
            if e.attrib[attr] == '0':
                del e.attrib[attr]

        if strip_attrs is None:
            return

        for attr in e.attrib.keys():
            if attr in strip_attrs:
                del e.attrib[attr]

    def _parse_xml(self, path):
        """Return a parse tree for the SVG file."""
        tree = None
        parser = etree.XMLParser(resolve_entities=False, huge_tree=False,
                                 remove_blank_text=True, ns_clean=True,
                                 remove_comments=True, remove_pis=True)

        if isinstance(path, bytes):
            tree = etree.fromstring(path, parser=parser)
        else:
            with open(path, 'rb') as fp:
                tree = etree.fromstring(fp.read(), parser=parser)

        objectify.deannotate(tree, cleanup_namespaces=True)
        return tree

    def clean(self):
        self._clean_attrs(self.tree,
                          ['x', 'y', 'width', 'height', 'enable-background',
                           '{http://www.w3.org/XML/1998/namespace}space'])

        for e in self.tree.iterfind('.//*[@id]'):
            self._clean_attrs(e)

        # Reparse to ensure it's in the final form since processing directives
        # are removed after the XML is read.
        tree = self._parse_xml(etree.tostring(self.tree))

        with open(self.filename, 'wb') as fp:
            fp.write(etree.tostring(tree))

    def save(self, **kwargs):
        """Saves using the most appropriate method for the file extension."""
        filename = kwargs.get('write_to')
        if not filename:
            raise ValueError('No file specified')

        print('Writing:', filename)
        ext = os.path.splitext(filename)[1].lstrip('.')
        if ext == 'svg':
            with open(filename, 'wb') as fp:
                fp.write(bytes(self))
            return

        w = kwargs.get('parent_width', 0)
        h = kwargs.get('parent_height', 0)
        if w or h:
            if w:
                scale = w / self.box[2]
            elif h:
                scale = h / self.box[3]

            kwargs['parent_width'] = round(self.box[2] * scale)
            kwargs['parent_height'] = round(self.box[3] * scale)

        writer = getattr(cairosvg, 'svg2%s' % ext, None)
        if not writer:
            raise ValueError('No writer for file extension: %s' % ext)
        else:
            writer(bytestring=bytes(self), **kwargs)

    def __bytes__(self):
        return etree.tostring(self.tree)


def update(args):
    """Update images."""
    pass


def clean(args, unknown):
    """Clean up the SVG files."""
    for root, dirs, files in os.walk(source):
        for f in files:
            if not f.endswith('.svg'):
                continue
            path = os.path.join(root, f)
            print('Cleaning:', path)
            svg = SVGFile(path)
            svg.clean()


def colorize(args, unknown):
    """Colorize artwork

    This is done by averaging the base color's white and black levels with the
    SVG's.  If the background is enabled and determined to be dark, the SVG's
    levels are inverted.
    """
    print('Coloring:', args.svg.filename)
    dark = False
    bg = None
    print('  Background:', args.bg is not None)
    if args.bg is not None:
        if isinstance(args.bg, Color):
            bg = args.bg
        else:
            bg = args.base_color.blend_hwb(Color([args.bg / 255] * 3))
        bg_hwb = bg.hwb

        # Darkness is based on the RGB luma.
        dark = bg.luma < 0.4
        print('  Luma: %f' % bg.luma)
        print('  White: %f, Black: %s' % (bg_hwb[1], bg_hwb[2]))
        print('  Dark Background: %r' % dark)

    for a, e in args.svg.iterwalk(events=('end',)):
        if 'fill' not in e.attrib:
            continue

        cls = e.attrib.get('class')
        if cls:
            off_arg = '--no-%s' % cls.split('_', 1)[-1]
            if off_arg in unknown:
                e.getparent().remove(e)
                continue

        fill = e.attrib.get('fill')
        if fill.startswith('url('):
            continue

        fill = Color(fill)
        if cls == 'v_background':
            if bg:
                e.attrib['fill'] = bg.hex
            continue
        elif dark:
            fill = fill.invert_levels()
        e.attrib['fill'] = args.base_color.blend_hwb(fill).hex

    args.svg.save(**vars(args))


def bg_color(val):
    try:
        val = int(val)
        if val > -1 or val < 256:
            return val
    except ValueError:
        pass

    try:
        return Color(val)
    except ValueError:
        pass

    raise argparse.ArgumentTypeError('Value must be between 0 and 255 '
                                     'or a color.')


def cli_main(args):
    """Entry point for command arguments."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()

    update_a = sub.add_parser('update', help='Update images.')
    update_a.set_defaults(func=update)

    clean_a = sub.add_parser('clean', help='Clean source SVG XML files')
    clean_a.set_defaults(func=clean)

    color_a = sub.add_parser('color', help='Colorize Images')
    color_a.add_argument('-i', '--in', type=SVGFile, help='SVG File.',
                         dest='svg', required=True)
    color_a.add_argument('-c', '--base-color', type=Color, help='Base color.',
                         required=True)
    color_a.add_argument('-b', '--bg', type=bg_color,
                         help='Between 0 and 255 (for grayscale) or a color.')
    color_a.add_argument('--hide', action='append', help='Elements to hide.')

    size = color_a.add_mutually_exclusive_group()

    # Below arguments are passed to CairoSVG for non-SVG output.
    # https://github.com/Kozea/CairoSVG/blob/0efe258616a92277883872a3092698c80fab51fe/cairosvg/__init__.py
    size.add_argument('-W', '--width', type=int, default=0, help='Width.',
                      dest='parent_width')
    size.add_argument('-H', '--height', type=int, default=0, help='Height.',
                      dest='parent_height')
    color_a.add_argument('-d', '--dpi', type=int, default=96,
                         help='DPI.')
    color_a.add_argument('-s', '--scale', type=float, default=1,
                         help='Scaling factor.  Between 0 and 1.')
    color_a.add_argument('-o', '--output', help='Output file.', required=True,
                         dest='write_to')
    color_a.set_defaults(func=colorize)

    args, unknown = parser.parse_known_args(args)
    args.func(args, unknown)


if __name__ == '__main__':
    cli_main(sys.argv[1:])

#  vim: set ft=python ts=4 sw=4 tw=79 et :

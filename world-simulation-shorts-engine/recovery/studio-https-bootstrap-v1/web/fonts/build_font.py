#!/usr/bin/env python3
"""Reproduce the UI-only OFL font derivative from the existing repository font.

The original font file and the renderer's font configuration are never changed.
Requires fonttools[woff]==4.61.1 and brotli==1.1.0. No network is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import brotli
from fontTools import __version__ as fonttools_version
from fontTools import subset
from fontTools.ttLib import TTFont

SOURCE_SHA = '91a6b21a427d1a5982e19e8875bfd6af620d0a372cd84967a0c225b90f342f6c'
FAMILY = 'WorldEngineStudioSetup'
POSTSCRIPT = 'WorldEngineStudioSetup-Regular'
RANGES = [(0x20, 0xFF), (0x1100, 0x11FF), (0x2000, 0x206F),
    (0x2190, 0x21FF), (0x3000, 0x303F), (0x3130, 0x318F),
    (0xA960, 0xA97F), (0xAC00, 0xD7A3), (0xD7B0, 0xD7FF)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_SHA:
        raise SystemExit('STUDIO_UI_FONT_SOURCE_SHA_MISMATCH')
    if fonttools_version != '4.61.1' or brotli.__version__ != '1.1.0':
        raise SystemExit('STUDIO_UI_FONT_FONTTOOLS_VERSION_REQUIRED')
    font = TTFont(args.source, recalcTimestamp=False)
    original_times = (font['head'].created, font['head'].modified)
    original_cmap = font.getBestCmap()
    unicode_values = {value for start, end in RANGES for value in range(start, end + 1)}
    options = subset.Options()
    options.name_IDs = ['*']
    options.name_languages = ['*']
    options.name_legacy = True
    options.layout_features = ['*']
    options.recalc_timestamp = False
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicode_values)
    subsetter.subset(font)
    # OFL derivative uses a distinct primary name. Retain original copyright
    # and license records; remove original primary/postscript family names.
    renamed = {1: FAMILY, 2: 'Regular', 3: 'WORLD-ENGINE-UI-OFL-1.0',
        4: FAMILY + ' Regular', 6: POSTSCRIPT, 16: FAMILY, 17: 'Regular',
        18: FAMILY + ' Regular', 21: FAMILY, 22: 'Regular'}
    for record in font['name'].names:
        if record.nameID in renamed:
            record.string = renamed[record.nameID].encode(record.getEncoding())
    cff = font['CFF '].cff
    cff.fontNames = [POSTSCRIPT]
    cff.topDictIndex[0].FamilyName = FAMILY
    cff.topDictIndex[0].FullName = FAMILY + ' Regular'
    font['head'].created, font['head'].modified = original_times
    font.flavor = 'woff2'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output, reorderTables=True)
    if not 0 < args.output.stat().st_size <= 4 * 1024**2:
        raise SystemExit('STUDIO_UI_FONT_SIZE_LIMIT')
    verified = TTFont(args.output, recalcTimestamp=False)
    retained = verified.getBestCmap()
    required_hangul = set(range(0xAC00, 0xD7A4))
    if not required_hangul <= set(retained):
        raise SystemExit('STUDIO_UI_FONT_COMPLETE_HANGUL_REQUIRED')
    if set(retained) != unicode_values & set(original_cmap):
        raise SystemExit('STUDIO_UI_FONT_CMAP_PRESERVATION_REQUIRED')
    print(json.dumps({'status': 'PASS', 'file': args.output.name,
        'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'bytes': args.output.stat().st_size, 'fontFamily': FAMILY,
        'hangulSyllables': len(required_hangul), 'mappedUnicodeCodepoints': len(retained),
        'sourceSha256': SOURCE_SHA, 'sourceModified': False,
        'scope': 'STUDIO_WEB_UI_ONLY_NOT_RENDERER_OR_GLOBAL_FONTS'}, sort_keys=True))


if __name__ == '__main__':
    main()

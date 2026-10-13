#!/usr/bin/python3
"""Authored flag shape data for the eight visible reference unit badges.

This is artwork, not a claim of actual force positions or troop numbers. The
selected reference is explicitly a modern counterfactual map scene. Flags live
in fixture data; the renderer has no country-specific branches.
"""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent


def rect(x, y, width, height, fill):
    return {'type': 'rect', 'x': x, 'y': y, 'width': width, 'height': height, 'fill': fill}


def star(x, y, radius, fill, rotation=0):
    return {'type': 'star', 'cx': x, 'cy': y, 'radius': radius, 'fill': fill, 'rotation': rotation}


def rotate_rect(x, y, width, height, angle, fill):
    points = [[x-width/2, y-height/2], [x+width/2, y-height/2],
              [x+width/2, y+height/2], [x-width/2, y+height/2]]
    cosine, sine = math.cos(angle), math.sin(angle)
    return {'type': 'polygon', 'points': [[p[0]*cosine-p[1]*sine, p[0]*sine+p[1]*cosine] for p in points], 'fill': fill}


def main():
    common = {'soldier_ink': '#0b1010', 'helmet_color': '#788a6d',
              'uniform_color': '#6e7f6d', 'skin_color': '#e9b58f'}
    profiles = {}
    profiles['flag_profile_01'] = {**common, 'background': '#ed0729', 'border_color': '#ffe76b',
        'flag_shapes': [star(-.24, -.24, .11, '#ffe756'),
                        star(-.052, -.335, .028, '#ffe756', .25), star(.052, -.245, .027, '#ffe756', .5),
                        star(.052, -.133, .027, '#ffe756', 0), star(-.052, -.058, .027, '#ffe756', .25)]}
    profiles['flag_profile_02'] = {**common, 'background': '#e90537', 'border_color': '#ffe76b',
        'flag_shapes': [rect(-.5, -.5, 1, .105, '#0665a1'), rect(-.5, -.395, 1, .054, '#fffdf5'),
                        rect(-.5, .343, 1, .055, '#fffdf5'), rect(-.5, .398, 1, .102, '#0665a1'),
                        {'type': 'circle', 'cx': -.255, 'cy': -.10, 'radius': .205, 'fill': '#fffdf5'},
                        star(-.255, -.10, .168, '#e90537')]}
    profiles['flag_profile_03'] = {**common, 'background': '#ffffff', 'border_color': '#ffe76b',
        'flag_shapes': [rect(-.5, -.167, 1, .334, '#024bd3'), rect(-.5, .167, 1, .333, '#e52a35')]}
    korean_shapes = [
        {'type': 'circle', 'cx': 0, 'cy': -.035, 'radius': .245, 'fill': '#ea163d'},
        {'type': 'path', 'commands': [['M', -.245, -.035],
          ['C', -.245, .10, -.135, .21, 0, .21], ['C', .135, .21, .245, .10, .245, -.035],
          ['C', .245, -.105, .13, -.16, 0, -.035], ['C', -.13, .09, -.245, .035, -.245, -.035], ['Z']],
         'fill': '#0769b7'},
    ]
    # Four compact trigrams stay fixture-owned authored shape geometry.
    for x, y, angle, broken in [(-.32, -.30, -.55, False), (.32, -.30, .55, True),
                                (-.32, .27, .55, True), (.32, .27, -.55, False)]:
        for offset in [-.045, 0, .045]:
            if broken:
                for dx in [-.049, .049]:
                    c, s = math.cos(angle), math.sin(angle)
                    points = []
                    for xx, yy in [(dx-.036, offset-.012), (dx+.036, offset-.012),
                                   (dx+.036, offset+.012), (dx-.036, offset+.012)]:
                        points.append([x+xx*c-yy*s, y+xx*s+yy*c])
                    korean_shapes.append({'type': 'polygon', 'points': points, 'fill': '#121414'})
            else:
                c, s = math.cos(angle), math.sin(angle)
                points = [[x+xx*c-yy*s, y+xx*s+yy*c] for xx, yy in
                          [(-.083, offset-.012), (.083, offset-.012), (.083, offset+.012), (-.083, offset+.012)]]
                korean_shapes.append({'type': 'polygon', 'points': points, 'fill': '#121414'})
    profiles['flag_profile_04'] = {**common, 'background': '#fffef7', 'border_color': '#fffef7', 'flag_shapes': korean_shapes}
    us_shapes = [rect(-.5, -.5+i/13, 1, 1/13, '#d92640' if i%2==0 else '#fffef7') for i in range(13)]
    us_shapes.append(rect(-.5, -.5, .50, 7/13, '#103e62'))
    for row in range(5):
        for column in range(5 if row%2==0 else 4):
            us_shapes.append(star(-.444+column*.087+(0 if row%2==0 else .0435), -.447+row*.092, .021, '#fffef7'))
    profiles['flag_profile_05'] = {**common, 'background': '#fffef7', 'border_color': '#fffef7', 'flag_shapes': us_shapes}
    result = {'schema_version': 'REFERENCE_COMBAT_AUTHORED_PROFILE_V2', 'profiles': profiles,
              'authorship': 'Original programmatic vector shapes authored for this study; no source bitmap extraction.',
              'source_visible_roles': {'flag_profile_01': 'China', 'flag_profile_02': 'North Korea',
                                      'flag_profile_03': 'Russia', 'flag_profile_04': 'South Korea', 'flag_profile_05': 'United States'},
              'source_visible_counts': {'flag_profile_01': 1, 'flag_profile_02': 1, 'flag_profile_03': 1,
                                       'flag_profile_04': 2, 'flag_profile_05': 3},
              'semantic_mode': 'COUNTERFACTUAL_REFERENCE_REPRODUCTION_NOT_REAL_MILITARY_SITUATION',
              'render_contract': 'Geographic anchors and per-frame screen sizes supplied by fixture, using final shared camera projection.',
              'visual_gap': 'Authored silhouettes approximate source helmet/flag badges; pixel-identical source icon artwork is not claimed.'}
    destination = ROOT/'fixtures/REFERENCE_COMBAT_VISUAL_PROFILE.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'profiles': len(profiles), 'source_visible_units': 8, 'no_country_renderer_branches': True}))


if __name__ == '__main__':
    main()

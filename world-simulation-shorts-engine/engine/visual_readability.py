"""Opt-in presentation for new FAST_PLUS plans; saved plans are never upgraded.

Based on the user's actual 12-second RTX4080S MP4 (SHA in the quality report).
Events/audio/route clocks remain independent of the bounded camera clock.
"""
from copy import deepcopy
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'readability_v011'


def apply_readability_policy(plan):
    if (plan.get('options', {}).get('pace') != 'FAST_PLUS'
            or plan.get('story', {}).get('domain') != 'shipping'):
        return plan
    plan = deepcopy(plan)
    files = ['web/readability_visual_adapter.js', 'web/render_readable_earth.html', 'tools/readable_semantic_preflight.mjs']
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
    scenes = [s for s in plan['scenes'] if s.get('production_defaults', {}).get('version') == 'v1'
              and s.get('render_mode', 'MASTER_V3_EARTH') == 'MASTER_V3_EARTH']
    for scene in scenes:
        d = scene['duration']
        # Allow information to appear before a move; arrive before the next cue.
        lead = min(.45, d*.18)
        tail = min(.8, d*.25)
        scene['visual_readability'] = dict(version=VERSION, initial_hold=lead,
            final_hold=tail, acceleration_fraction=.15, source_hashes=hashes,
            text_support=True, route_core_pixels_1080=3.0, entity_min_pixels_1080=18,
            lighting_curve='continuous_geography_with_city_lights',
            total_duration=plan['duration'])
        # Reuse all GIS paths/IDs/progress/events. Only newly authored short camera endpoints
        # are adjusted to the scale jumps directly observed in this MP4.
        if plan['duration'] <= 20 and plan.get('story', {}).get('domain') == 'shipping':
            if scene['scene_id'] == 'S001':
                for key, height in [('camera_start', 1.15), ('camera_end', 1.10)]:
                    scene[key].update(lon=scene['coordinates']['lon'], lat=scene['coordinates']['lat'],
                        target_lon=scene['coordinates']['lon'], target_lat=scene['coordinates']['lat'],
                        height=height, tilt=.38, yaw=-.20, bank=0, fov=50)
            elif scene['scene_id'] == 'S002':
                scene['camera_end'].update(lon=18, lat=35, target_lon=18, target_lat=35, height=1.60, tilt=.42, yaw=-.20, bank=0, fov=50)
            elif scene['scene_id'] == 'S003':
                scene['camera_end'].update(height=1.45, tilt=.40, yaw=-.15, bank=0, fov=50)
                # Suez arrival at .2667 must be read before the network pullback.
                scene['visual_readability'].update(initial_hold=.90, final_hold=.35)
            elif scene['scene_id'] == 'S004':
                # Reuse the already validated short-QA geographic approach.
                # A route-relative horizon rig cannot share a held world-camera
                # phase without a near-zero aim vector during this short move.
                scene['camera_preset'] = 'COUNTRY_APPROACH'
                scene['camera_end'].update(height=1.25, tilt=.40, yaw=-.15, bank=0, fov=50)
                # The long geographic move needs time, not a compressed whip.
                scene['visual_readability'].update(initial_hold=.10, final_hold=.40)
            elif scene['scene_id'] == 'S005':
                scene['camera_end'].update(lon=58, lat=20, target_lon=60, target_lat=20, height=3.0, tilt=.30, yaw=0, bank=0, fov=50)
                scene['visual_readability'].update(initial_hold=.60, final_hold=.60)
    # Endpoints and declared states are identical on both sides of each seam.
    for i, scene in enumerate(plan['scenes']):
        if scene in scenes:
            if i and plan['scenes'][i-1] in scenes:
                scene['camera_start'] = deepcopy(plan['scenes'][i-1]['camera_end'])
            scene['entry_state']['camera'] = deepcopy(scene['camera_start'])
            scene['exit_state']['camera'] = deepcopy(scene['camera_end'])
    return plan

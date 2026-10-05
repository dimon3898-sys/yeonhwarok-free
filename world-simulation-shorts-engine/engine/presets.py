"""Versioned, deterministic shot/lighting grammar inherited from MASTER V3."""
from copy import deepcopy

CAMERA_PRESETS = {
    'GLOBAL_ESTABLISH': dict(height=1.8, tilt=.35, yaw=-.18, fov=43, speed=.8, acceleration=.45, deceleration=.65, easing='smootherstep', bank=.015, motion_blur=.25),
    'FAST_HOOK_DIVE': dict(height=.65, tilt=.55, yaw=-.18, fov=42, speed=1.8, acceleration=.8, deceleration=.7, easing='quintic_out', bank=.025, motion_blur=.6),
    'COUNTRY_APPROACH': dict(height=.5, tilt=.5, yaw=.12, fov=42, speed=.9, acceleration=.4, deceleration=.6, easing='smootherstep', bank=.01, motion_blur=.25),
    'CITY_APPROACH': dict(height=.3, tilt=.6, yaw=-.15, fov=40, speed=.85, acceleration=.4, deceleration=.75, easing='smootherstep', bank=.015, motion_blur=.25),
    'GEOGRAPHY_APPROACH': dict(height=.42, tilt=.4, yaw=.08, fov=44, speed=.75, acceleration=.35, deceleration=.7, easing='smootherstep', bank=.008, motion_blur=.18),
    'ROUTE_CHASE': dict(height=.42, tilt=.7, yaw=-.26, fov=43, speed=1.15, acceleration=.55, deceleration=.55, easing='smootherstep', bank=.025, motion_blur=.4),
    'ENTITY_FOLLOW': dict(height=.23, tilt=.7, yaw=-.24, fov=42, speed=1.1, acceleration=.5, deceleration=.55, easing='smootherstep', bank=.025, motion_blur=.4),
    'EARTH_ORBIT': dict(height=1.1, tilt=.55, yaw=.35, fov=44, speed=.75, acceleration=.4, deceleration=.45, easing='smootherstep', bank=.018, motion_blur=.3),
    'HORIZON_REVEAL': dict(height=.32, tilt=.95, yaw=-.28, fov=44, speed=.8, acceleration=.45, deceleration=.65, easing='smootherstep', bank=.028, motion_blur=.35),
    'TERRITORY_OVERVIEW': dict(height=.8, tilt=.45, yaw=.12, fov=45, speed=.7, acceleration=.35, deceleration=.65, easing='smootherstep', bank=.008, motion_blur=.2),
    'NETWORK_EXPANSION': dict(height=1.45, tilt=.4, yaw=.16, fov=44, speed=1.2, acceleration=.6, deceleration=.6, easing='smootherstep', bank=.018, motion_blur=.4),
    'GLOBAL_PULLBACK': dict(height=2.05, tilt=.35, yaw=.16, fov=45, speed=1.55, acceleration=.65, deceleration=.65, easing='smootherstep', bank=.02, motion_blur=.5),
    'FINAL_REVEAL': dict(height=1.85, tilt=.4, yaw=.12, fov=44, speed=1.3, acceleration=.6, deceleration=.8, easing='smootherstep', bank=.012, motion_blur=.35),
}
# Explicit opt-in only. Existing planner selects only its original Earth grammar.
FLAT_CAMERA_PRESETS = {
    'FLAT_ESTABLISH': dict(height=.8, tilt=.02, yaw=0., fov=43, speed=.85, acceleration=.45, deceleration=.65, easing='smootherstep', bank=0., motion_blur=.18),
    'FLAT_COUNTRY_FOCUS': dict(height=.55, tilt=.025, yaw=0., fov=42, speed=.85, acceleration=.4, deceleration=.7, easing='smootherstep', bank=0., motion_blur=.16),
    'FLAT_REGION_FOCUS': dict(height=.7, tilt=.02, yaw=0., fov=43, speed=.8, acceleration=.4, deceleration=.65, easing='smootherstep', bank=0., motion_blur=.16),
    'FLAT_ROUTE_FOLLOW': dict(height=.48, tilt=.025, yaw=0., fov=43, speed=1.05, acceleration=.55, deceleration=.6, easing='smootherstep', bank=0., motion_blur=.22),
    'FLAT_ENTITY_FOLLOW': dict(height=.4, tilt=.025, yaw=0., fov=42, speed=1.05, acceleration=.55, deceleration=.6, easing='smootherstep', bank=0., motion_blur=.22),
    'FLAT_MULTI_COUNTRY': dict(height=1.1, tilt=.015, yaw=0., fov=44, speed=.8, acceleration=.45, deceleration=.65, easing='smootherstep', bank=0., motion_blur=.18),
    'FLAT_PULLBACK': dict(height=1.4, tilt=.02, yaw=0., fov=44, speed=1.2, acceleration=.6, deceleration=.7, easing='smootherstep', bank=0., motion_blur=.25),
    'FLAT_NEXT_EVENT_PREVIEW': dict(height=.65, tilt=.025, yaw=0., fov=43, speed=.95, acceleration=.5, deceleration=.65, easing='smootherstep', bank=0., motion_blur=.2),
}
CAMERA_PRESETS.update(FLAT_CAMERA_PRESETS)
RENDER_MODES = {'MASTER_V3_EARTH', 'FLAT_MAP_PREMIUM'}
FLAT_MAP_VFX = {'PULSE', 'RADAR', 'WARNING', 'IMPACT', 'SHOCKWAVE', 'AREA_HIGHLIGHT', 'ROUTE_BLOCK', 'ROUTE_REROUTE'}
FLAT_ENTITY_ACTIONS = {'split', 'merge', 'converge', 'diverge', 'follow', 'intercept', 'stop', 'reroute', 'move', 'depart', 'arrive'}
FLAT_SOUND_BINDINGS = {'route_blocked': 'warning_hit', 'route_reroute': 'transition_sweep',
                       'country_reveal': 'soft_pulse', 'region_reveal': 'soft_pulse',
                       'new_variable': 'tension_riser', 'peak_reveal': 'cinematic_hit'}

def scene_render_mode(scene):
    """Legacy immutable plans remain Earth; new flat mode must be explicit."""
    mode = scene.get('render_mode', 'MASTER_V3_EARTH')
    if mode not in RENDER_MODES:
        raise ValueError('UNKNOWN_RENDER_MODE: ' + str(mode))
    return mode

LIGHTING_PRESETS = {
    'CINEMATIC_NIGHT': dict(surface_exposure=.48, ambient=.22, city_lights=1.1, coast_contrast=.7, cloud_opacity=.32, atmosphere=1.0, sun_intensity=.65, sun_lon=15, sun_lat=-12, grade='cool_warm'),
    'GEOGRAPHY_READABILITY': dict(surface_exposure=1.1, ambient=.7, city_lights=.5, coast_contrast=1.4, cloud_opacity=.13, atmosphere=.8, sun_intensity=1.15, sun_lon=35, sun_lat=15, grade='natural'),
    'DAY_DOCUMENTARY': dict(surface_exposure=1.0, ambient=.55, city_lights=.1, coast_contrast=1.25, cloud_opacity=.22, atmosphere=.85, sun_intensity=1.3, sun_lon=25, sun_lat=20, grade='natural'),
    'HERO': dict(surface_exposure=.62, ambient=.3, city_lights=1., coast_contrast=.9, cloud_opacity=.28, atmosphere=1.25, sun_intensity=1.15, sun_lon=12, sun_lat=-10, grade='cinema'),
    'DISASTER': dict(surface_exposure=.95, ambient=.65, city_lights=.55, coast_contrast=1.3, cloud_opacity=.12, atmosphere=.8, sun_intensity=1., sun_lon=25, sun_lat=10, grade='neutral'),
    'WAR_SIMULATION': dict(surface_exposure=1., ambient=.65, city_lights=.6, coast_contrast=1.35, cloud_opacity=.1, atmosphere=.8, sun_intensity=1., sun_lon=25, sun_lat=10, grade='neutral'),
}
DIRECTING_PRESETS = {
    name: dict(role=role, event_priority=priority, information_limit=1)
    for name, role, priority in [
        ('HOOK_REVEAL','hook',10),('COUNTRY_REVEAL','orientation',7),('CITY_REVEAL','orientation',7),
        ('ROUTE_START','cause',8),('ROUTE_CHASE','progression',7),('NEW_VARIABLE','variable',9),
        ('COUNTER_RESPONSE','response',9),('NETWORK_EXPANSION','escalation',8),
        ('TERRITORY_CHANGE','consequence',9),('GEOGRAPHY_CHANGE','consequence',9),
        ('ESCALATION','escalation',9),('PEAK_MOMENT','peak',10),('FINAL_REVEAL','payoff',10)]
}
QUALITY_PRESETS = {
    'FAST': dict(width=540,height=960,internal_width=540,internal_height=960,fps=30,preview_only=True),
    'HIGH': dict(width=1080,height=1920,internal_width=2160,internal_height=3840,fps=30,preview_only=False),
    'CINEMA': dict(width=1080,height=1920,internal_width=2160,internal_height=3840,fps=30,preview_only=False),
}

def camera_state(location, preset):
    p=CAMERA_PRESETS[preset]
    c=location['coordinates']
    return {**{k:p[k] for k in ('height','tilt','yaw','bank','fov')},'lon':c['lon'],'lat':c['lat'],'target_lon':c['lon'],'target_lat':c['lat'],'location_id':location['id']}

def choose_lighting(scene_type, role):
    if scene_type in {'COUNTRY_FOCUS','COMPARISON','TERRITORY','TIMELINE'} or role in {'geography','consequence'}:
        return 'GEOGRAPHY_READABILITY'
    if role=='peak': return 'HERO'
    if scene_type=='EARTH_ESTABLISH':return 'CINEMATIC_NIGHT'
    return 'GEOGRAPHY_READABILITY' if scene_type=='CITY_FOCUS' else 'CINEMATIC_NIGHT'


# Production policy is a separate opt-in layer. Existing shot constants remain
# immutable so historical plans and renderer cache keys retain their semantics.
PACE_PRESETS = ('FAST', 'NORMAL', 'CINEMATIC')
PRODUCTION_VISUAL_MODES = ('FLAT_MAP', '3D_EARTH', 'HERO', 'CINEMATIC_CLIP')
PRODUCTION_TEXT_DENSITIES = ('NONE', 'MINIMAL', 'INFORMATIONAL')

def production_preset():
    from .production import PRODUCTION_PRESET
    return deepcopy(PRODUCTION_PRESET)

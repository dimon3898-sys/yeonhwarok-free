"""Fail-closed plugin capability registry; future modules are interfaces only."""
from dataclasses import dataclass, field
from typing import Protocol, Any

class PluginInterface(Protocol):
    name: str
    def validate(self, scene: dict) -> list[str]: ...
    def prepare(self, scene: dict, assets: dict) -> dict: ...

@dataclass(frozen=True)
class Capability:
    name: str
    available: bool
    scene_types: tuple[str,...]=()
    entity_types: tuple[str,...]=()
    description: str=''

REGISTRY={
    'AVIATION':Capability('AVIATION',True,('CITY_FOCUS','ROUTE','ROUTE_CHASE'),('aircraft','airport','city'), 'Verified-coordinate aviation visualizations; not flight performance predictions.'),
    'SHIPPING':Capability('SHIPPING',True,('ROUTE','ROUTE_CHASE'),('cargo_ship','port'), 'Sourced maritime graph routes; not navigation or economic forecasts.'),
    'NETWORK':Capability('NETWORK',True,('NETWORK','FINAL_OVERVIEW'),('location_marker','city'), 'Causal, explicitly labelled connection scenarios.'),
    'GEOGRAPHY':Capability('GEOGRAPHY',True,('EARTH_ESTABLISH','COUNTRY_FOCUS','CITY_FOCUS','COMPARISON','FINAL_OVERVIEW'),('location_marker','vehicle'), 'Modern verified geography only.'),
    'CINEMATIC_CLIP':Capability('CINEMATIC_CLIP',True,('CINEMATIC_CLIP',),(), 'User-supplied licensed MP4 slot.'),
    **{name:Capability(name,False,description='Extension contract exists; visual implementation is not installed.') for name in ('WAR_VFX','TIME_MORPH','GEOGRAPHY_MORPH','TERRITORY_TIMELINE','WEATHER','DISASTER','SPACE','ECONOMY')}
}
SCENE_TYPES=('EARTH_ESTABLISH','COUNTRY_FOCUS','CITY_FOCUS','ROUTE','ROUTE_CHASE','NETWORK','COMPARISON','TERRITORY','TIMELINE','CINEMATIC_CLIP','FINAL_OVERVIEW')
ENTITY_TYPES=('aircraft','cargo_ship','vehicle','location_marker','city','port','airport')
FUTURE_ENTITY_PLUGINS={'missile':'WAR_VFX','fighter':'WAR_VFX','warship':'WAR_VFX','tank':'WAR_VFX','satellite':'SPACE','storm':'WEATHER','tsunami':'DISASTER','volcano':'DISASTER','population_flow':'ECONOMY'}

class UnsupportedVisualRequirement(ValueError):
    code='UNSUPPORTED_VISUAL_REQUIREMENT'
    def __init__(self, modules, reason):
        self.modules=sorted(set(modules));self.reason=reason
        super().__init__(reason)
    def as_dict(self):
        return dict(code=self.code,message=self.reason,required_plugins=self.modules,required_plugin=self.modules[0] if self.modules else None)


def require_plugins(names):
    missing=[n for n in names if n not in REGISTRY or not REGISTRY[n].available]
    if missing: raise UnsupportedVisualRequirement(missing,'필요한 시각 모듈이 설치되지 않았습니다. 기존 효과로 대체하지 않습니다.')

@dataclass
class HistoricalState:
    year: int|None=None
    date: str|None=None
    era: str|None=None
    timeline_position: float|None=None
    geometry_state: dict=field(default_factory=dict)
    transition_duration: float=0.

class GeographyMorphInterface(Protocol):
    def transition(self, before:HistoricalState, after:HistoricalState, duration:float)->Any: ...

class WarEffectsInterface(Protocol):
    def missile_trail(self, event:dict)->Any: ...
    def impact(self, event:dict)->Any: ...
    def explosion(self, event:dict)->Any: ...
    def shockwave(self, event:dict)->Any: ...
    def smoke(self, event:dict)->Any: ...
    def radar_scan(self, event:dict)->Any: ...
    def fleet_move(self, event:dict)->Any: ...
    def fighter_move(self, event:dict)->Any: ...
    def territory_change(self, event:dict)->Any: ...

class WeatherInterface(Protocol):
    def visualize(self, state:dict, scientific_source:dict|None)->Any: ...

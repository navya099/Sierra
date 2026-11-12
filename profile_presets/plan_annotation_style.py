"""Sierra REG2-2-B: immutable, DXF-independent plan annotation styles.

Explicit plan JSON is authoritative. A missing plan section uses compatible
scale-based defaults (Tacoma station symbols; Sierra plan VIP dimensions).
No renderer, GUI, or Tacoma imports are required.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TextStyle:
    height: float
    color: int | None


@dataclass(frozen=True, slots=True)
class SymbolStyle:
    radius: float
    color: int | None


@dataclass(frozen=True, slots=True)
class StationSymbolStyle:
    enabled: bool
    interval: float
    text: TextStyle
    symbol: SymbolStyle


@dataclass(frozen=True, slots=True)
class TickStyle:
    enabled: bool
    interval: float
    length: float
    color: int | None


@dataclass(frozen=True, slots=True)
class PlanStationStyle:
    km: StationSymbolStyle
    main: StationSymbolStyle
    tick: TickStyle


@dataclass(frozen=True, slots=True)
class LeaderStyle:
    stem_length: float
    arm_length: float
    color: int


@dataclass(frozen=True, slots=True)
class PlanVipStyle:
    enabled: bool
    text: TextStyle
    leader: LeaderStyle

@dataclass(frozen=True, slots=True)
class PlanIpStyle:
    enabled: bool
    text: TextStyle
    table: TextStyle

@dataclass(frozen=True, slots=True)
class PlanAnnotationStyle:
    station: PlanStationStyle
    vip: PlanVipStyle
    ip: PlanIpStyle

def _default_plan(horizontal_scale: int) -> dict[str, Any]:
    """Compatibility fallback ONLY for old presets missing annotations.plan.

    H5000 uses Tacoma's 40m minor station interval; other scales retain 20m
    until a scale-specific Sierra preset explicitly provides a plan section.
    """
    k = horizontal_scale / 1000.0
    return {
        'station': {
            'km': {'enabled': True, 'interval': 1000, 'text': {'height': 3*k, 'color': None},
                   'symbol': {'radius': 2*k, 'color': None}},
            'main': {'enabled': True, 'interval': 200, 'text': {'height': 3*k, 'color': None},
                     'symbol': {'radius': 1.5*k, 'color': None}},
            'tick': {'enabled': True, 'interval': 40 if horizontal_scale == 5000 else 20,
                     'length': 3*k, 'color': None},
        },
        'vip': {'enabled': True, 'text': {'height': 3*k, 'color': 1},
                'leader': {'stem_length': 30*k, 'arm_length': 10.5*k, 'color': 1}},
    }


def plan_style_from_preset(preset: Mapping[str, Any]) -> PlanAnnotationStyle:
    """Validate the entire Sierra preset and build an immutable style snapshot.

    Caller-owned dict is never mutated. Explicit plan settings are never
    silently merged with defaults: invalid or partial sections fail validation.
    """
    from profile_presets.loader import validate_preset
    validate_preset(preset)
    scale = int(preset['horizontal_scale'])
    plan = preset['layout']['annotations'].get('plan')
    if plan is None:
        plan = _default_plan(scale)
    stations = plan['station']

    def station_symbol(name: str) -> StationSymbolStyle:
        raw = stations[name]
        return StationSymbolStyle(
            enabled=raw['enabled'], interval=float(raw['interval']),
            text=TextStyle(float(raw['text']['height']), raw['text']['color']),
            symbol=SymbolStyle(float(raw['symbol']['radius']), raw['symbol']['color']),
        )

    tick = stations['tick']
    vip = plan['vip']
    leader = vip['leader']

    #REG2-R3-B1-3: PlanAnnotationStyle 확장
    ip_raw = plan.get('ip')

    if ip_raw is None:
        # 기존 프리셋 호환성 유지
        legacy_height = 3.0 * 1000.0 / scale
        ip_style = PlanIpStyle(
            enabled=True,
            text=TextStyle(legacy_height, 1),
            table=TextStyle(legacy_height, 7),
        )
    else:
        ip_style = PlanIpStyle(
            enabled=ip_raw['enabled'],
            text=TextStyle(
                float(ip_raw['text']['height']),
                ip_raw['text']['color'],
            ),
            table=TextStyle(
                float(ip_raw['table']['text_height']),
                ip_raw['table']['color'],
            ),
        )

    return PlanAnnotationStyle(
        station=PlanStationStyle(
            km=station_symbol('km'), main=station_symbol('main'),
            tick=TickStyle(tick['enabled'], float(tick['interval']),
                           float(tick['length']), tick['color']),
        ),
        vip=PlanVipStyle(
            enabled=vip['enabled'],
            text=TextStyle(float(vip['text']['height']), vip['text']['color']),
            leader=LeaderStyle(float(leader['stem_length']),
                               float(leader['arm_length']), leader['color']),
        ),
    ip=ip_style,)

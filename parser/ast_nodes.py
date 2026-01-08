from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class TerrainType(Enum):
    FLAT = "flat"
    ROLLING = "rolling"
    MOUNTAINOUS = "mountainous"
    OCEAN = "ocean"


class Orientation(Enum):
    SOUTH = "south"
    NORTH = "north"
    EAST = "east"
    WEST = "west"


class TrackingMode(Enum):
    FIXED = "fixed"
    SINGLE_AXIS = "single_axis"
    DUAL_AXIS = "dual_axis"


@dataclass
class Coordinate:
    latitude: float
    longitude: float
    
    def __str__(self):
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude)}°{lat_dir}, {abs(self.longitude)}°{lon_dir}"


@dataclass
class Quantity:
    value: float
    unit: str
    
    def __str__(self):
        return f"{self.value}{self.unit}"


@dataclass
class Site:
    name: str
    location: Coordinate
    area: Optional[Quantity] = None
    terrain: Optional[str] = None
    irradiance: Optional[Quantity] = None
    elevation: Optional[Quantity] = None
    
    def __repr__(self):
        return f"Site(name='{self.name}', location={self.location})"


@dataclass
class Equipment:
    type: str  # panel, inverter, turbine, battery
    name: str
    from_catalog: bool = False
    specs: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.specs is None:
            self.specs = {}
    
    def __repr__(self):
        source = "catalog" if self.from_catalog else "custom"
        return f"Equipment(type='{self.type}', name='{self.name}', source={source})"


@dataclass
class EquipmentRef:
    name: str
    count: Optional[int] = None
    
    def __str__(self):
        if self.count:
            return f"{self.name} * {self.count}"
        return self.name


@dataclass
class Layout:
    name: str
    panels: Optional[EquipmentRef] = None
    inverters: Optional[EquipmentRef] = None
    turbines: Optional[EquipmentRef] = None
    orientation: Optional[str] = None
    tilt: Optional[float] = None  # degrees
    row_spacing: Optional[Quantity] = None
    tracking: Optional[TrackingMode] = None
    count: Optional[int] = None
    
    def __repr__(self):
        return f"Layout(name='{self.name}', panels={self.panels})"


@dataclass
class WeatherSource:
    provider: str
    args: List[str]
    
    def __str__(self):
        args_str = ", ".join(f"'{arg}'" for arg in self.args)
        return f"{self.provider}({args_str})"


@dataclass
class Simulation:
    weather: Optional[WeatherSource] = None
    duration: Optional[str] = None
    timestep: Optional[str] = None
    outputs: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.outputs is None:
            self.outputs = ["generation", "capacity_factor"]
    
    def __repr__(self):
        return f"Simulation(duration={self.duration}, timestep={self.timestep})"


@dataclass
class Constraint:
    variable: str
    operator: str
    value: Any
    
    def __str__(self):
        return f"{self.variable} {self.operator} {self.value}"


@dataclass
class Objective:
    mode: str  # maximize or minimize
    target: str
    
    def __str__(self):
        return f"{self.mode}({self.target})"


@dataclass
class Optimization:
    objective: Optional[Objective] = None
    variables: Optional[List[str]] = None
    constraints: Optional[List[Constraint]] = None
    algorithm: Optional[str] = "gradient"
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = []
        if self.constraints is None:
            self.constraints = []
    
    def __repr__(self):
        return f"Optimization(objective={self.objective}, vars={len(self.variables)})"


@dataclass
class Model:
    """Complete RenewDSL Model"""
    site: Optional[Site] = None
    equipment: List[Equipment] = None
    layouts: List[Layout] = None
    simulation: Optional[Simulation] = None
    optimization: Optional[Optimization] = None
    
    def __post_init__(self):
        if self.equipment is None:
            self.equipment = []
        if self.layouts is None:
            self.layouts = []
    
    def __repr__(self):
        parts = []
        if self.site:
            parts.append(f"site={self.site.name}")
        if self.equipment:
            parts.append(f"equipment={len(self.equipment)}")
        if self.layouts:
            parts.append(f"layouts={len(self.layouts)}")
        return f"Model({', '.join(parts)})"

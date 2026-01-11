from lark import Lark, Transformer, v_args
from .ast_nodes import (
    Site, Coordinate, Quantity, Equipment, EquipmentRef,
    Layout, Simulation, WeatherSource, Optimization,
    Objective, Constraint, Model, TrackingMode
)
from typing import Any, List


# TODO: Move grammar to separate file eventually
GRAMMAR = r"""
?start: statement+

statement: site_def
         | equipment_section
         | layout_def
         | simulate_def
         | optimize_def

site_def: "site" string ":" _NL _INDENT site_attr+ _DEDENT

site_attr: "location" ":" coordinate _NL
         | "area" ":" quantity _NL
         | "terrain" ":" string _NL
         | "irradiance" ":" quantity _NL
         | "elevation" ":" quantity _NL

coordinate: NUMBER "°" direction_ns "," NUMBER "°" direction_ew
direction_ns: "N" | "S"
direction_ew: "E" | "W"

equipment_section: "equipment" ":" _NL _INDENT equipment_item+ _DEDENT

equipment_item: equipment_type string spec_block? _NL

equipment_type: "panel" | "inverter" | "turbine" | "battery"

spec_block: ":" _NL _INDENT equipment_spec+ _DEDENT

equipment_spec: NAME ":" (quantity | NUMBER | string) _NL

layout_def: "layout" string ":" _NL _INDENT layout_attr+ _DEDENT

layout_attr: "panels" ":" equipment_ref _NL
           | "inverters" ":" equipment_ref _NL
           | "orientation" ":" orientation _NL
           | "tilt" ":" angle _NL
           | "row_spacing" ":" quantity _NL
           | "tracking" ":" tracking_mode _NL

equipment_ref: NAME ("*" NUMBER)?

orientation: "south" | "north" | "east" | "west"
tracking_mode: "fixed" | "single_axis" | "dual_axis"
angle: NUMBER "°"

simulate_def: "simulate" ":" _NL _INDENT simulate_attr+ _DEDENT

simulate_attr: "weather" ":" weather_source _NL
             | "duration" ":" duration _NL
             | "timestep" ":" duration _NL
             | "outputs" ":" output_list _NL

weather_source: NAME "(" string ("," string)* ")"

output_list: "[" NAME ("," NAME)* "]"

optimize_def: "optimize" ":" _NL _INDENT optimize_attr+ _DEDENT

optimize_attr: "objective" ":" objective_expr _NL
             | "variables" ":" variable_list _NL
             | "algorithm" ":" string _NL

objective_expr: ("maximize" | "minimize") "(" NAME ")"

variable_list: "[" NAME ("," NAME)* "]"

quantity: NUMBER unit

unit: "m" | "km" | "hectares" | "kW" | "MW" | "kWh/m²/day" | "°" | "h" | "hour" | "day" | "year"

duration: NUMBER unit

string: ESCAPED_STRING

NUMBER: /[0-9]+\.?[0-9]*/
NAME: /[a-zA-Z_][a-zA-Z0-9_]*/

_NL: /\r?\n/
_INDENT: /<INDENT>/
_DEDENT: /<DEDENT>/

%import common.ESCAPED_STRING
%import common.WS
%ignore WS
"""


class RenewDSLTransformer(Transformer):
    """Transform parse tree into AST nodes"""
    
    def __init__(self):
        super().__init__()
        self.model = Model()
    
    @v_args(inline=True)
    def string(self, s):
        return s[1:-1]  # Remove quotes
    
    @v_args(inline=True)
    def NUMBER(self, n):
        return float(n)
    
    @v_args(inline=True)
    def NAME(self, n):
        return str(n)
    
    @v_args(inline=True)
    def coordinate(self, lat, ns, lon, ew):
        lat_val = lat if ns == "N" else -lat
        lon_val = lon if ew == "E" else -lon
        return Coordinate(lat_val, lon_val)
    
    @v_args(inline=True)
    def quantity(self, value, unit):
        return Quantity(value, str(unit))
    
    @v_args(inline=True)
    def angle(self, value):
        return float(value)
    
    @v_args(inline=True)
    def duration(self, value, unit):
        return f"{value}{unit}"
    
    def site_attr(self, items):
        attr_name = items[0].data
        value = items[1]
        return (attr_name, value)
    
    def site_def(self, items):
        name = items[0]
        attrs = dict(items[1:])
        
        self.model.site = Site(
            name=name,
            location=attrs.get('location'),
            area=attrs.get('area'),
            terrain=attrs.get('terrain'),
            irradiance=attrs.get('irradiance'),
            elevation=attrs.get('elevation')
        )
        return self.model.site
    
    @v_args(inline=True)
    def equipment_type(self, type_name):
        return str(type_name)
    
    def equipment_spec(self, items):
        spec_name = str(items[0])
        value = items[1]
        return (spec_name, value)
    
    def spec_block(self, items):
        return dict(items)
    
    def equipment_item(self, items):
        eq_type = items[0]
        name = items[1]
        specs = items[2] if len(items) > 2 else {}
        
        equipment = Equipment(
            type=eq_type,
            name=name,
            specs=specs
        )
        self.model.equipment.append(equipment)
        return equipment
    
    def equipment_section(self, items):
        return items
    
    @v_args(inline=True)
    def equipment_ref(self, name, count=None):
        return EquipmentRef(name, int(count) if count else None)
    
    @v_args(inline=True)
    def tracking_mode(self, mode):
        mode_str = str(mode)
        return TrackingMode(mode_str)
    
    def layout_attr(self, items):
        attr_name = items[0].data
        value = items[1]
        return (attr_name, value)
    
    def layout_def(self, items):
        name = items[0]
        attrs = dict(items[1:])
        
        layout = Layout(
            name=name,
            panels=attrs.get('panels'),
            inverters=attrs.get('inverters'),
            orientation=attrs.get('orientation'),
            tilt=attrs.get('tilt'),
            row_spacing=attrs.get('row_spacing'),
            tracking=attrs.get('tracking')
        )
        self.model.layouts.append(layout)
        return layout
    
    def weather_source(self, items):
        provider = items[0]
        args = items[1:]
        return WeatherSource(provider, args)
    
    def output_list(self, items):
        return [str(item) for item in items]
    
    def simulate_attr(self, items):
        attr_name = items[0].data
        value = items[1]
        return (attr_name, value)
    
    def simulate_def(self, items):
        attrs = dict(items)
        
        self.model.simulation = Simulation(
            weather=attrs.get('weather'),
            duration=attrs.get('duration'),
            timestep=attrs.get('timestep'),
            outputs=attrs.get('outputs')
        )
        return self.model.simulation
    
    @v_args(inline=True)
    def objective_expr(self, mode, target):
        return Objective(str(mode), str(target))
    
    def variable_list(self, items):
        return [str(item) for item in items]
    
    def optimize_attr(self, items):
        attr_name = items[0].data
        value = items[1]
        return (attr_name, value)
    
    def optimize_def(self, items):
        attrs = dict(items)
        
        self.model.optimization = Optimization(
            objective=attrs.get('objective'),
            variables=attrs.get('variables'),
            algorithm=attrs.get('algorithm', 'gradient')
        )
        return self.model.optimization
    
    def statement(self, items):
        return items[0]
    
    def start(self, items):
        return self.model


class IndentPreprocessor:
    """Convert indentation to INDENT/DEDENT tokens"""
    
    def __init__(self, text: str):
        self.lines = text.split('\n')
        self.output = []
        self.indent_stack = [0]
    
    def process(self) -> str:
        for line in self.lines:
            if not line.strip():
                self.output.append('')
                continue
            
            # Calculate indentation level
            indent = len(line) - len(line.lstrip())
            
            # Handle indent changes
            if indent > self.indent_stack[-1]:
                self.indent_stack.append(indent)
                self.output.append(line.replace(' ' * indent, '<INDENT>' * (len(self.indent_stack) - 1), 1))
            elif indent < self.indent_stack[-1]:
                while self.indent_stack and indent < self.indent_stack[-1]:
                    self.indent_stack.pop()
                    self.output.append('<DEDENT>')
                self.output.append(line)
            else:
                self.output.append(line)
        
        # Close remaining indents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.output.append('<DEDENT>')
        
        return '\n'.join(self.output)


def parse(dsl_text: str) -> Model:
    """Parse RenewDSL text into a Model AST"""
    
    # Preprocess indentation
    preprocessor = IndentPreprocessor(dsl_text)
    processed_text = preprocessor.process()
    
    # Parse with Lark
    parser = Lark(GRAMMAR, parser='lalr', start='start')
    tree = parser.parse(processed_text)
    
    # Transform to AST
    transformer = RenewDSLTransformer()
    model = transformer.transform(tree)
    
    return model


if __name__ == "__main__":
    # Test parser with simple example
    test_dsl = """
site "Test Solar Farm":
    location: 35.0°N, 115.0°W
    area: 50 hectares
    irradiance: 6.2 kWh/m²/day

equipment:
    panel "TestPanel":
        capacity: 400 kW
        efficiency: 22.5

layout "main":
    panels: TestPanel * 1000
    orientation: south
    tilt: 30°
    tracking: fixed

simulate:
    duration: 1 year
    timestep: 1 hour
    outputs: [generation, capacity_factor]
"""
    
    model = parse(test_dsl)
    print(f"Parsed: {model}")
    print(f"Site: {model.site}")
    print(f"Equipment: {model.equipment}")
    print(f"Layouts: {model.layouts}")

"""
RenewDSL Solar Simulation Engine
File: renewdsl/simulation/solar_sim.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
import pvlib
from pvlib import location, pvsystem, modelchain, temperature


class SolarSimulator:
    """Simulates solar PV system performance using pvlib"""
    
    def __init__(self, model):
        self.model = model
        self.site = model.site
        self.layout = model.layouts[0] if model.layouts else None
        self.simulation = model.simulation
        self.results = None
    
    def create_location(self):
        """Create pvlib Location object from site"""
        return location.Location(
            latitude=self.site.location.latitude,
            longitude=self.site.location.longitude,
            tz='UTC',
            altitude=self.site.elevation.value if self.site.elevation else 0
        )
    
    def create_system(self):
        """Create PV system from layout and equipment"""
        # Get panel specs
        panel_name = self.layout.panels.name
        panel = next((e for e in self.model.equipment if e.name == panel_name), None)
        
        if not panel:
            raise ValueError(f"Panel '{panel_name}' not found in equipment")
        
        # Extract specifications
        capacity_w = panel.specs.get('capacity', Quantity(400, 'W')).value
        if isinstance(capacity_w, str):
            capacity_w = float(capacity_w.replace('kW', '').replace('W', '')) 
            if 'kW' in str(panel.specs.get('capacity')):
                capacity_w *= 1000
        
        # Create simple PV system parameters
        modules_per_string = 20
        strings = max(1, self.layout.panels.count // modules_per_string) if self.layout.panels.count else 50
        
        # System configuration
        system = pvsystem.PVSystem(
            surface_tilt=self.layout.tilt if self.layout.tilt else 30,
            surface_azimuth=self._orientation_to_azimuth(self.layout.orientation),
            module_parameters={
                'pdc0': capacity_w,
                'gamma_pdc': -0.004,  # Temperature coefficient
            },
            inverter_parameters={
                'pdc0': capacity_w * modules_per_string * strings * 0.95,
            },
            modules_per_string=modules_per_string,
            strings_per_inverter=strings
        )
        
        return system
    
    def _orientation_to_azimuth(self, orientation):
        """Convert orientation string to azimuth angle"""
        mapping = {
            'south': 180,
            'north': 0,
            'east': 90,
            'west': 270,
            None: 180  # Default to south
        }
        return mapping.get(orientation, 180)
    
    def generate_weather_data(self, loc, start_date, end_date):
        """Generate synthetic weather data (TMY-like)"""
        # Create hourly timestamps
        times = pd.date_range(start_date, end_date, freq='1H', tz='UTC')
        
        # Generate synthetic clear-sky data
        clearsky = loc.get_clearsky(times)
        
        # Add some realistic variability
        np.random.seed(42)
        cloud_cover = np.random.beta(2, 5, size=len(times))  # More clear days than cloudy
        ghi = clearsky['ghi'] * (1 - cloud_cover * 0.8)
        dni = clearsky['dni'] * (1 - cloud_cover * 0.9)
        dhi = clearsky['dhi'] + cloud_cover * 100
        
        # Temperature model (simplified)
        day_of_year = times.dayofyear
        hour_of_day = times.hour
        
        # Base temperature varies by season
        temp_base = 15 + 15 * np.cos(2 * np.pi * (day_of_year - 200) / 365)
        # Daily variation
        temp_daily = 10 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
        temp_air = temp_base + temp_daily + np.random.normal(0, 2, size=len(times))
        
        # Wind speed
        wind_speed = np.random.gamma(2, 2, size=len(times))
        
        weather = pd.DataFrame({
            'ghi': ghi,
            'dni': dni,
            'dhi': dhi,
            'temp_air': temp_air,
            'wind_speed': wind_speed
        }, index=times)
        
        return weather
    
    def run_simulation(self):
        """Run the complete solar simulation"""
        print("Starting solar simulation...")
        
        # Create location and system
        loc = self.create_location()
        system = self.create_system()
        
        # Parse duration
        duration = self.simulation.duration if self.simulation else "1 year"
        start_date = datetime(2023, 1, 1)
        
        if 'year' in duration:
            years = int(duration.split()[0])
            end_date = start_date + timedelta(days=365 * years)
        elif 'day' in duration:
            days = int(duration.split()[0])
            end_date = start_date + timedelta(days=days)
        else:
            end_date = start_date + timedelta(days=365)
        
        print(f"Simulating from {start_date} to {end_date}")
        
        # Generate weather data
        print("Generating weather data...")
        weather = self.generate_weather_data(loc, start_date, end_date)
        
        # Create model chain for simulation
        mc = modelchain.ModelChain(
            system, loc,
            aoi_model='physical',
            spectral_model='no_loss'
        )
        
        # Run simulation
        print("Running PV model...")
        mc.run_model(weather)
        
        # Extract results
        self.results = {
            'ac_power': mc.results.ac,  # AC power output (W)
            'dc_power': mc.results.dc.p_mp,  # DC power at max power point
            'weather': weather,
            'times': weather.index
        }
        
        # Calculate metrics
        self._calculate_metrics()
        
        print("Simulation complete!")
        return self.results
    
    def _calculate_metrics(self):
        """Calculate performance metrics"""
        ac_power = self.results['ac_power']
        
        # Total energy (kWh)
        timestep_hours = 1  # Assuming hourly data
        total_energy_kwh = (ac_power * timestep_hours).sum() / 1000
        
        # System capacity
        panel = self.model.equipment[0]
        capacity_w = float(str(panel.specs.get('capacity', '400 W')).replace('kW', '000').replace('W', '').strip())
        panel_count = self.layout.panels.count if self.layout.panels.count else 1000
        system_capacity_kw = (capacity_w * panel_count) / 1000
        
        # Capacity factor
        hours_in_period = len(ac_power)
        max_possible_energy = system_capacity_kw * hours_in_period
        capacity_factor = (total_energy_kwh / max_possible_energy) * 100 if max_possible_energy > 0 else 0
        
        # Peak power
        peak_power_kw = ac_power.max() / 1000
        
        # Average daily generation
        days = hours_in_period / 24
        avg_daily_kwh = total_energy_kwh / days if days > 0 else 0
        
        self.results['metrics'] = {
            'total_energy_kwh': total_energy_kwh,
            'system_capacity_kw': system_capacity_kw,
            'capacity_factor_pct': capacity_factor,
            'peak_power_kw': peak_power_kw,
            'avg_daily_kwh': avg_daily_kwh,
            'simulation_hours': hours_in_period
        }
    
    def print_summary(self):
        """Print simulation results summary"""
        if not self.results:
            print("No results available. Run simulation first.")
            return
        
        metrics = self.results['metrics']
        
        print("\n" + "="*60)
        print("SOLAR SIMULATION RESULTS")
        print("="*60)
        print(f"Site: {self.site.name}")
        print(f"Location: {self.site.location}")
        print(f"System Capacity: {metrics['system_capacity_kw']:.2f} kW")
        print("-"*60)
        print(f"Total Energy Generated: {metrics['total_energy_kwh']:,.2f} kWh")
        print(f"Capacity Factor: {metrics['capacity_factor_pct']:.2f}%")
        print(f"Peak Power Output: {metrics['peak_power_kw']:.2f} kW")
        print(f"Average Daily Generation: {metrics['avg_daily_kwh']:.2f} kWh/day")
        print(f"Simulation Period: {metrics['simulation_hours']:,} hours")
        print("="*60 + "\n")
    
    def export_results(self, filename='simulation_results.csv'):
        """Export results to CSV"""
        if not self.results:
            print("No results to export.")
            return
        
        df = pd.DataFrame({
            'timestamp': self.results['times'],
            'ac_power_w': self.results['ac_power'],
            'ghi': self.results['weather']['ghi'],
            'temp_air': self.results['weather']['temp_air']
        })
        
        df.to_csv(filename, index=False)
        print(f"Results exported to {filename}")


# Wrapper class for easy import
class Quantity:
    def __init__(self, value, unit):
        self.value = value
        self.unit = unit
    
    def __str__(self):
        return f"{self.value} {self.unit}"


if __name__ == "__main__":
    # Test with mock model
    from ast_nodes import Site, Coordinate, Equipment, Layout, Simulation, Model, EquipmentRef, TrackingMode
    
    model = Model()
    model.site = Site(
        name="Test Solar Farm",
        location=Coordinate(35.0, -115.0),
        area=Quantity(50, "hectares"),
        irradiance=Quantity(6.2, "kWh/m²/day")
    )
    
    model.equipment = [
        Equipment(
            type="panel",
            name="TestPanel",
            specs={'capacity': Quantity(400, 'W'), 'efficiency': 22.5}
        )
    ]
    
    model.layouts = [
        Layout(
            name="main",
            panels=EquipmentRef("TestPanel", 1000),
            orientation="south",
            tilt=30.0,
            tracking=TrackingMode.FIXED
        )
    ]
    
    model.simulation = Simulation(
        duration="30 day",
        timestep="1 hour",
        outputs=["generation", "capacity_factor"]
    )
    
    # Run simulation
    sim = SolarSimulator(model)
    sim.run_simulation()
    sim.print_summary()

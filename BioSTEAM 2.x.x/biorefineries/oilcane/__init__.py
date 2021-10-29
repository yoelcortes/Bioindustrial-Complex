# -*- coding: utf-8 -*-
# BioSTEAM: The Biorefinery Simulation and Techno-Economic Analysis Modules
# Copyright (C) 2020, Yoel Cortes-Pena <yoelcortes@gmail.com>
# 
# This module is under the UIUC open-source license. See 
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.
"""
"""
from colorpalette import Palette
from math import floor, ceil
import os
import biosteam as bst
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import thermosteam as tmo
import biorefineries.cornstover as cs
from biorefineries.sugarcane import create_sugarcane_to_ethanol_system
from biorefineries.lipidcane import (
    create_chemicals as create_starting_chemicals,
    set_lipid_fraction as set_oil_fraction, 
    get_lipid_fraction as get_oil_fraction,
)
from thermosteam.units_of_measure import format_units
from biosteam.utils import CABBI_colors, colors
from biosteam import main_flowsheet, UnitGroup
from chaospy import distributions as shape
from warnings import warn
import pandas as pd
import numpy as np
from typing import NamedTuple
from . import (_process_settings,
               _chemicals,
               _system,
               _tea,
               _oil_extraction_specification,
               _distributions,
)
from ._contours import *
from ._process_settings import *
from ._chemicals import *
from ._system import *
from ._tea import *
from ._oil_extraction_specification import *
from ._distributions import *
from biorefineries.sugarcane import create_tea as create_conventional_ethanol_tea
from biorefineries import cornstover as cs
from . import units
from .units import *
import numpy as np

__all__ = [*_process_settings.__all__,
           *_chemicals.__all__,
           *_system.__all__,
           *_tea.__all__,
           *_oil_extraction_specification.__all__,
           *_distributions.__all__,
           'sys',
           'tea', 
           'flowsheet',
]
_system_loaded = False
_chemicals_loaded = False

PRS = cs.PretreatmentReactorSystem
PRS_cost_item = PRS.cost_items['Pretreatment reactor system']
kg_per_ton = 907.18474
oil_content = np.linspace(0.05, 0.15, 5)

area_colors = {
    'Feedstock handling': CABBI_colors.teal, 
    'Juicing': CABBI_colors.green_dirty,
    'EtOH prod.': CABBI_colors.blue,
    'Oil ext.': CABBI_colors.brown,
    'Biod. prod.': CABBI_colors.orange,
    'Pretreatment': CABBI_colors.green,
    'Wastewater treatment': colors.purple,
    'CH&P': CABBI_colors.yellow,
    'Utilities': colors.red,
    'Storage': CABBI_colors.grey,
    'HXN': colors.orange,
}

area_hatches = {
    'Feedstock handling': 'x', 
    'Juicing': '-',
    'EtOH prod.': '/',
    'Oil ext.': '\\',
    'Biod. prod.': '/|',
    'Pretreatment': '//',
    'Wastewater treatment': r'\\',
    'CH&P': '',
    'Utilities': '\\|',
    'Storage': '',
    'HXN': '+',
}

for i in area_colors: area_colors[i] = area_colors[i].tint(20)
palette = Palette(**area_colors)


configuration_names = (
    'S1', 'O1', 'S2', 'O2', 'S1*', 'O1*', 'S2*', 'O2*',
)
comparison_names = (
    # 'I - ∅', 
    'O1 - S1', 
    'O2 - S2', 
    'O2 - O1', 
    'O1* - O1', 
    'O2* - O2',  
)

other_comparison_names = (
    'O1* - S1*', 'O2* - S2*', 
)

across_oil_content_names = (
    'O1', 'O2', 
)

across_oil_content_agile_names = (
    'O1*', 'O2*', 
)

across_oil_content_comparison_names = (
    'O1 - S1', 'O2 - S2', 'O2 - O1', 
)

across_oil_content_agile_direct_comparison_names = (
    'O1* - O1', 'O2* - O2', 
)

across_oil_content_agile_comparison_names = (
    'O1* - S1*', 'O2* - S2*', 'O2* - O1*', 
)

(set_cane_oil_content, set_relative_sorghum_oil_content, set_bagasse_oil_retention, 
 set_bagasse_oil_extraction_efficiency, 
 set_plant_capacity, set_ethanol_price,
 set_biodiesel_price, set_natural_gas_price, 
 set_electricity_price, set_operating_days, 
 set_IRR, set_crude_glycerol_price, set_pure_glycerol_price,
 set_saccharification_reaction_time, set_cellulase_price, 
 set_cellulase_loading, set_reactor_base_cost,
 set_cane_glucose_yield, set_cane_xylose_yield, 
 set_sorghum_glucose_yield, set_sorghum_xylose_yield, 
 set_glucose_to_ethanol_yield, set_xylose_to_ethanol_yield,
 set_cofermentation_titer, set_cofermentation_productivity,
 set_cane_PL_content, set_sorghum_PL_content, set_cane_FFA_content,
 set_sorghum_FFA_content, set_TAG_to_FFA_conversion, set_oilcane_GWP
 ) = all_parameter_mockups = (
    bst.MockVariable('Oil retention', '%', 'Stream-sugarcane'),
    bst.MockVariable('Bagasse oil extraction efficiency', '%', 'Stream-sugarcane'),
    bst.MockVariable('Capacity', 'ton/hr', 'Stream-sugarcane'),
    bst.MockVariable('Price', 'USD/gal', 'Stream-ethanol'),
    bst.MockVariable('Price', 'USD/gal', 'Stream-biodiesel'),
    bst.MockVariable('Price', 'USD/cf', 'Stream-natural gas'),
    bst.MockVariable('Electricity price', 'USD/kWh', 'biorefinery'),
    bst.MockVariable('Operating days', 'day/yr', 'biorefinery'),
    bst.MockVariable('IRR', '%', 'biorefinery'),
    bst.MockVariable('Price', 'USD/kg', 'Stream-crude glycerol'),
    bst.MockVariable('Price', 'USD/kg', 'Stream-pure glycerol'),
    bst.MockVariable('Reaction time', 'hr', 'Saccharification'),
    bst.MockVariable('Price', 'USD/kg', 'Stream-cellulase'),
    bst.MockVariable('Cellulase loading', 'wt. % cellulose', 'Stream-cellulase'),
    bst.MockVariable('Base cost', 'million USD', 'Pretreatment reactor system'),
    bst.MockVariable('Cane glucose yield', '%', 'Pretreatment and saccharification'),
    bst.MockVariable('Sorghum glucose yield', '%', 'Pretreatment and saccharification'),
    bst.MockVariable('Cane xylose yield', '%', 'Pretreatment and saccharification'),
    bst.MockVariable('Sorghum xylose yield', '%', 'Pretreatment and saccharification'),
    bst.MockVariable('Glucose to ethanol yield', '%', 'Cofermentation'),
    bst.MockVariable('Xylose to ethanol yield', '%', 'Cofermentation'),
    bst.MockVariable('Titer', 'g/L', 'Cofermentation'),
    bst.MockVariable('Productivity', 'g/L/hr', 'Cofermentation'),
    bst.MockVariable('Cane PL content', '% oil', 'oilcane'),
    bst.MockVariable('Sorghum PL content', '% oil', 'oilsorghum'),
    bst.MockVariable('Cane FFA content', '% oil', 'oilcane'),
    bst.MockVariable('Sorghum FFA content', '% oil', 'oilsorghum'),    
    bst.MockVariable('Cane oil content', 'dry wt. %', 'Stream-sugarcane'),
    bst.MockVariable('Relative sorghum oil content', 'dry wt. %', 'Stream-sugarcane'),
    bst.MockVariable('TAG to FFA conversion', '% theoretical', 'Biorefinery'), 
    # bst.MockVariable('GWP-CF', 'kg CO2-eq/kWhr', 'Power utility'),
    bst.MockVariable('GWP', 'kg*CO2-eq/kg', 'Stream-oilcane'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-enzyme'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-H3PO4'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-lime'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-denaturant'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-natural gas'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-FGD lime'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-cellulase'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-DAP'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-CSL'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-caustic'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-catalyst'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-methanol'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-HCl'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-NaOH'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-crude glycerol'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-pure glycerine'),
    # bst.MockVariable('GWP-CF', 'kg*CO2-eq/kg', 'Stream-dryer natural gas'),
)
     
(MFPP, biodiesel_production, ethanol_production, electricity_production, 
 natural_gas_consumption, TCI, feedstock_consumption, 
 heat_exchanger_network_error, MFPP_derivative,
 biodiesel_production_derivative, ethanol_production_derivative, 
 electricity_production_derivative, natural_gas_consumption_derivative, 
 TCI_derivative, GWP_economic, GWP_ethanol, GWP_biodiesel, 
 GWP_crude_glycerol, GWP_electricity, GWP_economic_derivative, 
 GWP_biodiesel_derivative, GWP_ethanol_derivative, GWP_electricity_derivative, 
 GWP_crude_glycerol_derivative,
 ) = all_metric_mockups = (
    bst.MockVariable('MFPP', 'USD/ton', 'Biorefinery'),
    bst.MockVariable('Biodiesel production', 'Gal/ton', 'Biorefinery'),
    bst.MockVariable('Ethanol production', 'Gal/ton', 'Biorefinery'),
    bst.MockVariable('Electricity production', 'kWhr/ton', 'Biorefinery'),
    bst.MockVariable('Natural gas consumption', 'cf/ton', 'Biorefinery'),
    bst.MockVariable('TCI', '10^6*USD', 'Biorefinery'),
    bst.MockVariable('Feedstock consumption', 'ton/yr', 'Biorefinery'),
    bst.MockVariable('Heat exchanger network error', '%', 'Biorefinery'),
    bst.MockVariable('GWP', 'kg*CO2*eq / USD', 'Economic allocation'),
    bst.MockVariable('GWP', 'kg*CO2*eq / (ethanol*gal)', 'Ethanol'),
    bst.MockVariable('GWP', 'kg*CO2*eq / (biodiesel*gal)', 'Biodiesel'),
    bst.MockVariable('GWP', 'kg*CO2*eq / (crude-glycerol*gal)', 'Crude glycerol'),
    bst.MockVariable('GWP', 'kg*CO2*eq / kWhr', 'Electricity'),
    bst.MockVariable('MFPP derivative', 'USD/ton', 'Biorefinery'),
    bst.MockVariable('Biodiesel production derivative', 'Gal/ton', 'Biorefinery'),
    bst.MockVariable('Ethanol production derivative', 'Gal/ton', 'Biorefinery'),
    bst.MockVariable('Electricity production derivative', 'kWhr/ton', 'Biorefinery'),
    bst.MockVariable('Natural gas consumption derivative', 'cf/ton', 'Biorefinery'),
    bst.MockVariable('TCI derivative', '10^6*USD', 'Biorefinery'),
    bst.MockVariable('GWP derivative', 'kg*CO2*eq / USD', 'Economic allocation'),
    bst.MockVariable('Ethanol GWP derivative', 'kg*CO2*eq / (ethanol*gal)', 'Ethanol'),
    bst.MockVariable('Biodiesel GWP derivative', 'kg*CO2*eq / (biodiesel*gal)', 'Biodiesel'),
    bst.MockVariable('Crude glycerol GWP derivative', 'kg*CO2*eq / (crude-glycerol*gal)', 'Crude glycerol'),
    bst.MockVariable('Electricity GWP derivative', 'kg*CO2*eq / kWhr', 'Electricity'),
)

tea_monte_carlo_metric_mockups = (
    MFPP, 
    TCI,
    ethanol_production,
    biodiesel_production,
    electricity_production,
    natural_gas_consumption
)

tea_monte_carlo_derivative_metric_mockups = (
    MFPP_derivative, 
    TCI_derivative,
    ethanol_production_derivative,
    biodiesel_production_derivative,
    electricity_production_derivative,
    natural_gas_consumption_derivative,
)

lca_monte_carlo_metric_mockups = (
    GWP_biodiesel, 
    GWP_ethanol,
    GWP_electricity,
    GWP_crude_glycerol,
)

lca_monte_carlo_derivative_metric_mockups = (
    GWP_biodiesel_derivative, 
    GWP_ethanol_derivative,
    GWP_electricity_derivative,
    GWP_crude_glycerol_derivative,
)

def asconfiguration(x):
    number, agile = x
    return Configuration(int(number), bool(agile))

def ascomparison(x):
    a, b = x
    return ConfigurationComparison(asconfiguration(a), asconfiguration(b))

class Configuration(NamedTuple):
    number: int
    agile: bool = False
   
class ConfigurationComparison(NamedTuple):
    a: Configuration
    b: Configuration

def name_to_configuration(name):
    name = name.replace(' ', '')
    return Configuration((-1 if name.startswith('S') else 1) * int(name[1]), '*' in name)

def parse(x):
    try:
        return asconfiguration(x)
        return ascomparison(x)
    except:
        pass
    if isinstance(x, int):
        return Configuration(x)
    elif isinstance(x, str):
        x = x.upper()
        left, *right = x.split('-')
        if right:
            if len(right) == 1:
                right = right[0]
                return ConfigurationComparison(
                    name_to_configuration(left),
                    name_to_configuration(right)
                )
            else:
                raise RuntimeError('cannot parse multiple subtractions')
        else:
            factor = -1 if x.startswith('S') else 1
            return Configuration(factor * int(x[1]), '*' in x)
    raise ValueError(f'could not parse {x}')
    

def format_name(name):
    key = parse(name)
    if isinstance(key, Configuration):
        return format_configuration(key)
    elif isinstance(key, ConfigurationComparison):
        return format_comparison(key)
    else:
        raise Exception('unknown error')

def format_configuration(configuration):
    number, agile = configuration
    if number == -2:
        name = 'S2'
    elif number == -1:
        name = 'S1'
    elif number == 0:
        name = '∅'
    elif number == 1:
        name = 'O1'
    elif number == 2:
        name = 'O2'
    else:
        raise ValueError(f'invalid configuration {configuration}')
    name = r'$\mathtt{' + name + '}$'
    if agile: name += '*'
    return name

def format_comparison(comparison):
    return ' $-$ '.join([format_configuration(i) for i in comparison])

def load_chemicals():
    global chemicals, _chemicals_loaded
    chemicals = create_chemicals()
    _chemicals_loaded = True

def sorghum_feedstock(ID):
    return bst.Stream(
        ID=ID, phase='l', T=298.15, P=101325, 
        Water=2.333e+05, Glucose=3703, Sucrose=4.196e+04, Ash=2000, 
        Cellulose=2.227e+04, Hemicellulose=1.314e+04, Lignin=1.193e+04, 
        Solids=5000, units='kg/hr'
    )

def disable_derivative(disable=True):
    global _derivative_disabled
    _derivative_disabled = disable
    
def enable_derivative(enable=True):
    global _derivative_disabled
    _derivative_disabled = not enable
    
_derivative_disabled = True

def load(name, cache={}, reduce_chemicals=True, enhanced_cellulosic_performance=False):
    dct = globals()
    number, agile = dct['configuration'] = parse(name)
    key = (number, agile, enhanced_cellulosic_performance)
    if key in cache:
        dct.update(cache[key])
        return
    global oilcane_sys, sys, tea, specs, flowsheet, _system_loaded
    global oil_extraction_specification, model, unit_groups
    global HXN, BT
    if not _chemicals_loaded: load_chemicals()
    flowsheet = bst.Flowsheet('oilcane')
    main_flowsheet.set_flowsheet(flowsheet)
    bst.settings.set_thermo(chemicals)
    load_process_settings()
    u = flowsheet.unit
    s = flowsheet.stream
    operating_hours = 24 * 200
    
    ## System
    
    area_names = None
    def rename_storage_units(storage):
        bst.rename_units([i for i in oilcane_sys.units if bst.is_storage_unit(i)], storage)
    
    if number == -1:
        isplit_efficiency_is_reversed = None
        # starting_chemicals = create_starting_chemicals()
        # bst.settings.set_thermo(starting_chemicals)
        oilcane_sys = create_sugarcane_to_ethanol_system(
            operating_hours=operating_hours,
            use_area_convention=True,
            pellet_bagasse=True,
        )
        area_names = [
            'Feedstock handling', 
            'Juicing', 
            'EtOH prod.', 
            'CH&P',
            'Utilities',
            'HXN',
            'Storage',
        ]
        rename_storage_units(700)
    elif number == -2:
        isplit_efficiency_is_reversed = None
        oilcane_sys = create_sugarcane_to_ethanol_combined_1_and_2g(
            operating_hours=operating_hours,
        )
        area_names = [
            'Feedstock handling', 
            'Juicing', 
            'Pretreatment',
            'EtOH prod.',
            'Wastewater treatment',
            'CH&P', 
            'Utilities',
            'HXN',
            'Storage',
        ]
        rename_storage_units(900)
    elif number == 1:
        isplit_efficiency_is_reversed = False
        oilcane_sys = create_oilcane_to_biodiesel_and_ethanol_1g(
            operating_hours=operating_hours,
        )
        area_names = [
            'Feedstock handling', 
            'Juicing', 
            'EtOH prod.', 
            'Oil ext.',
            'Biod. prod.', 
            'CH&P',
            'Utilities',
            'HXN',
            'Storage',
        ]
        rename_storage_units(1000)
    elif number == 2:
        isplit_efficiency_is_reversed = True
        area_names = [
            'Feedstock handling', 
            'Juicing', 
            'Pretreatment',
            'EtOH prod.',
            'Wastewater treatment',
            'Oil ext.',
            'CH&P', 
            'Biod. prod.',
            'Utilities',
            'HXN',
            'Storage',
        ]
        oilcane_sys = create_oilcane_to_biodiesel_and_ethanol_combined_1_and_2g_post_fermentation_oil_separation(
            operating_hours=operating_hours,
        )
        rename_storage_units(1100)
    else:
        raise NotImplementedError(number)
    oilcane_sys.set_tolerance(rmol=1e-5, mol=1e-3, subsystems=True)
    dct.update(flowsheet.to_dict())
    class MockStream:
        __slots__ = ('ID', 'price',)
        line = 'Stream'
        characterization_factors = {}
        
        def __init__(self, ID): 
            dct[ID] = self
            self.price = 0.
            self.ID = ID
            
        @property
        def F_vol(self): return 0.
        @property
        def F_mass(self): return 0.
        @property
        def F_mol(self): return 0.
        @property
        def cost(self): return 0.
    
    def get_stream(ID):
        return dct.get(ID) or MockStream(ID)
    
    crude_glycerol = get_stream('crude_glycerol')
    pure_glycerine = get_stream('pure_glycerine')
    if number == 1:
        oilcane_sys.prioritize_unit(T608)
    elif number == 2:
        oilcane_sys.prioritize_unit(T808)
    if number < 0:
        dct['oilcane'] = oilcane = sugarcane
        dct['oilcane_sys'] = oilcane_sys
    else:
        oilcane = dct['oilcane']
    unit_groups = UnitGroup.group_by_area(oilcane_sys.units)
    if area_names:
        for i, j in zip(unit_groups, area_names): i.name = j
    for i in unit_groups: i.autofill_metrics(shorthand=True)
    
    for BT in oilcane_sys.units:
        if isinstance(BT, bst.BoilerTurbogenerator): break

    HXN = None
    for HXN_group in unit_groups:
        if HXN_group.name == 'HXN':
            HXN_group.filter_savings = False
            HXN = HXN_group.units[0]
            assert isinstance(HXN, bst.HeatExchangerNetwork)
    unit_groups[-1].metrics[-1].getter = lambda: 0.    
    
    
    if abs(number) == 2:
        prs, = flowsheet(cs.units.PretreatmentReactorSystem)
        saccharification, = flowsheet(cs.units.Saccharification)
        seed_train, = flowsheet(cs.units.SeedTrain)
        fermentor, = flowsheet(cs.units.CoFermentation)
        dct['pretreatment_rxnsys'] = tmo.ReactionSystem(
            prs.reactions, saccharification.saccharification
        )
        dct['fermentation_rxnsys'] = tmo.ReactionSystem(
            seed_train.reactions, fermentor.cofermentation
        )
        dct['cellulosic_rxnsys'] = tmo.ReactionSystem(
            prs.reactions, saccharification.saccharification,
            seed_train.reactions, fermentor.cofermentation
        )
        saccharification.saccharification.X[0] = 0.0 # Baseline
        prs.reactions.X[10] = 0.0 # baseline
            
    def set_glucose_yield(glucose_yield):
        if abs(number) == 2:
            glucose_yield *= 0.01
            X1 = prs.reactions.X[0]
            X1_side = prs.reactions.X[1:3].sum()
            X2_side = saccharification.saccharification.X[:2].sum()
            saccharification.saccharification.X[2] = X2 = (glucose_yield - X1) / (1 - X1_side)
            X_excess = (X2_side + X2) - 1
            if X_excess > 0: breakpoint()
            
    def set_xylose_yield(xylose_yield):
        if abs(number) == 2:
            xylose_yield *= 0.01
            X1_side = prs.reactions.X[9:11].sum()
            prs.reactions.X[8] = X1 = xylose_yield
            X_excess = (X1_side + X1) - 1
            if X_excess > 0.: breakpoint()
    
    if agile: 
        dct['oilsorghum'] = oilsorghum = sorghum_feedstock(ID='oilsorghum')
        
        sys = bst.AgileSystem()
        @sys.operation_parameter(mode_dependent=True)
        def set_oil_content(oil_content, mode):
            if number > 0: 
                set_oil_fraction(oil_content, oilcane,
                                 FFA_fraction=mode.FFA_content,
                                 z_mass_carbs_baseline=mode.z_mass_carbs_baseline,
                                 PL_fraction=mode.PL_content)
            else:
                F_mass = oilcane.F_mass
                oilcane.copy_flow(mode.feedstock)
                oilcane.F_mass = F_mass
        sys.operation_parameter(set_glucose_yield)
        sys.operation_parameter(set_xylose_yield)
        
        dct['cane_mode'] = cane_mode = sys.operation_mode(oilcane_sys,
            operating_hours=200*24, oil_content=0.05, feedstock=oilcane.copy(),
            z_mass_carbs_baseline=0.1491, glucose_yield=85, xylose_yield=65, 
            FFA_content=0.10, PL_content=0.10
        )
        dct['sorghum_mode'] = sorghum_mode = sys.operation_mode(oilcane_sys, 
            operating_hours=60*24, oil_content=0.05, glucose_yield=79, xylose_yield=86,
            feedstock=oilsorghum,
            z_mass_carbs_baseline=0.1371, FFA_content=0.10, PL_content=0.10,
        )
        feedstocks = [oilcane]
        tea = create_tea(sys)
        tea.operating_days = 260 
        tea.IRR = 0.10
    else:
        sys = oilcane_sys
        tea = create_tea(sys)
        tea.operating_days = 200
        tea.IRR = 0.10
        feedstocks = [oilcane]
        
        # def electricity_GWP():
        #     power_utility = bst.PowerUtility.sum([i.power_utility for i in sys.cost_units])
        #     return power_utility.get_impact(production_key=GWP) * sys.operating_hours
        
    tea.income_tax = 0.21 # Davis et al. 2018; https://www.nrel.gov/docs/fy19osti/71949.pdf
    
    ## Specification for analysis
    if number < 0:
        dct['biodiesel'] = bst.Stream('biodiesel')
        isplit_a = None
        isplit_b = None
        oil_extraction_specification = MockExtractionSpecification()
    else:
        for i in oilcane_sys.cost_units:
            if getattr(i, 'tag', None) == 'oil extraction efficiency':
                isplit_a = i.isplit
                break
        
        for i in oilcane_sys.cost_units:
            if getattr(i, 'tag', None) == 'bagasse oil retention':
                isplit_b = i.isplit
                break
        
        oil_extraction_specification = OilExtractionSpecification(
            sys, feedstocks, isplit_a, isplit_b, isplit_efficiency_is_reversed
        )
    
    ## LCA
    # All values in cradle-to-gate except for CH4, which is in cradle-to-grave
    GWP_characterization_factors = { # Material GWP cradle-to-gate [kg*CO2*eq / kg]
        'sugarcane': 0.02931 * 0.30 / 0.25, # GREET, modified from moisture content of 0.75 to 0.70
        'sweet sorghum': 0.02821 * 0.30 / 0.25, # GREET, modified from moisture content of 0.75 to 0.70
        #'feedstock': 0.0607, # dry basis, Ecoinvent 2021
        'protease': 8.07, # Assume same as cellulase
        'cellulase': 8.07, # GREET
        'H3PO4': 1.00, # GREET
        'lime': 1.164, # GREET
        'pure-glycerol': 1.6678, # Ecoinvent, TRACI, market for glycerine, RoW; 
        # 'crude-glycerol': 0.36, # GREET
        'DAP': 1.66, # GREET
        'CSL': 1.56, # GREET
        'HCl': 1.96, # GREET
        'NaOH': 2.01, # GREET
        'gasoline': 0.88, # GREET
        'methanol': 0.45, # GREET, Natural gas to methanol
        'NaOCH3': 1.5871, # Ecoinvent, TRACI, sodium methoxide
        'CH4': 0.33 + chemicals.CO2.MW / chemicals.CH4.MW, # Natural gas from shell conventional recovery, GREET
        # from thermosteam.units_of_measure import convert, Chemical
        # CH4 = Chemical('CH4')
        # CO2 = Chemical('CO2')
        # electricty_produced_per_kg_CH4 = - convert(0.8 * 0.85 * CH4.LHV / CH4.MW, 'kJ', 'kWhr')
        # GWP_per_kg_CH4 = 0.33 + CO2.MW / CH4.MW
        # GWP_per_kWhr = electricty_produced_per_kg_CH4 / GWP_per_kg_CH4
        # 'Electricity': 0.325 # [kg*CO2*eq / kWhr] Based on balance above
    }
    GWP = 'GWP'
    # bst.PowerUtility.characterization_factors[GWP] = GWP_characterization_factors['Electricity']
    
    # Set non-negligible characterization factors
    if abs(number) != 2:
        for i in ('FGD_lime', 'cellulase', 'DAP', 'CSL', 'caustic'): MockStream(i)
    if number < 0:
        for i in ('catalyst', 'methanol', 'HCl', 'NaOH', 'crude_glycerol', 'pure_glycerine'): MockStream(i)
    if abs(number) != 1:
        MockStream(('dryer_natural_gas'))
    oilcane.characterization_factors[GWP] = GWP_characterization_factors['sugarcane'] 
    enzyme.characterization_factors[GWP] = GWP_characterization_factors['protease'] * 0.10
    H3PO4.characterization_factors[GWP] = GWP_characterization_factors['H3PO4']
    lime.characterization_factors[GWP] = GWP_characterization_factors['lime'] * 0.046 # Diluted with water
    denaturant.characterization_factors[GWP] = GWP_characterization_factors['gasoline']
    FGD_lime.characterization_factors[GWP] = GWP_characterization_factors['lime'] * 0.451 # Diluted with water
    cellulase.characterization_factors[GWP] = GWP_characterization_factors['cellulase'] * 0.02
    DAP.characterization_factors[GWP] = GWP_characterization_factors['DAP']
    CSL.characterization_factors[GWP] = GWP_characterization_factors['CSL']
    caustic.characterization_factors[GWP] = GWP_characterization_factors['NaOH'] * 0.5
    catalyst.characterization_factors[GWP] = GWP_characterization_factors['methanol'] * 0.75 + GWP_characterization_factors['NaOH'] * 0.25
    methanol.characterization_factors[GWP] = GWP_characterization_factors['methanol']
    HCl.characterization_factors[GWP] = GWP_characterization_factors['HCl']
    NaOH.characterization_factors[GWP] = GWP_characterization_factors['NaOH']
    # crude_glycerol.characterization_factors[GWP] = GWP_characterization_factors['crude-glycerol']
    pure_glycerine.characterization_factors[GWP] = GWP_characterization_factors['pure-glycerol']
    dryer_natural_gas.characterization_factors[GWP] = GWP_characterization_factors['CH4']
    natural_gas_streams = [natural_gas]
    if abs(number) == 1: natural_gas_streams.append(dryer_natural_gas)
    for s in natural_gas_streams:
        s.characterization_factors[GWP] = GWP_characterization_factors['CH4']
    
    ## Model
    model = bst.Model(sys, exception_hook='raise', retry_evaluation=False)
    parameter = model.parameter
    metric = model.metric
    
    def uniform(lb, ub, *args, **kwargs):
        return parameter(*args, distribution=shape.Uniform(lb, ub), bounds=(lb, ub), **kwargs)
    
    def default(baseline, *args, **kwargs):
        lb = 0.75*baseline
        ub = 1.25*baseline
        return parameter(*args, distribution=shape.Uniform(lb, ub), bounds=(lb, ub), **kwargs)
    
    def triangular(lb, mid, ub, *args, **kwargs):
        return parameter(*args, distribution=shape.Triangle(lb, mid, ub), bounds=(lb, ub), **kwargs)
    
    # def default_gwp(obj, units='kg*CO2-eq/kg'):
    #     if isinstance(obj, str):
    #         def f(value): pass
    #         return parameter(f, distribution=shape.Uniform(0, 1), bounds=(0, 1),
    #                          element=bst.Stream(obj), name='GWP-CF', units=units)
    #     else:
    #         def f(value): obj.characterization_factors[GWP] = value
    #         # f.__name__ = 'set_' + obj.ID + '_GWPCF'
    #         baseline = obj.characterization_factors[GWP]
    #         lb = 0.75 * baseline
    #         ub = 1.25 * baseline
    #         return parameter(f, distribution=shape.Uniform(lb, ub), bounds=(lb, ub),
    #                          element=obj, name='GWP-CF', units=units)
    
    # Currently at ~5%, but total oil content is past 10%
    
    @uniform(40, 70, units='%', kind='coupled')
    def set_bagasse_oil_retention(oil_retention):
        oil_extraction_specification.load_oil_retention(oil_retention / 100.)
    
    def oil_extraction_efficiency_hook(x):
        if number < 0:
            return x
        elif number == 1:
            return 50.0 + x
        elif number == 2:
            return 70.0 + x
    
    @uniform(0., 20, units='%', kind='coupled', 
             hook=oil_extraction_efficiency_hook)
    def set_bagasse_oil_extraction_efficiency(bagasse_oil_extraction_efficiency):
        oil_extraction_specification.load_efficiency(bagasse_oil_extraction_efficiency / 100.)

    capacity = oilcane.F_mass / kg_per_ton
    @uniform(0.75 * capacity, 1.25 * capacity, units='ton/hr', kind='coupled')
    def set_plant_capacity(capacity):
        oilcane.F_mass = F_mass = kg_per_ton * capacity
        if agile: oilsorghum.F_mass = F_mass

    # USDA ERS historical price data
    @parameter(distribution=ethanol_price_distribution, element=ethanol, units='USD/gal')
    def set_ethanol_price(price): # Triangular distribution fitted over the past 10 years Sep 2009 to Nov 2020
        ethanol.price = price / 2.98668849

    # USDA ERS historical price data
    @parameter(distribution=biodiesel_minus_ethanol_price_distribution, element=biodiesel, units='USD/gal',
               hook=lambda x: ethanol.price * 2.98668849 + x)
    def set_biodiesel_price(price): # Triangular distribution fitted over the past 10 years Sep 2009 to March 2021
        biodiesel.price = price / 3.3111

    # https://www.eia.gov/energyexplained/natural-gas/prices.php
    @parameter(distribution=natural_gas_price_distribution, element=natural_gas, units='USD/cf')
    def set_natural_gas_price(price): # Triangular distribution fitted over the past 10 years Sep 2009 to March 2021
        BT.natural_gas_price = 51.92624700383502 * price / 1000. 

    # https://www.eia.gov/outlooks/aeo/pdf/00%20AEO2021%20Chart%20Library.pdf
    # Data from historical prices, 2010-2020
    @triangular(0.0583, 0.065, 0.069, units='USD/kWh')
    def set_electricity_price(electricity_price): 
        bst.PowerUtility.price = electricity_price
        
    # From Huang's 2016 paper
    @uniform(6 * 30, 7 * 30, units='day/yr')
    def set_operating_days(operating_days):
        if agile:
            cane_mode.operating_hours = operating_days * 24
        else:
            tea.operating_days = operating_days
    
    # 10% is suggested for waste reducing, but 15% is suggested for investment
    @uniform(10., 15., units='%')
    def set_IRR(IRR):
        tea.IRR = IRR / 100.
    
    @uniform(0.10, 0.22, units='USD/kg', element=crude_glycerol)
    def set_crude_glycerol_price(price):
        crude_glycerol.price = price

    pure_glycerine_base_price = 0.65
    @uniform(0.75 * pure_glycerine_base_price, 1.25 * pure_glycerine_base_price,
             units='USD/kg', element=pure_glycerine)
    def set_pure_glycerol_price(price):
        pure_glycerine.price = price
    
    @default(72, units='hr', element='Saccharification')
    def set_saccharification_reaction_time(reaction_time):
        if abs(number) == 2: saccharification.tau = reaction_time
    
    cellulase_base_cost = 0.212
    @uniform(0.75 * cellulase_base_cost, 1.25 * cellulase_base_cost, units='USD/kg', element='cellulase')
    def set_cellulase_price(price):
        if abs(number) == 2: cellulase.price = price
    
    cellulase_loading = 0.02
    @uniform(0.75 * cellulase_loading, 1.25 * cellulase_loading, units='wt. % cellulose', element='cellulase')
    def set_cellulase_loading(cellulase_loading):
        if abs(number) == 2: M302.cellulase_loading = cellulase_loading
    
    PRS_base_cost = PRS_cost_item.cost
    @uniform(0.75 * PRS_base_cost, 1.25 * PRS_base_cost, units='million USD', element='Pretreatment reactor system')
    def set_reactor_base_cost(base_cost):
        PRS_cost_item.cost = base_cost
    
    @uniform(85, 97.5, units='%', element='Pretreatment and saccharification')
    def set_cane_glucose_yield(cane_glucose_yield):
        if agile:
            cane_mode.glucose_yield = cane_glucose_yield
        elif abs(number) == 2:
            set_glucose_yield(cane_glucose_yield)
    
    @uniform(79, 97.5, units='%', element='Pretreatment and saccharification')
    def set_sorghum_glucose_yield(sorghum_glucose_yield):
        if not agile: return
        sorghum_mode.glucose_yield = sorghum_glucose_yield
        
    @uniform(65, 97.5, units='%', element='Pretreatment and saccharification')
    def set_cane_xylose_yield(cane_xylose_yield):
        if agile:
            cane_mode.xylose_yield = cane_xylose_yield
        elif abs(number) == 2:
            set_xylose_yield(cane_xylose_yield)
    
    @uniform(86, 97.5, units='%', element='Pretreatment and saccharification')
    def set_sorghum_xylose_yield(sorghum_xylose_yield):
        if not agile: return
        sorghum_mode.xylose_yield = sorghum_xylose_yield
    
    @uniform(90, 95, units='%', element='Cofermenation')
    def set_glucose_to_ethanol_yield(glucose_to_ethanol_yield):
        if abs(number) == 2:
            glucose_to_ethanol_yield *= 0.01
            # fermentor.cofermentation[2].X = 0.004 # Baseline
            # fermentor.cofermentation[3].X = 0.006 # Baseline
            # fermentor.loss[0].X = 0.03 # Baseline
            split = np.mean(S403.split)
            X1 = split * seed_train.reactions.X[0]
            X3 = (glucose_to_ethanol_yield - X1) / (1 / (1 - X1)) 
            X_excess = X3 - 1
            if X_excess > 0.: breakpoint()
            fermentor.cofermentation.X[0] = X3
    
    @uniform(50, 95, units='%', element='Cofermenation')
    def set_xylose_to_ethanol_yield(xylose_to_ethanol_yield):
        if abs(number) == 2:
            # fermentor.cofermentation[6].X = 0.004 # Baseline
            # fermentor.cofermentation[7].X = 0.046 # Baseline
            # fermentor.cofermentation[8].X = 0.009 # Baseline
            # fermentor.loss[1].X = 0.03 # Baseline
            xylose_to_ethanol_yield *= 0.01
            split = np.mean(S403.split)
            X1 = split * seed_train.reactions.X[1]
            X3 = (xylose_to_ethanol_yield - X1) / (1 / (1 - X1)) 
            X_excess = X3 - 1
            if X_excess > 0.: breakpoint()
            fermentor.cofermentation.X[1] = X3

    @uniform(68.5, 137, units='g/L', element='Cofermentation')
    def set_cofermentation_titer(titer):
        if abs(number) == 2: fermentor.titer = titer

    @uniform(0.951, 1.902, units='g/L', element='Cofermentation')
    def set_cofermentation_productivity(productivity):
        if abs(number) == 2: fermentor.productivity = productivity

    @default(10, element='oilcane', units='% oil', kind='coupled')
    def set_cane_PL_content(cane_PL_content):
        if agile: cane_mode.PL_content = cane_PL_content / 100.
        else: oil_extraction_specification.PL_content = cane_PL_content / 100.
    
    @default(10, element='oilsorghum', units='% oil', kind='coupled')
    def set_sorghum_PL_content(sorghum_PL_content):
        if agile: sorghum_mode.PL_content = sorghum_PL_content / 100.
    
    @default(10, element='oilcane', units='% oil', kind='coupled')
    def set_cane_FFA_content(cane_FFA_content):
        if agile: cane_mode.FFA_content = cane_FFA_content / 100.
        else: oil_extraction_specification.FFA_content = cane_FFA_content / 100.
    
    @default(10, element='oilsorghum', units='% oil', kind='coupled')
    def set_sorghum_FFA_content(sorghum_FFA_content):
        if agile: sorghum_mode.FFA_content = sorghum_FFA_content / 100. 

    @uniform(5., 15., element='oilcane', units='dry wt. %', kind='coupled')
    def set_cane_oil_content(cane_oil_content):
        if agile:
            cane_mode.oil_content = cane_oil_content / 100.
        else:
            oil_extraction_specification.load_oil_content(cane_oil_content / 100.)

    @uniform(-3., 0., element='oilsorghum', units='dry wt. %', kind='coupled')
    def set_relative_sorghum_oil_content(relative_sorghum_oil_content):
        if agile:
            sorghum_mode.oil_content = cane_mode.oil_content + relative_sorghum_oil_content / 100.

    @default(23, units='% oil', kind='coupled', name='TAG to FFA conversion')
    def set_TAG_to_FFA_conversion(TAG_to_FFA_conversion):
        if number == 1:
            R301.oil_reaction.X[0] = TAG_to_FFA_conversion / 100.
        elif number == 2:
            R401.oil_reaction.X[0] = TAG_to_FFA_conversion / 100.
    
    @default(oilcane.characterization_factors[GWP], name='GWP', 
             element=oilcane, units='kg*CO2-eq/kg')
    def set_oilcane_GWP(value):
        if number > 1:
            oilcane.characterization_factors[GWP] = value
    
    @default(methanol.characterization_factors[GWP], name='GWP', 
             element=methanol, units='kg*CO2-eq/kg')
    def set_methanol_GWP(value):
        methanol.characterization_factors[GWP] = value
    
    # @default(crude_glycerol.characterization_factors[GWP], name='GWP', 
    #          element=crude_glycerol, units='kg*CO2-eq/kg')
    # def set_crude_glycerol_GWP(value):
    #     crude_glycerol.characterization_factors[GWP] = value
    
    @default(pure_glycerine.characterization_factors[GWP], name='GWP', 
             element=pure_glycerine, units='kg*CO2-eq/kg')
    def set_pure_glycerine_GWP(value):
        pure_glycerine.characterization_factors[GWP] = value
    
    @default(cellulase.characterization_factors[GWP], name='GWP', 
             element=cellulase, units='kg*CO2-eq/kg')
    def set_cellulase_GWP(value):
        cellulase.characterization_factors[GWP] = value
    
    natural_gas.phase = 'g'
    natural_gas.set_property('T', 60, 'degF')
    natural_gas.set_property('P', 14.73, 'psi')
    original_value = natural_gas.imol['CH4']
    natural_gas.imass['CH4'] = 1 
    V_ng = natural_gas.get_total_flow('ft3/hr')
    natural_gas.imol['CH4'] = original_value
    
    if agile:
        feedstock_flow = lambda: sum([sys.flow_rates[i] for i in feedstocks]) / kg_per_ton # ton/yr
        biodiesel_flow = lambda: sys.flow_rates.get(biodiesel, 0.) / 3.3111 # gal/yr
        ethanol_flow = lambda: sys.flow_rates[ethanol] / 2.98668849 # gal/yr
        natural_gas_flow = lambda: sum([sys.flow_rates[i] for i in natural_gas_streams]) * V_ng # cf/yr
        
        @sys.operation_metric(annualize=True)
        def electricity(mode):
            power_utility = bst.PowerUtility.sum([i.power_utility for i in mode.system.cost_units])
            return power_utility.rate
        
    else:
        feedstock_flow = lambda: sys.operating_hours * oilcane.F_mass / kg_per_ton # ton/yr
        biodiesel_flow = lambda: sys.operating_hours * biodiesel.F_mass / 3.3111 # gal/yr
        ethanol_flow = lambda: sys.operating_hours * ethanol.F_mass / 2.98668849 # gal/yr
        crude_glycerol_flow = lambda: sys.operating_hours * crude_glycerol.F_mass # kg/yr
        natural_gas_flow = lambda: sum([i.F_mass for i in natural_gas_streams]) * sys.operating_hours * V_ng # cf/yr
        if number <= 1:
            electricity = lambda: sys.operating_hours * sum([i.rate for i in oilcane_sys.power_utilities])
        elif number == 2:
            electricity = lambda: 0.
    dct['flows'] = flows = {'feedstock': feedstock_flow,
                            'biodiesel': biodiesel_flow,
                            'ethanol': ethanol_flow,
                            'natural_gas': natural_gas_flow,
                            'electricity': electricity}
    @metric(units='USD/ton')
    def MFPP():
        price = tea.solve_price(feedstocks)
        return kg_per_ton * price
    
    @metric(units='Gal/ton')
    def biodiesel_production():
        return biodiesel_flow() / feedstock_flow()
    
    @metric(units='Gal/ton')
    def ethanol_production():
        return ethanol_flow() / feedstock_flow()
    
    @metric(units='kWhr/ton')
    def electricity_production():
        value = - electricity() / feedstock_flow() 
        if value < 0.: value = 0.
        return value
    
    @metric(units='cf/ton')
    def natural_gas_consumption():
        value = natural_gas_flow() / feedstock_flow()
        return value
    
    @metric(units='10^6*USD')
    def TCI():
        return tea.TCI / 1e6 # 10^6*$
    
    @metric(units='ton/yr')
    def feedstock_consumption():
        return feedstock_flow()
    
    @metric(units='%')
    def heat_exchanger_network_error():
        return HXN.energy_balance_percent_error if HXN else 0.    

    @metric(name='GWP', element='Economic allocation', units='kg*CO2*eq / USD')
    def GWP_economic(): # Cradle to gate
        GWP_material = sys.get_total_feeds_impact(GWP) # kg CO2 eq. / yr
        sales = (
            biodiesel_flow() * mean_biodiesel_price
            + ethanol_flow() * mean_ethanol_price
            + crude_glycerol_flow() * mean_glycerol_price
            + max(-electricity(), 0) * mean_electricity_price
        )
        return GWP_material / sales

    @metric(name='Ethanol GWP', element='Ethanol', units='kg*CO2*eq / (ethanol*gal)')
    def GWP_ethanol(): # Cradle to gate
        try:
            return GWP_economic.cache * mean_ethanol_price
        except:
            return GWP_economic() * mean_ethanol_price
    
    @metric(name='Biodiesel GWP', element='Biodiesel', units='kg*CO2*eq / (biodiesel*gal)')
    def GWP_biodiesel(): # Cradle to gate
        if number > 0:
            try:
                return GWP_economic.cache * mean_biodiesel_price
            except:
                return GWP_economic() * mean_biodiesel_price
        else:
            return 0.
    
    @metric(name='Crude glycerol GWP', element='Crude glycerol', units='kg*CO2*eq / (crude-glycerol*gal)')
    def GWP_crude_glycerol(): # Cradle to gate
        if number > 0:
            try:
                return GWP_economic.cache * mean_glycerol_price
            except:
                return GWP_economic() * mean_glycerol_price
        else:
            return 0.
    
    @metric(name='Electricity GWP', element='Electricity', units='kg*CO2*eq / (biodiesel*gal)')
    def GWP_electricity(): # Cradle to gate
        if abs(number) == 1:
            try:
                return GWP_economic.cache * mean_electricity_price
            except:
                return GWP_economic() * mean_electricity_price
        else:
            return 0.

    @metric(units='USD/ton')
    def MFPP_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        if agile:
            cane_mode.oil_content += 0.01
            sorghum_mode.oil_content += 0.01
        else:
            oil_extraction_specification.load_oil_content(oil_extraction_specification.oil_content + 0.01)
        sys.simulate()  
        # value = (kg_per_ton * tea.solve_price(oilcane) - MFPP.cache)
        # oilcane.price = tea.solve_price(oilcane)
        # print('AFTER')
        # print('MFPP', kg_per_ton * tea.solve_price(oilcane))
        # print('VOC', tea.VOC / 1e3)
        # print('TCI', tea.TCI / 1e6)
        # print('sales', tea.sales / 1e3)
        # print('NPV', tea.NPV)
        return MFPP.difference()
    
    @metric(units='Gal/ton')
    def biodiesel_production_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        return biodiesel_production.difference()
    
    @metric(units='Gal/ton')
    def ethanol_production_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        return ethanol_production.difference()
    
    @metric(units='kWhr/ton')
    def electricity_production_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        return electricity_production.difference()
    
    @metric(units='cf/ton')
    def natural_gas_consumption_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        # print('natural gas production derivative', value)
        return natural_gas_consumption.difference()
    
    @metric(units='10^6*USD')
    def TCI_derivative():
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        return TCI.difference()
    
    @metric(name='GWP derivative', element='Economic allocation', units='kg*CO2*eq / USD')
    def GWP_economic_derivative(): # Cradle to gate
        if number < 0: return 0.
        if _derivative_disabled: return np.nan
        return GWP_economic.difference()

    @metric(name='Ethanol GWP derivative', element='Ethanol', units='kg*CO2*eq / (ethanol*gal)')
    def GWP_ethanol_derivative(): # Cradle to gate
        try:
            return GWP_economic_derivative.cache * mean_ethanol_price
        except:
            return GWP_economic_derivative() * mean_ethanol_price
    
    @metric(name='Biodiesel GWP derivative', element='Biodiesel', units='kg*CO2*eq / (biodiesel*gal)')
    def GWP_biodiesel_derivative(): # Cradle to gate
        if number > 0:
            try:
                return GWP_economic_derivative.cache * mean_biodiesel_price
            except:
                return GWP_economic_derivative() * mean_biodiesel_price
        else:
            return 0.
    
    @metric(name='Crude glycerol GWP derivative', element='Crude glycerol', units='kg*CO2*eq / (crude-glycerol*gal)')
    def GWP_crude_glycerol_derivative(): # Cradle to gate
        if number > 0:
            try:
                return GWP_economic_derivative.cache * mean_glycerol_price
            except:
                return GWP_economic_derivative() * mean_glycerol_price
        else:
            return 0.
    
    @metric(name='Electricity GWP derivative', element='Electricity', units='kg*CO2*eq / (biodiesel*gal)')
    def GWP_electricity_derivative(): # Cradle to gate
        if abs(number) == 1:
            try:
                return GWP_economic_derivative.cache * mean_electricity_price
            except:
                return GWP_economic_derivative() * mean_electricity_price
        else:
            return 0.
    
    # @metric(units='MMGGE/yr')
    # def productivity():
    #     GGE = (ethanol_flow() / 1.5
    #         + biodiesel_flow() / 0.9536
    #         - electricity() * 3600 / 131760
    #         - natural_gas_flow() / 126.67)
    #     return GGE / 1e6
    
    
    # Single point evaluation for detailed design results
    if abs(number) == 2:
        if enhanced_cellulosic_performance:
            set_sorghum_glucose_yield.setter(95)
            set_sorghum_xylose_yield.setter(95)
            set_cane_glucose_yield.setter(95)
            set_cane_xylose_yield.setter(95)
            set_glucose_to_ethanol_yield.setter(95)
            set_xylose_to_ethanol_yield.setter(95)
            set_cofermentation_titer.setter(120.)
            set_cofermentation_productivity.setter(2.0)
        else:
            set_sorghum_glucose_yield.setter(79)
            set_sorghum_xylose_yield.setter(86)
            set_cane_glucose_yield.setter(85)
            set_cane_xylose_yield.setter(65)
            set_glucose_to_ethanol_yield.setter(91)
            set_xylose_to_ethanol_yield.setter(50.)
    oil_extraction_specification.load_oil_retention(0.70)
    oil_extraction_specification.load_oil_content(0.05)
    set_bagasse_oil_extraction_efficiency.setter(oil_extraction_efficiency_hook(0.))
    set_ethanol_price.setter(1.898) 
    set_biodiesel_price.setter(4.363)
    set_natural_gas_price.setter(4.3)
    set_electricity_price.setter(0.0641)
    if number > 0:
        set_cane_PL_content.setter(10)
        set_cane_FFA_content.setter(10)
    # set_fermentation_solids_loading(20) # Same as Humbird
    # set_feedstock_oil_content(10) # Consistent with SI of Huang's 2016 paper
    # set_ethanol_price(2.356) # Consistent with Huang's 2016 paper
    # set_biodiesel_price(4.569) # Consistent with Huang's 2016 paper
    # set_natural_gas_price(4.198) # Consistent with Humbird's 2012 paper
    # set_electricity_price(0.0572) # Consistent with Humbird's 2012 paper
    # set_operating_days(200) # Consistent with Huang's 2016 paper
    
    for i in model._parameters:
        dct[i.setter.__name__] = i
    for i in model._metrics:
        dct[i.getter.__name__] = i
    cache[key] = dct.copy()
    
    ## Simulation
    try: 
        sys.simulate()
    except Exception as e:
        raise e
    if reduce_chemicals:
        oilcane_sys.reduce_chemicals()
    oilcane_sys._load_stream_links()
    HXN.force_ideal_thermo = True
    HXN.cache_network = True
    HXN.simulate()

def evaluate_configurations_across_extraction_efficiency_and_oil_content(
        efficiency, oil_content, oil_retention, agile, configurations,
    ):
    A = len(agile)
    C = len(configurations)
    M = len(all_metric_mockups)
    data = np.zeros([A, C, M])
    for ia in range(A):
        for ic in range(C):    
            load([int(configurations[ic]), agile[ia]])
            if agile[ia]:
                cane_mode.oil_content = sorghum_mode.oil_content = oil_content
                oil_extraction_specification.load_efficiency(efficiency)
                oil_extraction_specification.load_oil_retention(oil_retention)
            else:
                oil_extraction_specification.load_specifications(
                    efficiency=efficiency, 
                    oil_content=oil_content, 
                    oil_retention=oil_retention
                )
            sys.simulate()
            data[ia, ic, :] = [j() for j in model.metrics]
    return data

N_metrics = len(all_metric_mockups)
evaluate_configurations_across_extraction_efficiency_and_oil_content = np.vectorize(
    evaluate_configurations_across_extraction_efficiency_and_oil_content, 
    excluded=['oil_retention', 'agile', 'configurations'],
    signature=f'(),(),(),(a),(c)->(a,c,{N_metrics})'
)

def evaluate_configurations_across_sorghum_and_cane_oil_content(
        sorghum_oil_content, cane_oil_content, configurations, relative,
    ):
    C = len(configurations)
    M = len(all_metric_mockups)
    data = np.zeros([C, M])
    for ic in range(C):
        load([int(configurations[ic]), True])
        cane_mode.oil_content = cane_oil_content
        if relative:
            sorghum_mode.oil_content = cane_oil_content + sorghum_oil_content
        else:
            sorghum_mode.oil_content = sorghum_oil_content
        sys.simulate()
        data[ic, :] = [j() for j in model.metrics]
    return data

evaluate_configurations_across_sorghum_and_cane_oil_content = np.vectorize(
    evaluate_configurations_across_sorghum_and_cane_oil_content, 
    excluded=['configurations', 'relative'],
    signature=f'(),(),(c),()->(c,{N_metrics})'
)              

def evaluate_MFPP_uncertainty_across_ethanol_and_biodiesel_prices(name, ethanol_price, biodiesel_price):
    table = get_monte_carlo(name)
    oilcane_price = table[MFPP.index].to_numpy()[:, np.newaxis] # USD/ton
    biodiesel_flow = table[biodiesel_production.index].to_numpy()[:, np.newaxis] * 1e6 # gal/yr
    ethanol_price_baseline = table[set_ethanol_price.index].to_numpy()[:, np.newaxis]
    biodiesel_price_baseline = table[set_biodiesel_price.index].to_numpy()[:, np.newaxis]
    ethanol_flow = table[ethanol_production.index].to_numpy()[:, np.newaxis] * 1e6 # gal/yr
    feedstock_flow = table[feedstock_consumption.index].to_numpy()[:, np.newaxis] # ton/yr
    baseline_price = (
        oilcane_price
        - (ethanol_price_baseline * ethanol_flow + biodiesel_price_baseline * biodiesel_flow) / feedstock_flow
    )
    return (
        baseline_price 
        + (ethanol_price[np.newaxis, :] * ethanol_flow + biodiesel_price[np.newaxis, :] * biodiesel_flow) / feedstock_flow
    )

def evaluate_MFPP_benefit_uncertainty_across_ethanol_and_biodiesel_prices(name, ethanol_price, biodiesel_price, baseline=None):
    if baseline is None:
        configuration = parse(name)
        number, agile = configuration
        assert number > 0
        baseline = Configuration(-number, agile)
    MFPP_baseline = evaluate_MFPP_uncertainty_across_ethanol_and_biodiesel_prices(baseline, ethanol_price, biodiesel_price)
    MFPP = evaluate_MFPP_uncertainty_across_ethanol_and_biodiesel_prices(name, ethanol_price, biodiesel_price)
    return MFPP - MFPP_baseline

def evaluate_MFPP_across_ethanol_and_biodiesel_prices(ethanol_price, biodiesel_price, configuration=None):
    if configuration is not None: load(configuration)
    feedstock_flow = flows['feedstock']()
    biodiesel_flow = flows['biodiesel']()
    ethanol_flow = flows['ethanol']()
    baseline_price = (
        tea.solve_price(oilcane) * kg_per_ton
        - (ethanol.price * ethanol_flow  * 2.98668849 + biodiesel.price * 3.3111 * biodiesel_flow) / feedstock_flow
    )
    return (
        baseline_price 
        + (ethanol_price * ethanol_flow + biodiesel_price * biodiesel_flow) / feedstock_flow
    )

def evaluate_MFPP_benefit_across_ethanol_and_biodiesel_prices(ethanol_price, biodiesel_price, baseline=None, configuration=None):
    if configuration is None: configuration = globals()['configuration']
    if baseline is None:
        number, agile = configuration
        assert number > 0
        baseline = Configuration(-number, agile)
    MFPP_baseline = evaluate_MFPP_across_ethanol_and_biodiesel_prices(ethanol_price, biodiesel_price, baseline)
    MFPP = evaluate_MFPP_across_ethanol_and_biodiesel_prices(ethanol_price, biodiesel_price, configuration)
    return MFPP - MFPP_baseline

def spearman_file(name):
    number, agile = parse(name)
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = f'oilcane_spearman_{number}'
    if agile: filename += '_agile'
    filename += '.xlsx'
    return os.path.join(folder, filename)

def monte_carlo_file(name, across_oil_content=False):
    number, agile = parse(name)
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = f'oilcane_monte_carlo_{number}'
    if agile: filename += '_agile'
    if across_oil_content: filename += '_across_oil_content'
    filename += '.xlsx'
    return os.path.join(folder, filename)

def autoload_file_name(name):
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = name.replace('*', '_agile')
    return os.path.join(folder, filename)

def run_uncertainty_and_sensitivity(name, N, rule='L',
                                    across_oil_content=False, 
                                    sample_cache={},
                                    autosave=True,
                                    autoload=True):
    enable_derivative()
    try:
        np.random.seed(1)
        from warnings import filterwarnings
        filterwarnings('ignore', category=bst.utils.DesignWarning)
        load(name)
        key = (N, rule)
        if key in sample_cache:
            samples = sample_cache[key]
        else:
            sample_cache[key] = samples = model.sample(N, rule)
        model.load_samples(samples)
        file = monte_carlo_file(name, across_oil_content)
        if across_oil_content:
            if parse(name).number < 0:
                model.evaluate(notify=int(N/10))
                model.evaluate_across_coordinate(
                    name='Oil content',
                    f_coordinate=lambda x: None,
                    coordinate=oil_content,
                    notify=int(N/10), 
                    notify_coordinate=True,
                    xlfile=file,
                    re_evaluate=False,
                )
            else:
                def f(x):
                    oil_extraction_specification.locked_oil_content = False
                    oil_extraction_specification.load_oil_content(x)
                    oil_extraction_specification.locked_oil_content = True
                model.evaluate_across_coordinate(
                    name='Oil content',
                    f_coordinate=f,
                    coordinate=oil_content,
                    notify=int(N/10), 
                    notify_coordinate=True,
                    xlfile=file,
                )
        else:
            N = min(int(N/10), 50)
            model.evaluate(notify=N,
                           autosave=N if autosave else N,
                           autoload=autoload,
                           file=autoload_file_name(name))
            model.table.to_excel(file)
            rho, p = model.spearman_r()
            file = spearman_file(name)
            rho.to_excel(file)
    finally:
        disable_derivative()

run = run_uncertainty_and_sensitivity
    
def run_all(N, across_oil_content=False, rule='L', configurations=None, **kwargs):
    if configurations is None: configurations = configuration_names
    for name in configurations:
        print(f"Running {name}:")
        run_uncertainty_and_sensitivity(
            name, N, rule, across_oil_content, **kwargs
        )

def get_monte_carlo_across_oil_content(name, metric, derivative=False):
    key = parse(name)
    if isinstance(key, Configuration):
        df = pd.read_excel(
            monte_carlo_file(key, True),
            sheet_name=metric if isinstance(metric, str) else metric.short_description,
            index_col=0
        )
    elif isinstance(key, ConfigurationComparison):
        df = (
            get_monte_carlo_across_oil_content(key.a, metric)
            - get_monte_carlo_across_oil_content(key.b, metric)
        )
    else:
        raise Exception('unknown error')
    if derivative: 
        arr = np.diff(df.values) / np.diff(df.columns.values) / 100.
    else:
        arr = df.values
    return arr
        

def get_monte_carlo(name):
    key = parse(name)
    if isinstance(key, Configuration):
        file = monte_carlo_file(key)
        return pd.read_excel(file, header=[0, 1], index_col=[0])
    elif isinstance(key, ConfigurationComparison):
        index = [i.index for i in tea_monte_carlo_metric_mockups + tea_monte_carlo_derivative_metric_mockups]
        df_a = get_monte_carlo(key.a)[index]
        df_b = get_monte_carlo(key.b)[index]
        row_a = df_a.shape[0]
        row_b = df_b.shape[0]
        if row_a != row_b:
            length = min(row_a, row_b)
            return df_a.iloc[:length] - df_b.iloc[:length]
        else:
            return df_a - df_b
    else:
        raise Exception('unknown error')

def plot_monte_carlo_across_coordinate(coordinate, data, color_wheel):
    if isinstance(data, list):
        return [plot_monte_carlo_across_coordinate(coordinate, i, color_wheel) for i in data]
    else:
        color = color_wheel.next()
        return bst.plots.plot_montecarlo_across_coordinate(
            coordinate, data,
            light_color=color.tint(50).RGBn,
            dark_color=color.shade(50).RGBn,
        )

def plot_monte_carlo_across_oil_content(kind=0, derivative=False):
    MFPP, TCI, *production, electricity_production, natural_gas_consumption = tea_monte_carlo_metric_mockups
    rows = [MFPP, TCI, production]
    if kind == 0:
        columns = across_oil_content_names
    elif kind == 1:
        columns = across_oil_content_agile_names
    elif kind == 2:
        columns = across_oil_content_comparison_names
    elif kind == 3:
        columns = across_oil_content_agile_comparison_names
    elif kind == 4:
        columns = across_oil_content_agile_direct_comparison_names
    else:
        raise NotImplementedError(str(kind))
    if derivative:
        x = 100 * (oil_content[:-1] + np.diff(oil_content) / 2.)
        ylabels = [
            f"MFPP der. [{format_units('USD/ton')}]",
            f"TCI der. [{format_units('10^6*USD')}]",
            f"Production der. [{format_units('gal/ton')}]"
        ]
    else:
        x = 100 * oil_content
        ylabels = [
            f"MFPP$\backprime$ [{format_units('USD/ton')}]",
            f"TCI [{format_units('10^6*USD')}]",
            f"Production [{format_units('gal/ton')}]"
        ]
    N_cols = len(columns)
    N_rows = len(rows)
    fig, axes = plt.subplots(ncols=N_cols, nrows=N_rows)
    data = np.zeros([N_rows, N_cols], dtype=object)
    
    def get_data(metric, name):
        if isinstance(metric, bst.Variable):
            return get_monte_carlo_across_oil_content(name, metric, derivative)
        else:
            return [get_data(i, name) for i in metric]
    
    data = np.array([[get_data(i, j) for j in columns] for i in rows])
    tickmarks = [None] * N_rows
    get_max = lambda x: max([i.max() for i in x]) if isinstance(x, list) else x.max()
    get_min = lambda x: min([i.min() for i in x]) if isinstance(x, list) else x.min()
    N_ticks = 5
    for r in range(N_rows):
        lb = min(min([get_min(i) for i in data[r, :]]), 0)
        ub = max([get_max(i) for i in data[r, :]])
        diff = 0.1 * (ub - lb)
        ub += diff
        if derivative:
            lb = floor(lb)
            ub = ceil(ub)
            step = (ub - lb) / (N_ticks - 1)
            tickmarks[r] = [0, 1] if step == 0 else [int(lb + step * i) for i in range(N_ticks)]
        else:
            if rows[r] is MFPP:
                if kind == 0 or kind == 1:
                    tickmarks[r] = [-20, 0, 20, 40, 60]
                elif kind == 2:
                    tickmarks[r] = [-20, -10, 0, 10, 20]
                elif kind == 3:
                    tickmarks[r] = [-10, 0, 10, 20, 30]
                elif kind == 4:
                    tickmarks[r] = [-5, 0, 5, 10, 15]
                continue
            lb = floor(lb / 15) * 15
            ub = ceil(ub / 15) * 15
            step = (ub - lb) / (N_ticks - 1)
            tickmarks[r] = [0, 1] if step == 0 else [int(lb + step * i) for i in range(N_ticks)]
    color_wheel = CABBI_colors.wheel()
    for j in range(N_cols):
        color_wheel.restart()
        for i in range(N_rows):
            arr = data[i, j]
            ax = axes[i, j]
            plt.sca(ax)
            percentiles = plot_monte_carlo_across_coordinate(x, arr, color_wheel)
            if i == 0: ax.set_title(format_name(columns[j]))
            xticklabels = i == N_rows - 1
            yticklabels = j == 0
            if xticklabels: plt.xlabel('Oil content [dry wt. %]')
            if yticklabels: plt.ylabel(ylabels[i])
            bst.plots.style_axis(ax,  
                                 xticks = [5, 10, 15],
                                 yticks = tickmarks[i],
                                 xticklabels= xticklabels, 
                                 yticklabels= yticklabels,
                                 ytick0=False)
    for i in range(N_cols): fig.align_ylabels(axes[:, i])
    plt.subplots_adjust(hspace=0.1, wspace=0.1)

def monte_carlo_box_plot(data, positions, light_color, dark_color):
    return plt.boxplot(x=data, positions=positions, patch_artist=True,
                     widths=0.8, whis=[5, 95],
                     boxprops={'facecolor':light_color,
                               'edgecolor':dark_color},
                     medianprops={'color':dark_color,
                                  'linewidth':1.5},
                     flierprops = {'marker':'D',
                                   'markerfacecolor': light_color,
                                   'markeredgecolor': dark_color,
                                   'markersize':6})

def monte_carlo_results(with_units=False):
    results = {}
    ethanol_over_biodiesel = bst.MockVariable('Ethanol over biodiesel', 'Gal/ton', 'Biorefinery')
    for name in configuration_names + comparison_names + other_comparison_names:
        try: 
            df = get_monte_carlo(name)
        except:
            warn(f'could not load {name}', RuntimeWarning)
            continue
        results[name] = dct = {}
        if name in ('O1', 'O2'):
            index = ethanol_over_biodiesel.index
            key = index[1] if with_units else index[1].split(' [')[0]
            data = df[ethanol_production.index].values / df[biodiesel_production.index].values
            dct[key] = subdct = {
                'mean': np.mean(data),
                'std': np.std(data),
                'q05': q05,
                'q25': q25,
                'q50': q50,
                'q75': q75,
                'q95': q95,
            }
        for metric in (*tea_monte_carlo_metric_mockups, *tea_monte_carlo_derivative_metric_mockups,
                       *lca_monte_carlo_metric_mockups, *lca_monte_carlo_derivative_metric_mockups):
            index = metric.index
            data = df[index].values
            q05, q25, q50, q75, q95 = percentiles = np.percentile(data, [5,25,50,75,95], axis=0)
            key = index[1] if with_units else index[1].split(' [')[0]
            dct[key] = subdct = {
                'mean': np.mean(data),
                'std': np.std(data),
                'q05': q05,
                'q25': q25,
                'q50': q50,
                'q75': q75,
                'q95': q95,
            }
    results['(O2 - O1) / O1'] = relative_results = {}
    df_O2O1 = get_monte_carlo('O2 - O1')
    df_O1 = get_monte_carlo('O1')
    for metric in (biodiesel_production, ethanol_production):
        index = metric.index
        key = index[1] if with_units else index[1].split(' [')[0]
        data = (df_O2O1[index].values / df_O1[index].values)
        q05, q25, q50, q75, q95 = percentiles = np.percentile(data, [5,25,50,75,95], axis=0)
        relative_results[key] = subdct = {
            'mean': np.mean(data),
            'std': np.std(data),
            'q05': q05,
            'q25': q25,
            'q50': q50,
            'q75': q75,
            'q95': q95,
        }
    return results

def plot_monte_carlo(derivative=False, absolute=True, comparison=True,
                     configuration_names=configuration_names, comparison_names=comparison_names,
                     labels=None, tickmarks=None, kind=None):
    if kind is None: kind = 'TEA'
    if kind == 'TEA':
        if derivative:
            configuration_names = ['O1', 'O2']
            comparison_names = ['O2 - O1']
            MFPP, TCI, *production, electricity_production, natural_gas_consumption = tea_monte_carlo_derivative_metric_mockups
        else:
            MFPP, TCI, *production, electricity_production, natural_gas_consumption = tea_monte_carlo_metric_mockups
        combined = absolute and comparison
        if combined:
            columns = configurations = configuration_names + comparison_names
        elif absolute:
            columns = configurations = configuration_names
        elif comparison:
            columns = configurations = comparison_names
        else:
            columns = configurations = []
        N_cols = len(columns)
        rows = metrics = [
            MFPP, 
            TCI, 
            production,
            electricity_production,
            natural_gas_consumption,
            GWP_biofuel_allocation,
        ]
        N_rows = len(rows)
        fig, axes = plt.subplots(ncols=1, nrows=N_rows)
        axes = axes.flatten()
        xtext = labels or [format_name(i).replace(' ', '') for i in configurations]
        N_marks = len(xtext)
        xticks = tuple(range(N_marks))
        color_wheel = CABBI_colors.wheel()
        ylabels = [
            f"MFPP\n[{format_units('USD/ton')}]",
            f"TCI\n[{format_units('10^6*USD')}]",
            f"Production\n[{format_units('Gal/ton')}]",
            f"Elec. prod.\n[{format_units('kWhr/ton')}]",
            f"NG cons.\n[{format_units('cf/ton')}]",
            f"GWP\n[{format_units('kg CO2-eq/GGE')}]",
        ]
        if derivative:
            ylabels = [
                r"$\Delta$" + format_units(r"MFPP/OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('USD/ton')}]",
                r"$\Delta$" + format_units(r"TCI/OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('10^6*USD')}]",
                r"$\Delta$" + format_units(r"Prod./OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('Gal/ton')}]",
                r"$\Delta$" + format_units(r"EP/OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('kWhr/ton')}]",
                r"$\Delta$" + format_units(r"NGC/OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('cf/ton')}]"
                r"$\Delta$" + format_units(r"GWP/OC").replace('cdot', r'cdot \Delta') + f"\n[{format_units('kg CO2-eq/GGE')}]"
            ]
        elif comparison and not absolute:
            ylabels = [r"$\Delta$" + i for i in ylabels]
    elif kind == 'LCA':
        pass
        
    def get_data(metric, name):
        if isinstance(metric, bst.Variable):
            df = get_monte_carlo(name)
            values = df[metric.index].values
            return values
        else:
            return [get_data(i, name) for i in metric]
    
    def plot(arr, position):
        if isinstance(arr, list):
            return [plot(i, position) for i in arr]
        else:
            color = color_wheel.next()
            light_color = color.RGBn
            dark_color = color.shade(60).RGBn
            return monte_carlo_box_plot(
                    arr, (position,),
                    light_color=light_color,
                    dark_color=dark_color,
            )
    
    data = np.zeros([N_rows, N_cols], dtype=object)
    data = np.array([[get_data(i, j) for j in columns] for i in rows])
    step_min = 1 if derivative else 30
    if tickmarks is None: 
        tickmarks = [
            bst.plots.rounded_tickmarks_from_data(
                i, step_min=step_min, N_ticks=5, lb_max=0, center=0
            ) 
            for i in data
        ]
    color_wheel = CABBI_colors.wheel()

    x0 = len(configuration_names) - 0.5
    xf = len(columns) - 0.5
    for i in range(N_rows):
        ax = axes[i]
        plt.sca(ax)
        if combined:
            bst.plots.plot_vertical_line(x0)
            ax.axvspan(x0, xf, color=colors.purple_tint.tint(60).RGBn)
        plt.xlim(-0.5, xf)

    for j in range(N_cols):
        color_wheel.restart()
        for i in range(N_rows):
            ax = axes[i]
            plt.sca(ax)
            plot(data[i, j], j)
            plt.ylabel(ylabels[i])
    
    for i in range(N_rows):
        ax = axes[i]
        plt.sca(ax)
        yticks = tickmarks[i]
        plt.ylim([yticks[0], yticks[1]])
        if yticks[0] < 0.:
            bst.plots.plot_horizontal_line(0, color=CABBI_colors.black.RGBn, linestyle='--')
        bst.plots.style_axis(ax,  
            xticks = xticks,
            yticks = yticks,
            xticklabels= xtext, 
            ytick0=False,
            ytickf=False,
        )
    
    fig.align_ylabels(axes)
    plt.subplots_adjust(hspace=0)
    plt.sca(axes[1])
    # legend = plt.legend(
    #     handles=[
    #         mpatches.Patch(facecolor=color_wheel[0].RGBn, 
    #                        edgecolor=CABBI_colors.black.RGBn,
    #                        label='Oilcane only'),
    #         mpatches.Patch(facecolor=color_wheel[1].RGBn, 
    #                        edgecolor=CABBI_colors.black.RGBn,
    #                        label='Oilcane & oilsorghum'),
    #     ], 
    #     bbox_to_anchor=(0, 1, 1, 0), 
    #     loc="lower right", 
    #     # mode="expand", 
    #     # ncol=2
    # )
    # legend.get_frame().set_linewidth(0.0)

def plot_spearman(configuration, top=None, agile=True, labels=None, metric=None):
    if metric is None:
        metric = MFPP
    elif metric == 'MFPP':
        metric = MFPP
    elif metric == 'GWP':
        metric = GWP_biofuel_allocation
    stream_price = format_units('USD/gal')
    USD_ton = format_units('USD/ton')
    ng_price = format_units('USD/cf')
    electricity_price = format_units('USD/kWhr')
    operating_days = format_units('day/yr')
    capacity = format_units('ton/hr')
    titer = format_units('g/L')
    productivity = format_units('g/L/hr')
    material_GWP = format_units('kg*CO2-eq/kg')
    index, ignored_list = zip(*[
         ('Bagasse oil retention [40 $-$ 70 %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Oil extraction efficiency [baseline + 0 $-$ 20 %]', ['S2', 'S1', 'S2*', 'S1*']),
        (f'Plant capacity [330 $-$ 404 {capacity}]', []),
        (f'Ethanol price [1.02, 1.80, 2.87 {stream_price}]', []),
        (f'Biodiesel price relative to ethanol [0.31, 2.98, 4.11 {stream_price}]', []),
        (f'Natural gas price [3.71, 4.73, 6.18 {ng_price}]', ['S1', 'O1', 'S1*', 'O1*']),
        (f'Electricity price [0.0583, 0.065, 0.069 {electricity_price}]', ['S2', 'O2', 'S2*', 'O2*']),
        (f'Operating days [180 $-$ 210 {operating_days}]', []),
         ('IRR [10 $-$ 15 %]', []),
        (f'Crude glycerol price [91 $-$ 200 {USD_ton}]', ['S2', 'S1', 'S2*', 'S1*']),
        (f'Pure glycerol price [501 $-$ 678 {USD_ton}]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Saccharification reaction time [54 $-$ 90 hr]', ['S1', 'O1', 'S1*', 'O1*']),
        (f'Cellulase price [144 $-$ 240 {USD_ton}]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Cellulase loading [1.5 $-$ 2.5 wt. % cellulose]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Pretreatment reactor system base cost [14.9 $-$ 24.7 MMUSD]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Cane glucose yield [85 $-$ 97.5 %]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Sorghum glucose yield [85 $-$ 97.5 %]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Cane xylose yield [65 $-$ 97.5 %]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Sorghum xylose yield [65 $-$ 97.5 %]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Glucose to ethanol yield [90 $-$ 95 %]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Xylose to ethanol yield [50 $-$ 95 %]', ['S1', 'O1', 'S1*', 'O1*']),
        (f'Titer [65 $-$ 130 {titer}]', ['S1', 'O1', 'S1*', 'O1*']),
        (f'Productivity [1.0 $-$ 2.0 {productivity}]', ['S1', 'O1', 'S1*', 'O1*']),
         ('Cane PL content [7.5 $-$ 12.5 %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Sorghum PL content [7.5 $-$ 12.5 %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Cane FFA content [7.5 $-$ 12.5 %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Sorghum FFA content [7.5 $-$ 12.5 %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Cane oil content [5 $-$ 15 dry wt. %]', ['S2', 'S1', 'S2*', 'S1*']),
         ('Relative sorghum oil content [-3 $-$ 0 dry wt. %]', ['S2', 'S1', 'S2*', 'S1*', 'O2', 'O1']),
         ('TAG to FFA conversion [17.25 $-$ 28.75 % theoretical]', ['S1', 'O1', 'S1*', 'O1*']),
        (f'Feedstock GWP [0.0263 $-$ 0.0440 {material_GWP}]', []),
    ])
    ignored_dct = {
        'S1': [],
        'O1': [],
        'S2': [],
        'O2': [],
        'S1*': [],
        'O1*': [],
        'S2*': [],
        'O2*': [],
    }
    for i, ignored in enumerate(ignored_list):
        for name in ignored: ignored_dct[name].append(i)
    
    configuration_names = (configuration, configuration + '*') if agile else (configuration,)
    rhos = []
    for name in configuration_names:
        file = spearman_file(name)
        try: 
            df = pd.read_excel(file, header=[0, 1], index_col=[0, 1])
        except: 
            warning = RuntimeWarning(f"file '{file}' not found")
            warn(warning)
            continue
        s = df[metric.index]
        s.iloc[ignored_dct[name]] = 0.
        rhos.append(s)
    color_wheel = [CABBI_colors.orange, CABBI_colors.green_soft]
    fig, ax = bst.plots.plot_spearman_2d(rhos, top=top, index=index, 
                                         color_wheel=color_wheel,
                                         name=metric.name)
    plt.legend(
        handles=[
            mpatches.Patch(
                color=color_wheel[i].RGBn, 
                label=labels[i] if labels else format_name(configuration_names[i])
            )
            for i in range(len(configuration_names))
        ], 
        loc='upper left'
    )
    return fig, ax

def plot_configuration_breakdown(name, across_coordinate=False, **kwargs):
    load(name)
    if across_coordinate:
        return bst.plots.plot_unit_groups_across_coordinate(
            set_cane_oil_content,
            [5, 7.5, 10, 12.5],
            'Feedstock oil content [dry wt. %]',
            unit_groups,
            colors=[area_colors[i.name].RGBn for i in unit_groups],
            hatches=[area_hatches[i.name] for i in unit_groups],
            **kwargs,
        )
    else:
        def format_total(x):
            if x < 1e3:
                return format(x, '.3g')
            else:
                x = int(x)
                n = 10 ** (len(str(x)) - 3)
                value = int(round(x / n) * n)
                return format(value, ',')
        for i in unit_groups: 
            i.metrics[0].name = 'Inst. eq.\ncost'
            i.metrics[3].name = 'Elec.\ncons.'
            i.metrics[4].name = 'Mat.\ncost'
        
        return bst.plots.plot_unit_groups(
            unit_groups,
            colors=[area_colors[i.name].RGBn for i in unit_groups],
            hatches=[area_hatches[i.name] for i in unit_groups],
            format_total=format_total,
            fraction=True,
            **kwargs,
        )

def plot_TCI_areas_across_oil_content(configuration='O2'):
    load(configuration)
    data = {i.name: [] for i in unit_groups}
    increasing_areas = []
    decreasing_areas = []
    oil_contents = np.linspace(5, 15, 10)
    for i in oil_contents:
        set_cane_oil_content(i)
        sys.simulate()
        for i in unit_groups: data[i.name].append(i.get_installed_cost())
    for name, group_data in data.items():
        lb, *_, ub = group_data
        if ub > lb: 
            increasing_areas.append(group_data)
        else:
            decreasing_areas.append(group_data)
    increasing_values = np.sum(increasing_areas, axis=0)
    increasing_values -= increasing_values[0]
    decreasing_values = np.sum(decreasing_areas, axis=0)
    decreasing_values -= decreasing_values[-1]
    plt.plot(oil_contents, increasing_values, label='Oil & fiber areas')
    plt.plot(oil_contents, decreasing_values, label='Sugar areas')
    
def save_detailed_expenditure_tables(name):
    number, agile = parse(name)
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = f'expenditures_{number}'
    if agile: filename += '_agile'
    filename += '.xlsx'
    file = os.path.join(folder, filename)
    writer = pd.ExcelWriter(file)
    load(name)
    cs.voc_table(sys, tea, [ethanol, biodiesel]).to_excel(writer, 'VOC', startrow=1)
    cs.foc_table(tea).to_excel(writer, 'FOC', startrow=1)
    cs.capex_table(tea).to_excel(writer, 'CAPEX', startrow=1)
    writer.save()

# DO NOT DELETE: For removing ylabel and yticklabels and combine plots
# import biorefineries.oilcane as oc
# import matplotlib.pyplot as plt
# oc.plot_configuration_breakdown('O2')
# ax, *_ = plt.gcf().get_axes()
# yticks = ax.get_yticks()
# plt.yticks(yticks, ['']*len(yticks))
# plt.ylabel('')
# plt.show()

# DO NOT DELETE: For better tickmarks
# import biorefineries.oilcane as oc
# import numpy as np
# oc.plot_monte_carlo(derivative=True, comparison=False,
#     tickmarks=np.array([
#         [-3.0, -1.5, 0, 1.5, 3.0, 4.5],
#         [-6, -3, 0, 3, 6, 9],
#         [-2.25, -1.5, -0.75, 0, 0.75, 1.5],
#         [-10, 0, 10, 20, 30, 40],
#         [-300, -225, -150, -75, 0, 75]
#     ]),
#     labels=['Conventional', 'Cellulosic']
# )

# DO NOT DELETE: For SI Monte Carlo
# import biorefineries.oilcane as oc
# import numpy as np
# oc.plot_monte_carlo(
#     absolute=True, comparison=False,
#     labels=['Sugarcane\nconventional', 'Oilcane\nconventional',
#             'Sugarcane\ncellulosic', 'Oilcane\ncellulosic',
#             'Sugarcane\nconventional\nagile', 'Oilcane\nconventional\nagile',
#             'Sugarcane\ncellulosic\nagile', 'Oilcane\ncellulosic\nagile'],
# )
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 12 16:52:07 2023

Modified from the biorefineries constructed in [1], [2], and [3] for the production of
[1] 3-hydroxypropionic acid, [2] lactic acid, and [3] ethanol from lignocellulosic feedstocks

[1]	Bhagwat et al., Sustainable Production of Acrylic Acid via 3-Hydroxypropionic Acid from Lignocellulosic Biomass. ACS Sustainable Chem. Eng. 2021, 9 (49), 16659–16669. https://doi.org/10.1021/acssuschemeng.1c05441
[2]	Li et al., Sustainable Lactic Acid Production from Lignocellulosic Biomass. ACS Sustainable Chem. Eng. 2021, 9 (3), 1341–1351. https://doi.org/10.1021/acssuschemeng.0c08055
[3]	Cortes-Peña et al., BioSTEAM: A Fast and Flexible Platform for the Design, Simulation, and Techno-Economic Analysis of Biorefineries under Uncertainty. ACS Sustainable Chem. Eng. 2020, 8 (8), 3302–3310. https://doi.org/10.1021/acssuschemeng.9b07040


@author: sarangbhagwat
"""


# %% 

# =============================================================================
# Setup
# =============================================================================

# import numpy as np
import biosteam as bst
from chaospy import distributions as shape
# from biosteam import main_flowsheet as find
from biosteam.evaluation import Model, Metric
# from biosteam.evaluation.evaluation_tools import Setter
from biorefineries.TAL.systems.system_TAL_solubility_exploit_ethanol_sugarcane import TAL_sys, TAL_tea, TAL_lca, u, s, unit_groups, unit_groups_dict, spec, price, TEA_breakdown, simulate_and_print, theoretical_max_g_TAL_per_g_glucose, TAL_chemicals
from biorefineries.TAL.models.model_utils import EasyInputModel
# get_annual_factor = lambda: TAL_tea._annual_factor

per_kg_KSA_to_per_kg_SA = TAL_chemicals.PotassiumSorbate.MW/TAL_chemicals.SorbicAcid.MW

get_annual_factor = lambda: TAL_tea.operating_hours # hours per year

_kg_per_ton = 907.18474


system_feeds = [i for i in TAL_sys.feeds if i.price]
system_products = [i for i in TAL_sys.products if i.price]
    
# gypsum = find.stream.gypsum
# system_products.append(gypsum)

baseline_yield, baseline_titer, baseline_productivity =\
    spec.baseline_yield, spec.baseline_titer, spec.baseline_productivity

u.U402.decarboxylation_conversion_basis = 'fixed'

# %% 

# =============================================================================
# Overall biorefinery metrics
# =============================================================================

feedstock = s.sugarcane
product_stream = s.TAL_product
# CSL = s.CSL_fresh


R302 = u.R302
R303 = u.R303

BT = u.BT701
# F404 = u.F404

_feedstock_factor = feedstock.F_mass / (feedstock.F_mass-feedstock.imass['Water'])
# Minimum selling price of TAL stream
def get_MSP():
    for i in range(3):
        product_stream.price = TAL_tea.solve_price(product_stream)
    # return product_stream.price*product_stream.F_mass/sum(product_stream.imass['Octyl_5_hydroxyhexanoate','Octyl_3_5_dihydroxyhexanoate', 'DHL'])
    return product_stream.price 

# Mass flow rate of TAL stream
get_yield = lambda: product_stream.F_mass*get_annual_factor()/1e6
# Purity (%) of TAL in the final product
get_purity = lambda: product_stream.imass['TAL']/product_stream.F_mass
# Adjust for purity
get_adjusted_MSP = lambda: get_MSP() / get_purity()
get_adjusted_yield = lambda: get_yield() * get_purity()
# Recovery (%) = recovered/amount in fermentation broth
get_recovery = lambda: product_stream.imol['TAL']\
    /(R302.outs[1].imol['TAL'])
get_overall_TCI = lambda: TAL_tea.TCI/1e6

get_overall_installed_cost = lambda: TAL_tea.installed_equipment_cost/1e6

# Annual operating cost, note that AOC includes electricity credit
get_overall_AOC = lambda: TAL_tea.AOC/1e6
get_material_cost = lambda: (TAL_tea.material_cost +
                             abs(BT.ash_disposal_price*
                                 BT.ash_disposal.F_mass*
                                 TAL_tea.operating_hours))/1e6
get_overall_FOC = lambda: TAL_tea.FOC/1e6
# Annual sale revenue from products, note that electricity credit is not included,
# but negative sales from waste disposal are included
# (i.e., wastes are products of negative selling price)
get_annual_sale = lambda: TAL_tea.sales/1e6
# System power usage, individual unit power usage should be positive
excess_power = lambda: (TAL_sys.power_utility.production-TAL_sys.power_utility.consumption)
get_electricity_price = lambda: bst.PowerUtility.price
# Electricity credit is positive if getting revenue from excess electricity
get_electricity_credit = lambda: (excess_power()*get_electricity_price()*get_annual_factor())/1e6

metrics = [Metric('Minimum selling price', get_MSP, '$/kg SA-eq.', 'Biorefinery'),
           Metric('Production rate', get_yield, '10^6 kg/yr', 'Biorefinery'),
           Metric('Product purity', get_purity, '%', 'Biorefinery'),
           Metric('Adjusted minimum selling price', get_adjusted_MSP, '$/kg SA-eq.', 'Biorefinery'),
           Metric('Adjusted product yield', get_adjusted_yield, '10^6 kg/yr', 'Biorefinery'),
           Metric('Product recovery', get_recovery, '%', 'Biorefinery'),
           Metric('Total capital investment', get_overall_TCI, '10^6 $', 'Biorefinery'),
           Metric('Total installed equipment cost', get_overall_installed_cost, '10^6 $', 'Biorefinery'),
           Metric('Annual material cost (incl. boiler ash disposal)', get_material_cost, '10^6 $/yr', 'Biorefinery'),
           Metric('Annual electricity credit', get_electricity_credit, '10^6 $/yr', 'Biorefinery'),
           Metric('Annual operating cost (incl. electricity credit)', get_overall_AOC, '10^6 $/yr', 'Biorefinery'),
           Metric('Annual product sale (excl. electricity)', get_annual_sale, '10^6 $/yr', 'Biorefinery'),
           Metric('Fixed operating cost', get_overall_FOC, '10^6 $/yr', 'Biorefinery'),
           ]

# To see if TEA converges well for each simulation
get_NPV = lambda: TAL_tea.NPV
metrics.extend((Metric('Net present value', get_NPV, '$', 'TEA'), ))


# metrics_labels_dict = {
#     'Installed cost':(0, '10^6 $'), 
#     'Material cost':(4,'USD/h'), 
#     'Cooling duty':(1,'GJ/h'), 
#     'Heating duty':(2,'GJ/h'), 
#     'Electricity usage':(3, 'MW'), 
#     }

# for m, u_i in metrics_labels_dict.items():
#     for ug in unit_groups:
#         metrics.append(Metric(ug.name, ug.metrics[u_i[0]], u_i[1], m))

#%% Unit group metrics - absolute
ug_metrics = unit_groups[0].metrics
for mi in range(len(ug_metrics)):
    m = ug_metrics[mi]
    for ug in unit_groups:
        metrics.append(Metric(ug.name, ug.metrics[mi], m.units, m.name))

#%% Metric totals
def metric_total_func_generator(metric_index):
    mname =  unit_groups[0].metrics[metric_index].name
    
    if not mname == 'Operating cost':
        return lambda: sum([ugr.metrics[metric_index]() 
                            for ugr in unit_groups])
    else:
        return lambda: sum([ugr.metrics[metric_index]() 
                            for ugr in unit_groups])\
                        * TAL_tea.operating_hours / 1e6
                        
def metric_total_without_offset_func_generator(metric_index):
    mname =  unit_groups[0].metrics[metric_index].name
    if mname == 'Operating cost':
        return lambda: (sum([ugr.metrics[metric_index]() 
                        for ugr in unit_groups]) + excess_power()*get_electricity_price())\
                        * TAL_tea.operating_hours / 1e6
    elif mname in ('Heating duty', 'Cooling duty'):
        return lambda: sum([ugr.metrics[metric_index]() 
                        for ugr in unit_groups]) - unit_groups_dict['heat exchanger network'].metrics[metric_index]()

for mi in range(len(ug_metrics)):
    m = ug_metrics[mi]
    metrics.append(Metric('Total', 
                          metric_total_func_generator(mi),
                          m.units,
                          m.name))
    if m.name in ('Operating cost', 'Heating duty', 'Cooling duty'):
        metrics.append(Metric('Total before offset',
                              metric_total_without_offset_func_generator(mi), 
                              m.units, 
                              m.name))
metrics.append(Metric('Total', 
                      lambda: TAL_sys.power_utility.rate/1e3,
                      'MW',
                      'Net electricity'))

metrics.append(Metric('Total', 
                      lambda: unit_groups_dict['natural gas (for product drying)'].metrics[1]() * TAL_tea.operating_hours/1e6,
                      'MM$/y',
                      'Natural gas (product drying) material cost'))

#%% Unit group metrics - contributions
def metric_fraction_func_generator(u_group, metric_index):
  mname =  u_group.metrics[metric_index].name
  if not mname in ('Operating cost', 'Heating duty', 'Cooling duty'):
      return lambda: u_group.metrics[metric_index]() / sum([ugr.metrics[metric_index]() 
                                                            for ugr in unit_groups])
  elif mname == 'Operating cost':
      return lambda: u_group.metrics[metric_index]() / (sum([ugr.metrics[metric_index]() 
                                                            for ugr in unit_groups]) + excess_power()*get_electricity_price())
  elif mname in ('Heating duty', 'Cooling duty'):
      return lambda: u_group.metrics[metric_index]() / (sum([ugr.metrics[metric_index]() 
                                                            for ugr in unit_groups]) - unit_groups_dict['heat exchanger network'].metrics[metric_index]())

for mi in range(len(ug_metrics)):
    m = ug_metrics[mi]
    for ug in unit_groups:
        metrics.append(Metric(ug.name, 
                              metric_fraction_func_generator(ug, mi),
                              m.units, 
                              'Contributions [%] - ' + m.name,
                              ))

#%% Material cost contributions to total operating cost
def mat_cost_frac_of_op_cost_func_generator(si):
  return lambda: si.cost*TAL_tea.operating_hours/(TAL_tea.AOC +
                                                  excess_power()*get_electricity_price()*TAL_tea.operating_hours)

for i in TAL_sys.feeds:
    if i.price:
        metrics.append(Metric(i.ID, 
                              mat_cost_frac_of_op_cost_func_generator(i),
                              'MM$/y', 
                              'Contributions to total operating cost [%]',
                              ))

#%% Material cost contributions to total material cost
def mat_cost_frac_of_mat_cost_func_generator(si):
  return lambda: si.cost*TAL_tea.operating_hours/TAL_tea.material_cost

for i in TAL_sys.feeds:
    if i.price:
        metrics.append(Metric(i.ID, 
                              mat_cost_frac_of_mat_cost_func_generator(i),
                              'MM$/y', 
                              'Contributions to total material cost [%]',
                              ))

#%% LCA - absolute impacts
get_GWP_before_offset = lambda: TAL_lca.GWP - TAL_lca.net_electricity_GWP
get_other_materials_GWP = lambda: TAL_lca.material_GWP - TAL_lca.material_GWP_breakdown['AceticAcid'] - TAL_lca.material_GWP_breakdown['CSL'] - TAL_lca.material_GWP_breakdown['DAP'] - TAL_lca.material_GWP_breakdown['CH4'] # all materials other than feedstock, CSL, acetate, and CH4

# IPCC 2013 GWP100a
metrics.append(Metric('Total GWP100a', lambda: TAL_lca.GWP, 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('Total GWP100a excl. net electricity', get_GWP_before_offset, 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric('GWP100a - Heating demand', lambda: TAL_lca.heating_demand_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric('GWP100a - Cooling demand', lambda: TAL_lca.cooling_demand_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('GWP100a - Net electricity', lambda: TAL_lca.net_electricity_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('GWP100a - Direct non-biogenic emissions', lambda: TAL_lca.direct_emissions_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric('GWP100a - Feedstock (FGHTP) ', lambda: TAL_lca.FGHTP_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('GWP100a - Materials (except feedstock and BT.natural_gas) ', lambda: TAL_lca.material_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric(f'GWP100a - Materials breakdown - CSL', lambda: TAL_lca.material_GWP_breakdown['CSL'], 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a - Materials breakdown - DAP', lambda: TAL_lca.material_GWP_breakdown['DAP'], 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a - Materials breakdown - Acetate', lambda: TAL_lca.material_GWP_breakdown['AceticAcid'], 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a - Materials breakdown - CH4', lambda: TAL_lca.material_GWP_breakdown['CH4'], 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a - Materials breakdown - CO2', lambda: TAL_lca.material_GWP_breakdown['CO2'], 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric('GWP100a - Other materials', get_other_materials_GWP, 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric(f'GWP100a - Other materials breakdown - H2SO4', lambda: TAL_lca.material_GWP_breakdown['H2SO4'], 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a - Materials breakdown - CalciumDihydroxide', lambda: TAL_lca.material_GWP_breakdown['CalciumDihydroxide'], 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a - Materials breakdown - MEA', lambda: TAL_lca.material_GWP_breakdown['MEA'], 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a - Other materials breakdown - H3PO4', lambda: TAL_lca.material_GWP_breakdown['H3PO4'], 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a - Other materials breakdown - NaOH', lambda: TAL_lca.material_GWP_breakdown['NaOH'], 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a - Other materials breakdown - CaO', lambda: TAL_lca.material_GWP_breakdown['CaO'], 'kg-CO2-eq/kg', 'Biorefinery'))

# FEC
get_FEC_before_offset = lambda: TAL_lca.FEC - TAL_lca.net_electricity_FEC
get_other_materials_FEC = lambda: TAL_lca.material_FEC - TAL_lca.material_FEC_breakdown['AceticAcid'] - TAL_lca.material_FEC_breakdown['CH4'] - TAL_lca.material_FEC_breakdown['CSL'] - TAL_lca.material_FEC_breakdown['DAP']

metrics.append(Metric('Total FEC', lambda: TAL_lca.FEC, 'MJ/kg', 'Biorefinery'))
metrics.append(Metric('Total FEC excl. net electricity', get_FEC_before_offset, 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric('FEC - Heating demand', lambda: TAL_lca.heating_demand_FEC, 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric('FEC - Cooling demand', lambda: TAL_lca.cooling_demand_FEC, 'MJ/kg', 'Biorefinery'))
metrics.append(Metric('FEC - Net electricity', lambda: TAL_lca.net_electricity_FEC, 'MJ/kg', 'Biorefinery'))

metrics.append(Metric('FEC - Feedstock (FGHTP) ', lambda: TAL_lca.feedstock_FEC, 'MJ/kg', 'Biorefinery'))
metrics.append(Metric('FEC - Materials (except feedstock and BT.natural_gas) ', lambda: TAL_lca.material_FEC, 'MJ/kg', 'Biorefinery'))

metrics.append(Metric(f'FEC - Materials breakdown - CSL', lambda: TAL_lca.material_FEC_breakdown['CSL'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Materials breakdown - DAP', lambda: TAL_lca.material_FEC_breakdown['DAP'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Materials breakdown - Acetate', lambda: TAL_lca.material_FEC_breakdown['AceticAcid'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Materials breakdown - CH4', lambda: TAL_lca.material_FEC_breakdown['CH4'], 'MJ/kg', 'Biorefinery'))

metrics.append(Metric('FEC - Other materials', get_other_materials_FEC, 'MJ/kg', 'Biorefinery'))

# metrics.append(Metric(f'FEC - Materials breakdown - CO2', lambda: TAL_lca.material_FEC_breakdown['CO2'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Other materials breakdown - H2SO4', lambda: TAL_lca.material_FEC_breakdown['H2SO4'], 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC - Materials breakdown - CalciumDihydroxide', lambda: TAL_lca.material_FEC_breakdown['CalciumDihydroxide'], 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC - Materials breakdown - MEA', lambda: TAL_lca.material_FEC_breakdown['MEA'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Other materials breakdown - H3PO4', lambda: TAL_lca.material_FEC_breakdown['H3PO4'], 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC - Other materials breakdown - NaOH', lambda: TAL_lca.material_FEC_breakdown['NaOH'], 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC - Other materials breakdown - CaO', lambda: TAL_lca.material_FEC_breakdown['CaO'], 'MJ/kg', 'Biorefinery'))

#%% LCA - % contributions relative to total positive impacts

# IPCC 2013 GWP100a

metrics.append(Metric('GWP100a % - Net electricity', lambda: TAL_lca.net_electricity_GWP/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('GWP100a %- Direct non-biogenic emissions', lambda: TAL_lca.direct_emissions_GWP/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric('GWP100a % - Feedstock (FGHTP) ', lambda: TAL_lca.FGHTP_GWP/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric('GWP100a % - Materials (except feedstock and BT.natural_gas) ', lambda: TAL_lca.material_GWP/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric(f'GWP100a % - Materials breakdown - CSL', lambda: TAL_lca.material_GWP_breakdown['CSL']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a % - Materials breakdown - DAP', lambda: TAL_lca.material_GWP_breakdown['DAP']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a % - Materials breakdown - Acetate', lambda: TAL_lca.material_GWP_breakdown['AceticAcid']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a % - Materials breakdown - CH4', lambda: TAL_lca.material_GWP_breakdown['CH4']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a % - Materials breakdown - CO2', lambda: TAL_lca.material_GWP_breakdown['CO2']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric('GWP100a % - Other materials', lambda: get_other_materials_GWP()/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))

metrics.append(Metric(f'GWP100a % - Other materials breakdown - H2SO4', lambda: TAL_lca.material_GWP_breakdown['H2SO4']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a % - Materials breakdown - CalciumDihydroxide', lambda: TAL_lca.material_GWP_breakdown['CalciumDihydroxide']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a % - Materials breakdown - MEA', lambda: TAL_lca.material_GWP_breakdown['MEA']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a % - Other materials breakdown - H3PO4', lambda: TAL_lca.material_GWP_breakdown['H3PO4']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
# metrics.append(Metric(f'GWP100a % - Other materials breakdown - NaOH', lambda: TAL_lca.material_GWP_breakdown['NaOH']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))
metrics.append(Metric(f'GWP100a % - Other materials breakdown - CaO', lambda: TAL_lca.material_GWP_breakdown['CaO']/get_GWP_before_offset(), 'kg-CO2-eq/kg', 'Biorefinery'))

# FEC

metrics.append(Metric('FEC % - Net electricity', lambda: TAL_lca.net_electricity_FEC/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))

metrics.append(Metric('FEC % - Feedstock (FGHTP) ', lambda: TAL_lca.feedstock_FEC/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric('FEC % - Materials (except feedstock and BT.natural_gas) ', lambda: TAL_lca.material_FEC/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))

metrics.append(Metric(f'FEC % - Materials breakdown - CSL', lambda: TAL_lca.material_FEC_breakdown['CSL']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Materials breakdown - DAP', lambda: TAL_lca.material_FEC_breakdown['DAP']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Materials breakdown - Acetate', lambda: TAL_lca.material_FEC_breakdown['AceticAcid']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Materials breakdown - CH4', lambda: TAL_lca.material_FEC_breakdown['CH4']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))

metrics.append(Metric('FEC % - Other materials', lambda: get_other_materials_FEC()/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))

# metrics.append(Metric(f'FEC % - Materials breakdown - CO2', lambda: TAL_lca.material_FEC_breakdown['CO2']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Other materials breakdown - H2SO4', lambda: TAL_lca.material_FEC_breakdown['H2SO4']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC % - Materials breakdown - CalciumDihydroxide', lambda: TAL_lca.material_FEC_breakdown['CalciumDihydroxide']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC % - Materials breakdown - MEA', lambda: TAL_lca.material_FEC_breakdown['MEA']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Other materials breakdown - H3PO4', lambda: TAL_lca.material_FEC_breakdown['H3PO4']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
# metrics.append(Metric(f'FEC % - Other materials breakdown - NaOH', lambda: TAL_lca.material_FEC_breakdown['NaOH']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))
metrics.append(Metric(f'FEC % - Other materials breakdown - CaO', lambda: TAL_lca.material_FEC_breakdown['CaO']/get_FEC_before_offset(), 'MJ/kg', 'Biorefinery'))

#%% Generate the required namespace
namespace_dict = {}
exclude_from_globals = [
    'search',
    'register',
    'register_safely',
    'discard',
    'clear',
    'mark_safe_to_replace',
    'unmark_safe_to_replace']

namespace_dict.update({k:s.__getitem__(k) for k in s.__dir__() if not k in exclude_from_globals})
namespace_dict.update({k:u.__getitem__(k) for k in u.__dir__() if not k in exclude_from_globals})
namespace_dict['feedstock'] = feedstock
namespace_dict['product_stream'] = product_stream
namespace_dict['TAL_tea'] = namespace_dict['tea'] = TAL_tea
namespace_dict['spec'] = spec
PowerUtility = bst.PowerUtility
namespace_dict['PowerUtility'] = PowerUtility
# namespace_dict['PD'] = s.PD
namespace_dict['theoretical_max_g_TAL_per_g_glucose'] = theoretical_max_g_TAL_per_g_glucose

#%% 


model = TAL_model = EasyInputModel(TAL_sys, metrics, namespace_dict=namespace_dict)



    
#%% Bugfix barrage
baseline_spec = {'spec_1': spec.baseline_yield,
                 'spec_2': spec.baseline_titer,
                 'spec_3': spec.baseline_productivity,}

system=model._system
def reset_and_reload():
    print('Resetting cache and emptying recycles ...')
    system.reset_cache()
    system.empty_recycles()
    print('Loading and simulating with baseline specifications ...')
    spec_1, spec_2, spec_3 = spec.spec_1, spec.spec_2, spec.spec_3
    spec.load_specifications(**baseline_spec)
    spec.set_production_capacity(spec.desired_annual_production)
    # system.simulate()
    print('Loading and simulating with required specifications ...')
    spec.load_specifications(spec_1=spec_1, spec_2=spec_2, spec_3=spec_3)
    spec.set_production_capacity(spec.desired_annual_production)
    # system.simulate()
    
def reset_and_switch_solver(solver_ID):
    system.reset_cache()
    system.empty_recycles()
    system.converge_method = solver_ID
    print(f"Trying {solver_ID} ...")
    # spec.load_specifications(spec_1=spec.spec_1, spec_2=spec.spec_2, spec_3=spec.spec_3)
    spec.set_production_capacity(spec.desired_annual_production)
    # system.simulate()
    
def run_bugfix_barrage():
    try:
        reset_and_reload()
    except Exception as e:
        print(str(e))
        try:
            reset_and_switch_solver('fixedpoint')
        except Exception as e:
            print(str(e))
            try:
                reset_and_switch_solver('aitken')
            except Exception as e:
                print(str(e))
                # print(_yellow_text+"Bugfix barrage failed.\n"+_reset_text)
                print("Bugfix barrage failed.\n")
                # breakpoint()
                raise e
###############################

#%% Model specification
pre_fermenter_units_path = list(spec.reactor.get_upstream_units())
pre_fermenter_units_path.reverse()
def model_specification():
    try:
        for i in pre_fermenter_units_path: i.simulate()
        # spec.load_specifications(spec_1=spec.spec_1, spec_2=spec.spec_2, spec_3=spec.spec_3)
        spec.set_production_capacity(spec.desired_annual_production)
        # system.simulate()
        # model._system.simulate()
    

    except Exception as e:
        str_e = str(e).lower()
        print('Error in model spec: %s'%str_e)
        # raise e
        if 'sugar concentration' in str_e:
            # flowsheet('AcrylicAcid').F_mass /= 1000.
            raise e
        else:
            run_bugfix_barrage()
            
model.specification = model_specification



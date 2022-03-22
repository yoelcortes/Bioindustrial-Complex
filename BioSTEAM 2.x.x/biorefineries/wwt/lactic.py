#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Bioindustrial-Park: BioSTEAM's Premier Biorefinery Models and Results
# Copyright (C) 2021-, Yalin Li <zoe.yalin.li@gmail.com>
#
# Part of this module is based on the lactic acid biorefinery:
# https://github.com/BioSTEAMDevelopmentGroup/Bioindustrial-Park/tree/master/BioSTEAM%202.x.x/biorefineries/lactic
#
# This module is under the UIUC open-source license. See
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.

info = {
    'abbr': 'la',
    'WWT_ID': '5',
    'is2G': True,
    'add_CHP': False,
    'ww_price': None,
    }


# %%

# =============================================================================
# Systems
# =============================================================================

def create_la_comparison_systems():
    # Create from scratch, IRR for existing system is 24.38% (24.39% if do direct loading)
    from biorefineries.wwt import create_comparison_systems, add_wwt_chemicals
    from biorefineries.lactic import (
        create_chemicals,
        create_system,
        create_tea,
        load_process_settings,
        get_splits,
        )
    # Add WWT chemicals to the existing splits array,
    # splits of chemicals that do now exist in the original chemicals obj
    # will be copied from the splits of the corresponding group
    la_chems = add_wwt_chemicals(create_chemicals())
    def create_new_splits(original_splits):
        new_splits = la_chems.zeros()
        new_splits[la_chems.indices(('Bisulfite', 'CitricAcid', 'HCl', 'NaOCl'))] = \
            original_splits[la_chems.index('NaOH')]
        return new_splits
    cell_mass_split, gypsum_split, AD_split, MB_split = get_splits(la_chems)
    new_cell_mass_split = create_new_splits(cell_mass_split)
    new_gypsum_split = create_new_splits(gypsum_split)

    functions = (create_chemicals, create_system, create_tea, load_process_settings,)
    sys_dct = {
        'create_system': {'cell_mass_split': new_cell_mass_split, 'gypsum_split': new_gypsum_split},
        'BT': 'CHP',
        'new_wwt_connections': {'sludge': ('M601', 0), 'biogas': ('CHP', 1)},
        }
    exist_sys, new_sys = create_comparison_systems(info, functions, sys_dct)

    # #!!! COD from above is ~504, but here 416, need to figure out why
    # # IRR for existing system is 24.63% (24.39% if do direct loading)
    # from biorefineries.wwt import create_comparison_systems
    # from biorefineries import lactic as la
    # sys_dct = {
    #     'load': {'print_results': False},
    #     'system_name': 'lactic_sys',
    #     'BT': 'CHP',
    #     'new_wwt_connections': {'sludge': ('M601', 0), 'biogas': ('CHP', 1)},
    #     }
    # exist_sys, new_sys = create_comparison_systems(info, la, sys_dct, from_load=True)

    return exist_sys, new_sys


def simulate_la_systems():
    from biorefineries.wwt import simulate_systems
    global exist_sys, new_sys
    exist_sys, new_sys = create_la_comparison_systems()
    # ~504 mg/L COD, soluble lignin, arabinose, and galactose all >10%,
    # lactic acid, extract, xylose, and mannose ~5-10%
    simulate_systems(exist_sys, new_sys, info)
    return exist_sys, new_sys


# %%

# =============================================================================
# Models
# =============================================================================

def create_la_comparison_models():
    from biorefineries.wwt import create_comparison_models
    exist_sys, new_sys = create_la_comparison_systems()

    ##### Existing system #####
    exist_model_dct = {
        'abbr': info['abbr'],
        'feedstock': 'feedstock',
        'FERM_product': 'lactic_acid',
        'sludge': 'wastes_to_CHP',
        'biogas': 'biogas',
        'PT_acid_mixer': 'T201',
        'adjust_acid_with_acid_loading': True,
        'PT_solids_mixer': 'M202',
        'PT_rx': 'R201',
        'EH_mixer': 'M301',
        'fermentor': 'R301',
        'reactions': {
            'PT glucan-to-glucose': ('pretreatment_rxns', 0),
            'PT xylan-to-xylose': ('pretreatment_rxns', 4),
            'EH glucan-to-glucose': ('saccharification_rxns', 2),
            'FERM glucan-to-product': ('cofermentation_rxns', 0),
            'FERM xylan-to-product': ('cofermentation_rxns', 3),
            },
        'BT': 'CHP',
        'BT_eff': ('B_eff', 'TG_eff'),
        'wwt_system': 'exist_sys_wwt',
        'is2G': info['is2G'],
        }
    exist_model = create_comparison_models(exist_sys, exist_model_dct)

    ##### With the new wastewater treatment process #####
    new_model_dct = exist_model_dct.copy()
    new_model_dct['wwt_system'] = 'new_sys_wwt'
    new_model_dct['new_wwt_ID'] = info['WWT_ID']
    new_model = create_comparison_models(new_sys, new_model_dct)
    return exist_model, new_model


def evaluate_la_models(**kwargs):
    from biorefineries.wwt import evaluate_models
    global exist_model, new_model
    exist_model, new_model = create_la_comparison_models()
    return evaluate_models(exist_model, new_model, abbr=info['abbr'], **kwargs)


# %%

# =============================================================================
# Run
# =============================================================================

#!!! The lactic acid module is REALLY slow... would want to profile and find out why
#!!! There are problems with the metrics
if __name__ == '__main__':
    # exist_sys, new_sys = simulate_la_systems()
    exist_model, new_model = create_la_comparison_models()
    # exist_model, new_model = evaluate_la_models(N=10, notify=1)
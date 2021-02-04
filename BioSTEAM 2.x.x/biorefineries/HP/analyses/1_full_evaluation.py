#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BioSTEAM: The Biorefinery Simulation and Techno-Economic Analysis Modules
# Copyright (C) 2020, Yoel Cortes-Pena <yoelcortes@gmail.com>
# Bioindustrial-Park: BioSTEAM's Premier Biorefinery Models and Results
# Copyright (C) 2020, Yalin Li <yalinli2@illinois.edu>,
# Sarang Bhagwat <sarangb2@illinois.edu>, and Yoel Cortes-Pena (this biorefinery)
# 
# This module is under the UIUC open-source license. See 
# github.com/BioSTEAMDevelopmentGroup/biosteam/blob/master/LICENSE.txt
# for license details.

"""
Created on Mon Apr 13 10:24:42 2020

Modified from the biorefineries constructed in [1] and [2] for the production of
HP acid from lignocellulosic feedstocks

[1] Cortes-Peña et al., BioSTEAM: A Fast and Flexible Platform for the Design, 
    Simulation, and Techno-Economic Analysis of Biorefineries under Uncertainty. 
    ACS Sustainable Chem. Eng. 2020, 8 (8), 3302–3310.
    https://doi.org/10.1021/acssuschemeng.9b07040
    
[2] Li et al., Tailored Pretreatment Processes for the Sustainable Design of
    Lignocellulosic Biorefineries across the Feedstock Landscape. Submitted,
    2020.

@author: yalinli_cabbi
"""


# %% 

# =============================================================================
# Setup
# =============================================================================
from warnings import filterwarnings
filterwarnings('ignore')
import numpy as np
import pandas as pd
import biosteam as bst
from biosteam.utils import TicToc
from biosteam.plots import plot_montecarlo_across_coordinate
from biorefineries.HP.system_light_lle_vacuum_distillation import spec, HP_sys, get_AA_MPSP, get_GWP, get_FEC, R301
from biorefineries.HP.analyses import models
from datetime import datetime



percentiles = [0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1]


# %%

# =============================================================================
# Evaluate and organize results for Monte Carlo analysis
# =============================================================================

# Initiate a timer
timer = TicToc('timer')
timer.tic()

# model = models.model_full
model = models.HP_model
R301.set_titer_limit = True

# Set seed to make sure each time the same set of random numbers will be used
np.random.seed(3221)
N_simulation = 5 # 1000
samples = model.sample(N=N_simulation, rule='L')
model.load_samples(samples)

baseline_initial = model.metrics_at_baseline()
baseline = pd.DataFrame(data=np.array([[i for i in baseline_initial.values],]), 
                        columns=baseline_initial.keys())

model.evaluate()

# Baseline results
baseline_end = model.metrics_at_baseline()
dateTimeObj = datetime.now()
file_to_save = 'HP_%s.%s.%s-%s.%s'%(dateTimeObj.year, dateTimeObj.month, dateTimeObj.day, dateTimeObj.hour, dateTimeObj.minute)

baseline = baseline.append(baseline_end, ignore_index=True)
baseline.index = ('initial', 'end')
baseline.to_excel(file_to_save+'_0_baseline.xlsx')

# Parameters
parameters = model.get_parameters()
index_parameters = len(model.get_baseline_sample())
parameter_values = model.table.iloc[:, :index_parameters].copy()

#%%
# TEA results
index_TEA = index_parameters + models.index_TEA
TEA_results = \
    model.table.iloc[:, index_parameters:index_TEA].copy()
TEA_percentiles = TEA_results.quantile(q=percentiles)

# MPSP across IRRs
index_IRR = index_parameters + models.index_IRR
IRR_results = \
    model.table.iloc[:, index_TEA:index_IRR].copy()
IRR_percentiles = IRR_results.quantile(q=percentiles)

# LCA_results
LCA_results = \
    model.table.iloc[:, index_IRR::].copy()
LCA_percentiles = LCA_results.quantile(q=percentiles)

# Spearman's rank correlation
spearman_metrics = model.metrics[0:2] + model.metrics[6:8] + \
    model.metrics[models.index_IRR:models.index_IRR+2]
    
model.table = model.table.dropna()
spearman_parameters = parameters
spearman_results = model.spearman(spearman_parameters, spearman_metrics)
spearman_results.columns = pd.Index([i.name_with_units for i in spearman_metrics])

# Calculate the cumulative probabilitie of each parameter
probabilities = {}
for i in range(index_parameters):
    p = parameters[i]
    p_values = parameter_values.iloc[:, 2*i]
    probabilities[p.name] = p.distribution.cdf(p_values)
    parameter_values.insert(loc=2*i+1, 
                      column=(parameter_values.iloc[:, 2*i].name[0], 'Probability'), 
                      value=probabilities[p.name],
                      allow_duplicates=True)

run_number = samples.shape[0]


# %%

# =============================================================================
# Evaluate the min/max of one parameter each time to ensure the parameter can
# independently affect the system
# =============================================================================

p_values = [[], [], []]
MPSPs = [[], [], []]
GWPs = [[], [], []]
FECs = [[], [], []]

# import pdb
bst.speed_up()
for p in parameters:
    # pdb.set_trace()
    # [p_min], [p_max] = p.distribution.range().tolist()
    p_dist = p.distribution
    [p_min], [p_max] = p_dist.lower.tolist(), p_dist.upper.tolist()
    p_baseline = p.baseline
    p_value = (p_min, p_max, p_baseline)
    p.system = HP_sys
    for i in range(len(p_value)):
        p.setter(p_value[i])
        p_values[i].append(p_value[i])
        MPSP = get_AA_MPSP()
        MPSPs[i].append(MPSP)
        GWPs[i].append(get_GWP())
        FECs[i].append(get_FEC())
        run_number += 1

MPSP_baseline = np.asarray(MPSPs[2])
MPSP_min_diff = np.asarray(MPSPs[0]) - MPSP_baseline
MPSP_max_diff = np.asarray(MPSPs[1]) - MPSP_baseline

GWP_baseline = np.asarray(GWPs[2])
GWP_min_diff = np.asarray(GWPs[0]) - GWP_baseline
GWP_max_diff = np.asarray(GWPs[1]) - GWP_baseline

FEC_baseline = np.asarray(FECs[2])
FEC_min_diff = np.asarray(FECs[0]) - FEC_baseline
FEC_max_diff = np.asarray(FECs[1]) - FEC_baseline

one_p_df = pd.DataFrame({
    ('Parameter', 'Name'): [i.name_with_units for i in parameters],
    ('Parameter', 'Baseline'): p_values[2],
    ('Parameter', 'Min'): p_values[0],
    ('Parameter', 'Max'): p_values[1],
    ('MPSP [$/kg]', 'MPSP baseline'): MPSP_baseline,
    ('MPSP [$/kg]', 'MPSP min'): MPSPs[0],
    ('MPSP [$/kg]', 'MPSP min diff'): MPSP_min_diff,
    ('MPSP [$/kg]', 'MPSP max'): MPSPs[1],
    ('MPSP [$/kg]', 'MPSP max diff'): MPSP_max_diff,
    ('GWP [kg CO2-eq/kg]', 'GWP baseline'): GWP_baseline,
    ('GWP [kg CO2-eq/kg]', 'GWP min'): GWPs[0],
    ('GWP [kg CO2-eq/kg]', 'GWP min diff'): GWP_min_diff,
    ('GWP [kg CO2-eq/kg]', 'GWP max'): GWPs[1],
    ('GWP [kg CO2-eq/kg]', 'GWP max diff'): GWP_max_diff,
    ('FEC [MJ/kg]', 'FEC baseline'): FEC_baseline,
    ('FEC [MJ/kg]', 'FEC min'): FECs[0],
    ('FEC [MJ/kg]', 'FEC min diff'): FEC_min_diff,
    ('FEC [MJ/kg]', 'FEC max'): FECs[1],
    ('FEC [MJ/kg]', 'FEC max diff'): FEC_max_diff,
    })

time = timer.elapsed_time / 60.
print(f'\nSimulation time for {run_number} runs is: {time:.1f} min')


# %%

# '''Get a quick plot'''
# IRR_plot_indices = [metric.index for metric in model.metrics
#                     if 'IRR' in metric.index[0] and 'MPSP' in metric.index[1]]
# IRR_plot_data = IRR_results[IRR_plot_indices].copy()
# IRR_plot_data.columns = models.IRRs.copy()
# IRR_plot_y = IRR_plot_data.sort_index(axis=1)
# IRR_plot_y = IRR_plot_y.dropna()
# IRR_plot_x = models.IRRs.copy()
# IRR_plot_x.sort()
# plot_montecarlo_across_coordinate(IRR_plot_x, IRR_plot_y)

#%%
'''Output to Excel'''
with pd.ExcelWriter(file_to_save+'_1_full_evaluation.xlsx') as writer:
    parameter_values.to_excel(writer, sheet_name='Parameters')
    TEA_results.to_excel(writer, sheet_name='TEA results')
    TEA_percentiles.to_excel(writer, sheet_name='TEA percentiles')
    IRR_results.to_excel(writer, sheet_name='IRR results')
    IRR_percentiles.to_excel(writer, sheet_name='IRR percentiles')
    LCA_results.to_excel(writer, sheet_name='LCA results')
    LCA_percentiles.to_excel(writer, sheet_name='LCA percentiles')
    spearman_results.to_excel(writer, sheet_name='Spearman')
    one_p_df.to_excel(writer, sheet_name='One-parameter')
    model.table.to_excel(writer, sheet_name='Raw data')


# %%

# =============================================================================
# Temporary codes for debugging
# =============================================================================

# import numpy as np
# from HP.analyses import models

# model = models.model_full
# np.random.seed(3221)

# try: parameter = [parameters[-2]]
# except: parameter = parameters
# model.set_parameters(parameter)

# N_simulation = 20 # 1000
# # samples = model.sample(N=N_simulation, rule='L')
# samples = np.ones(N_simulation)
# samples *= 0.070

# model.load_samples(samples)
# model.evaluate()

# model.table.to_clipboard()








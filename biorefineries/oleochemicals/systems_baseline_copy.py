# -*- coding: utf-8 -*-
"""
Created on Sun Nov 12 18:42:44 2023

@author: lavan
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Aug 23 07:37:23 2022
@author: Lavanya
"""
import biosteam as bst
import thermosteam as tmo
import numpy as np
from biorefineries.oleochemicals import units_baseline
from units_baseline import *
from biorefineries.oleochemicals.chemicals_baseline import chems
from biosteam import Flowsheet as F
from biosteam import main_flowsheet
from biosteam import units, SystemFactory
from biorefineries.biodiesel.systems import create_transesterification_and_biodiesel_separation_system
from biosteam import ProcessWaterCenter
from warnings import filterwarnings; filterwarnings('ignore')

#Settings to set the name of the flowsheet
F = bst.Flowsheet('azelaic_acid_baseline')
bst.main_flowsheet.set_flowsheet(F) 
#Settings to set the chemicals for the flowsheet
bst.settings.set_thermo(chems, cache= True) 

#################################################################################################################################################################################################################################
#The first section is to convert the crude oil to biodiesel
#Area 100
@SystemFactory(
    ID = 'crude_HO_oil_to_biodiesel',

    ins=[dict(ID ='crude_vegetable_oil'),
         dict(ID ='base_for_saponification_of_FFA'),
         dict(ID ='water_for_degumming'),
         dict(ID ='citricacid_for_degumming'),
         dict(ID ='water_for_degumming_2'),
         dict(ID = 'water_for_sodium_oleate_sep')
        ],
    outs=[
#Lipids in this process are being burned in the boilerturbogenerator available in the facilities        
          dict(ID='polar_lipids_to_boilerturbogenerator'),
#Biodiesel produced in this unit is oxidatively cleaved in the following sections          
          dict(ID='biodiesel'),
#Co-product of biodiesel production          
          dict(ID ='crude_glycerol'),
#Wastwater burned in the boilerturbogenerator  
          dict(ID = 'waste_to_boilerturbogenerator'),
          dict(ID ='free_fatty_acid_waste_mixture')
            ],
    fixed_outs_size = True)

def crude_HO_oil_to_biodiesel(ins,outs,X_tes):
    crude_vegetable_oil,base_for_saponification_of_FFA,water_for_degumming,citricacid_for_degumming,water_for_degumming_2,water_for_sodium_oleate_sep = ins
    polar_lipids_to_boilerturbogenerator,biodiesel,crude_glycerol,waste_to_boilerturbogenerator,free_fatty_acid_waste_mixture, = outs
# Stainless steel tanks are preferred for crude oils [1]
    T100 = bst.units.StorageTank('T100',
                               ins = crude_vegetable_oil,
                               outs ='biodiesel_to_pump',
                               vessel_material='Stainless steel',
                               tau = 3*7*24)##crude veg oil is stored for a maximum of 3-4 weeks [2]
    
    P100 = bst.units.Pump('P100',
                      ins = T100-0,
                      outs = 'biodiesel_to_reactor_mixer',
                      material = 'Stainless steel')
   
    H100 = bst.HXutility('H100',
                          ins = P100-0,
                          outs = ('heated_crude_oil'),
                          T = 273.15 + 80)#Based on acid degumming detailed in [3]
 
#Mixing 30% of citric acid and then adding the solution 2% by vol to oil in a mixtank [3]
#Degumming ensures that the refined oil is free from gums that are highly prone to transesterification [4]. 
    T101 = bst.MixTank(ID = 'T101',
                        ins = (H100-0,
                              water_for_degumming,
                              citricacid_for_degumming),
                        outs = ('acid_water_mixture'),
                        vessel_material='Stainless steel',
                        tau = 20/60)
    def adjust_degumming_components(): 
      citricacid_for_degumming.imass['Citric_acid'] = 0.3 * water_for_degumming.F_mass
      (citricacid_for_degumming+ water_for_degumming).F_vol =  0.02 * H100-0
      T101.add_specification(adjust_degumming_components, run=True)   
#Cooling the mixture       
    H101 = bst.HXutility('H101',
                          ins = T101-0,
                          outs = ('cooled_crude_oil'),
                          T = 273.15 + 25)
#Adding 1% water solution to the mix [2]
    M100 = bst.Mixer(ID = 'M100',
                           ins = (H101-0,
                                  water_for_degumming_2))
    
#Holding tank to hold the mixture                           
    T102 = bst.units.StorageTank(ID = 'T102',
                       ins = M100-0,
                       outs = ('water_oil_mixture'), 
                       tau = 1)
                                                                                                   
    def adjust_degumming_components_2():
        water_for_degumming_2.F_vol = 0.01*H101-0
        M100.run()            
        M100.add_specification(adjust_degumming_components_2) 
        
#Centrifuging the degummed oil out, 97% removal of PL using acid degumming[3]
    C100 = bst.LiquidsSplitCentrifuge(ID = 'C100',
                         ins = T102-0,
                         outs = ('degummed_oil', 
                                  polar_lipids_to_boilerturbogenerator),
                         split = dict(PL = 0.4,
                                      TAG = 1,
                                      Water = 0,
                                      Citric_acid = 0,
                                      Oleic_acid = 1))
    
# Neutralization is conducted to control the oil flavor and rancidity of the oil.
# But it is also essential for preventing the saponification of free fatty acids during the transesterification [5]    
#Assuming complete neutralisation in the Mixtank (99%)
    M101 = units_baseline.FFA_neutralisation_tank('M101',
                              ins = (C100-0,
                                     base_for_saponification_of_FFA),
                              outs = 'saponified_mix_for_separation',
                             tau = 0.5)
    def adjust_neutralisation_components(): 
          base_for_saponification_of_FFA.imol['Sodium_hydroxide'] = 1.5*M101.ins[0].imol['Oleic_acid']
    M101.add_specification(adjust_neutralisation_components, run=True)     
    
    S100 = bst.units.Splitter('S100',
                              ins = M101-0,
                              outs = ('neutralised_oil_for_transesterification',
                                       'Recovered_sodium_oleate_mixture'),
                              split = dict(
                                       Sodium_hydroxide = 0,
                                       Phosphatidylinositol = 1,
                                       OOO = 1,LnLnLn = 1,
                                       LLL = 1,PPP = 1,
                                       SSS = 1,Water = 1,
                                       Oleic_acid  = 0,
                                       Sodium_oleate =0,
                                       ))
                          
#Bleaching process is for bleaching colour related impurities
#Deodorisation process is for removing odors
#Dewaxing processes are intended for waxes present in the oil crystallizes, which give hazy appearance to the oil, 
#These processes were ignored for this process as the produced biodiesel is an intermediate product in the process 
# and is not sold as a co-product of the biorefinery [18]
# Even though High oleic oils generally have an increased stability over conventional oils, 
# Due to limited availability and high cost of the feedstock, the biodiesel derived from it might not be market competitive [7]

#Transesterification reaction conversion (X_tes) at baseline was assumed to be 95.61% based on biodiesel yield of HoSun (95.61%) provided in[8]
    reactions = tmo.ParallelReaction([
        tmo.Reaction('OOO + 3Methanol -> 3Methyl_oleate + Glycerol', reactant='OOO',  X = X_tes), 
        tmo.Reaction('LLL + 3Methanol -> 3Methyl_linoleate + Glycerol', reactant='LLL',  X = X_tes),
        tmo.Reaction('SSS + 3Methanol -> 3Methyl_stearate + Glycerol', reactant='SSS',  X = X_tes),
        tmo.Reaction('LnLnLn + 3Methanol -> 3Methyl_linolenate + Glycerol', reactant='LnLnLn',  X = X_tes),
        tmo.Reaction('PPP + 3Methanol -> 3Methyl_palmitate + Glycerol', reactant='PPP',  X = X_tes),
                                    ])
    
    transesterification_sys = create_transesterification_and_biodiesel_separation_system(ins = S100-0,
                                                                     outs = (biodiesel,
                                                                             crude_glycerol,
                                                                             waste_to_boilerturbogenerator),
                                                                     transesterification_reactions = reactions)
    
    M102 = bst.units.MixTank('M102',ins = (S100-1,water_for_sodium_oleate_sep),
                                           outs = free_fatty_acid_waste_mixture)
    def adjust_water_for_NaOH_sep(): 
    #Sodium hydroxide has a soluility of 0.9g/1ml (or 1Kg/L) in water [9]
    #sodium oleate has a solubility of 0.1Kg/ L [10]
    #Therefore, since sodium oleate is barely soluble in water, sodium hydroxide can be separated out
          water_for_sodium_oleate_sep.imass['Water'] = M102.ins[0].imass['Sodium_hydroxide']
    M101.add_specification(adjust_neutralisation_components, run=True)    
      
#References for "crude_HO_oil_to_biodiesel" system
#[1]Bailey's Industrial Oil and Fat Products, Edible Oil and Fat Products Processing Technologies By Alton Edward Bailey · 2005
# From section 2.4: Equipment for storage and handling of crude fats and oils 
#[2]Storage of crude veg oil : https://doi.org/10.1016/B978-1-63067-050-4.00003-9
#[3]Zufarov, Oybek, Štefan Schmidt and Stanislav Sekretár. “Degumming of rapeseed and sunflower oils.” (2008)
#[4]U. N. Annal, A. Natarajan, B. Gurunathan, V. Mani, and R. Sahadevan, “Challenges and opportunities in large-scale production of biodiesel,” in Biofuels and Bioenergy, Elsevier, 2022, 
# pp. 385–407. doi: 10.1016/B978-0-323-90040-9.00033-3.
#[5] L. C. Meher, D. Vidya Sagar, and S. N. Naik, “Technical aspects of biodiesel production by 
# transesterification—a review,” Renew. Sustain. Energy Rev., vol. 10, no. 3, pp. 248–268, 
# Jun. 2006, doi: 10.1016/j.rser.2004.09.002.
#[6] “Sunflower Oil Refining Process | Sunflower Oil Refinery Plant - Goyum.” 
# https://www.oilexpeller.com/sunflower-oil-refining-process/ (accessed Mar. 31, 2023)
#[7] N. T. Dunford, E. Martínez-Force, and J. J. Salas, “High-oleic sunflower seed oil,” High 
#Oleic Oils Dev. Prop. Uses, pp. 109–124, Jan. 2022, doi: 10.1016/B978-0-12-822912-5.00004-6.
#[8] https://pubs.acs.org/doi/full/10.1021/ef0502148
#[9] https://pubchem.ncbi.nlm.nih.gov/compound/Sodium-hydroxide#section=Solubility
#[10]https://pubchem.ncbi.nlm.nih.gov/compound/23665730#section=Solubility

######################################################################################################################################################################################################
#Area 200
# After degumming and production of biodiesel, it is sent for dihydroxylation [11]
@SystemFactory(
    ID = 'dihydroxylation_system',
    ins = [dict(ID = 'fresh_HP'),
            dict(ID = 'fresh_tungsten_catalyst'),                        
            dict(ID = 'recovered_tungstic_acid'),
            dict(ID = 'biodiesel'),
            ],
    outs = [dict(ID = 'condensate'),
            dict(ID = 'diol_product'),
            ],
    fixed_outs_size = True,     
              )
def dihydroxylation_system(ins,outs):
    fresh_HP, fresh_tunsgten_catalyst,recovered_tungstic_acid,biodiesel, = ins
    condensate,diol_product, = outs
    
# Fresh_Hydrogen_peroxide_feedtank
    T200 =  bst.units.StorageTank('T200',
                                ins = fresh_HP,
                                outs = 'fresh_HP_to_pump',
                                vessel_type= 'Field erected',
                                vessel_material='Stainless steel')#MOC from [12]
    P200 = bst.units.Pump('P200',
                      ins = T200-0,
                      outs = 'HP_to_mixer')
    
#Moles of methyl oleate in the patent [11] = 0.85*10/Mol.wt of methyl oleate = 0.02866
#Moles of hydrogen peroxide in the patent[11] = 0.6*2.3/ Mol. wt of hydrogen peroxide = 0.04057
#Ratio of hydrogen peroxide moles/methyl oleate moles =0.04057/ 0.02866 = 1.415144 #approx 1.4
    
    def adjust_HP_feed_flow(): 
        # moles_of_hydrogen_peroxide = 1.4* biodiesel.imol['Methyl_oleate'] based on above
        # added 2 instead to allow compatibility with UnandSen analysis scenarios
        moles_of_hydrogen_peroxide = 2*biodiesel.imol['Methyl_oleate'] 
        fresh_HP.imol['Hydrogen_peroxide'] = moles_of_hydrogen_peroxide
        fresh_HP.imass['Water'] = fresh_HP.imass['Hydrogen_peroxide']
    P200.add_specification(adjust_HP_feed_flow, run=True)  
    
#Tungstic acid Catalyst feed tank
    T201 = bst.units.StorageTank('T201',
                                  ins = fresh_tunsgten_catalyst,
                                  outs = 'fresh_catalyst_to_pump',
                                  vessel_type  = "Solids handling bin",#since it is a solid catalyst
                                  vessel_material='Carbon steel')

#recycled tungstic acid coming from the catalyst recovery section    
    M200 = bst.units.Mixer(ID = 'M200',
                            ins = (P200-0,
                                   T201-0,
                                   recovered_tungstic_acid,
                                   biodiesel),
                            outs = ('feed_to_heat_exchanger'))

   
#Tungstic acid is preferably 0.06% and 1.5% by moles with respect to the total moles of unsaturations[11]
#Tungstic acid can be recycled upto 6 times [13]

#Due to biosteam's user defined convergence criteria, sometimes during uncertainity and sensitivity analyses
#it may happen that the incoming recycled tungstic acid is very slightly more (0.01 times)
#Due to this, the fresh tungstic catalyst required becomes negative
#The if/else loops were added to handle this issue
#This does not impact any TEA and LCA results 

    def adjust_tungsten_catalyst_flow(tungstencatalyst_mol_factor,TA_cycles_of_reuse):
            moles_of_unsaturation = biodiesel.imol['Methyl_oleate']+ 2*biodiesel.imol['Methyl_linoleate'] + 3* biodiesel.imol['Methyl_linolenate'] 
            moles_of_tungstic_acid_required_per_cycle = tungstencatalyst_mol_factor * moles_of_unsaturation/TA_cycles_of_reuse
            if moles_of_tungstic_acid_required_per_cycle - recovered_tungstic_acid.imol['Tungstic_acid'] <0:
                M200.ins[1].imol['Tungstic_acid'] = 0
                recovered_tungstic_acid.imol['Tungstic_acid'] = moles_of_tungstic_acid_required_per_cycle
            else:
                M200.ins[1].imol['Tungstic_acid'] = moles_of_tungstic_acid_required_per_cycle - (recovered_tungstic_acid.imol['Tungstic_acid'])
            M200.run()
    M200.add_specification(adjust_tungsten_catalyst_flow,args = [0.0078,6])
    
##Dihydroxylation reaction is conducted under vaccuum under absolute pressure of 0.10-0.20*10^5 Pa [11]
#Water is continuosly removed to maintain proper H2O2 concentration

    R200 = units_baseline.DihydroxylationReactor('R200',
                                                  ins = M200-0, 
                                                  outs = (condensate,
                                                          diol_product                                        
                                                          ),
                                                  P = 0.1*1E5,#vacuum conditions to evaporate water
                                                  T = 62 + 273.15,#specs based on [11]
                                                  tau = 3.5, #specs based on [14] 
                                                 )  
    
#[11]CONTINUOUS PROCESS FOR THE PRODUCTION OF DERVATIVES OF SATURATED CARBOXYLIC ACDS,US 9.272,975 B2
#[12]http://ptpip.co.id/id/wp-content/uploads/2017/01/H2O2-60persen.pdf  
#[13]https://doi.org/10.1039/B921334A   
#[14]IMPROVED PROCESS FOR THE PRODUCTION OF DERIVATIVES OF SATURATED CARBOXYLIC ACIDS,EP 1 926 699 B1

#############################################################################################################################################################################################
##Oxidative cleavage system to cleave the dihydroxylated feed to produce the fatty acids[11]
#Area 300
@SystemFactory(
    ID = 'oxidative_cleavage_system',
    ins = [ dict(ID = 'dihydroxylation_product'),
            dict(ID = 'fresh_cobalt_catalyst_stream'),
            dict(ID = 'recovered_mixture_of_cobalt_catalyst'),
            dict(ID = 'air_for_oxidative_cleavage'),
            dict(ID = 'recycled_diols_and_other_fatty_acids'),
          ],                                   
    outs = [dict(ID = 'mixed_oxidation_products')],
    fixed_outs_size = True,     
              )
def oxidative_cleavage_system(ins,outs):
    dihydroxylation_product,fresh_cobalt_catalyst_stream,recovered_mixture_of_cobalt_catalyst,air_for_oxidative_cleavage,recycled_diols_and_other_fatty_acids, = ins
    mixed_oxidation_products, = outs 


    HX300 = bst.HXutility(ID = 'HX300',ins = dihydroxylation_product,
                          outs = 'heated_diol_stream',T = 60 + 273.15)
    P300 = bst.units.Pump('P300',
                             ins = HX300-0,
                             outs = 'diol_product',
                             P = 20*100000)  
    M300 = bst.units.Mixer('M300',
                            ins = (P300-0))
   
#Mass of oxygen required = 12-15Kg/hr per 11.4Kg/hr of total diol feed [11]
    T300 = bst.StorageTank('T300',
                            ins = fresh_cobalt_catalyst_stream,
                            outs = 'fresh_cobalt_catalyst_stream_to_mixer',
                            vessel_type = 'Solids handling bin',
                            vessel_material = 'Carbon steel'
                            )
    P301 = bst.Pump('P301',
                    ins = T300-0,
                    P = 2e+06,
                    outs = 'fresh_cobalt_acetate')
   
#Cobalt catalyst required is preferably between 0.3% and 1.5% by moles of diol molecules[11]
    R300 = units_baseline.OxidativeCleavageReactor('R300',
                                ins = (
                                       M300-0, #diol product
                                       P301-0,#fresh cobalt catalyst
                                       recovered_mixture_of_cobalt_catalyst,#recycled cobalt catalyst
                                       air_for_oxidative_cleavage, #air feed
                                       recycled_diols_and_other_fatty_acids
                                       ), 
                                outs = ( 'vented_gases',
                                        'mixed_oxidation_products_to_valve'),
                                tau = 3.5,
                                P = 20*1e5, 
                                T = 60 + 273.15,
                                V_max= 500,
                                length_to_diameter = 4,#[15] 
                                dT_hx_loop = 5,)
    
#Required amount of cobalt per diol moles is 0.3% and 1.5% [11]
#Mass of oxygen required = 12-15Kg/hr per 11.4Kg/hr of total diol feed [11]
#air_mass_factor = 13/11.4 
#Used a ratio of 2  to ensure 10% of oxygen is at the reactor outlet based on [11]
#Assuming that cobalt acetate tetrahydrate can be reuse for 6 times based on reusability of other heterogeneous cobalt catalysts [16],[17]

    def adjust_incoming_ratios(cycles_of_reuse,cobaltcatalyst_mol_factor,air_mass_factor):
        g_to_Kg = 1000
        total_diol_moles = dihydroxylation_product.imol['MDHSA'] +  dihydroxylation_product.imol['Tetrahydroxy_octadecanoate'] +  dihydroxylation_product.imol['Hexahydroxy_octadecanoate']
        R300.ins[1].empty()
        total_incoming_cobalt_catalyst_moles = recovered_mixture_of_cobalt_catalyst.imol['Cobalt_hydroxide'] 
        required_cobalt_moles = cobaltcatalyst_mol_factor*total_diol_moles/cycles_of_reuse
        
        if required_cobalt_moles-total_incoming_cobalt_catalyst_moles <0:
           R300.ins[1].imass['Cobalt_acetate_tetrahydrate']  = 0
           R300.ins[1].imass['Water'] =  0
           recovered_mixture_of_cobalt_catalyst.imol['Cobalt_hydroxide'] = required_cobalt_moles
        else:
            cobalt_mol_deficit = (required_cobalt_moles - total_incoming_cobalt_catalyst_moles)
            cobalt_mass_deficit = cobalt_mol_deficit*chems['Cobalt_acetate_tetrahydrate'].MW
            R300.ins[1].imass['Cobalt_acetate_tetrahydrate']  = cobalt_mass_deficit/g_to_Kg
            cobalt_hydroxide_recovered = recovered_mixture_of_cobalt_catalyst.imass['Cobalt_hydroxide']
            total_cobalt_mass = (cobalt_mass_deficit+cobalt_hydroxide_recovered)/g_to_Kg
            R300.ins[1].imass['Water'] =  65.66*total_cobalt_mass
        c = 0.21*air_mass_factor*(dihydroxylation_product.F_mass )
        d = 0.79*air_mass_factor*(dihydroxylation_product.F_mass)
        air_for_oxidative_cleavage.imass['Oxygen'] = c
        air_for_oxidative_cleavage.imass['Nitrogen'] = d
        R300.run()
    R300.add_specification(adjust_incoming_ratios,args = [6,#based on value for tungstic acid
                                                          0.015,#cobalt cat mol factor
                                                          2 #air mass factor
                                                          ])
#Valves do not have a cost and does not show up in the diagram    
    V300= bst.units.valve.IsenthalpicValve(ID = 'V300',
                               ins = R300-1,
                               outs = mixed_oxidation_products,
                               P = 101325) 
    T4 = bst.StorageTank(ins = recycled_diols_and_other_fatty_acids) #TODO: ask Sarang why this might be happening
    

#[15]https://processdesign.mccormick.northwestern.edu/index.php/Equipment_sizing#Cost
#[16]https://doi.org/10.1039/C9GC00293F
#[17]https://doi.org/10.1002/ange.202008261                               
   
#########################################################################################################                                
#Area 400
#Organic phase separation to separate aqueous portion 
#Aqueous portion contains catalysts and leftover hydrogen peroxide 
#Organic phase contains the mixed oxidation products
#This section is based on the catalyst recovery process highlighted in [18]
@SystemFactory(
    ID = 'organic_phase_separation_and_catalyst_recovery',
    ins = [
           dict(ID='oxidative_cleavage_products'),
           dict(ID ='sodium_hydroxide_stream'),
           dict(ID ='water_for_NaOH_soln_prep'),
           dict(ID ='calcium_chloride_for_cat_sept'),
           dict(ID ='conc_hydrochloric_acid'),
           dict(ID ='water_for_dilution'),
           ],                  
    outs = [
            dict(ID = 'dried_crude_fatty_acids'),            
            dict(ID = 'recovered_mixture_of_cobalt_catalyst'),  
            dict(ID = 'wastewater_from_cat_sep_1'),  
            dict(ID = 'hot_moisture_1'),
            dict(ID = 'emissions_from_dryer_1'),
            dict(ID = 'recovered_tungstic_acid'),
            dict(ID = 'hot_moisture_2'),
            dict(ID = 'emissions_from_dryer_2')           
            ],
    fixed_outs_size = True,     
              )
def organic_phase_separation_and_catalyst_recovery(ins,outs):
    oxidative_cleavage_products,sodium_hydroxide_stream,water_for_NaOH_soln_prep,calcium_chloride_for_cat_sept,conc_hydrochloric_acid,water_for_dilution, = ins
    dried_crude_fatty_acids,recovered_mixture_of_cobalt_catalyst,wastewater_from_cat_sep_1,hot_moisture_1,emissions_from_dryer_1,recovered_tungstic_acid,hot_moisture_2,emissions_from_dryer_2, = outs

#The organic phase and aqueous phase of the reaction mixture are separated
#The organic phase contains azelaic acid, pelargonic acid and other co-products which get separated out
#The aqueous phase contains water, tungstic acid and cobalt acetate 
    L400 = bst.units.LiquidsSplitCentrifuge('L400',
                                            ins= oxidative_cleavage_products,
                                            outs=('organic_phase_1'
                                                  'aqueous_phase_1'),
                                            split = ({'Hydrogen_peroxide': 0.0,   
                                                      'Water': 0.5,
                                                      'MDHSA': 1,'Tetrahydroxy_octadecanoate':1,
                                                      'Hexahydroxy_octadecanoate':1,
                                                      'Pelargonic_acid' : 1,'Azelaic_acid': 1,
                                                      'Methyl_oleate': 1,'Monomethyl_azelate' : 1,
                                                      'Monomethyl_suberate': 1,'Caprylic_acid': 1,
                                                      'Hexanoic_acid': 1,'Heptanoic_acid': 1,
                                                      'Malonic_acid': 0,'Methanol':0,'Glycerol': 0,
                                                      'Methyl_oleate': 1,
                                                      'Methyl_palmitate': 1,'Methyl_stearate':1,'Methyl_linoleate':1,
                                                      'Methyl_linolenate':1,'Methyl_caprylate':1,'Tungstic_acid': 0,'Cobalt_acetate_tetrahydrate':0,
                                                      'Propanoic_acid':0,  'Monoester_MDHSA_MMA':1,
                                                      'Diester_MDHSA_MMA':1,'Monoester_MDHSA_PA':1,
                                                      'Diester_MDHSA_PA':1,'Cobalt_chloride':0,
                                                      'Calcium_hydroxide':0,'Calcium_chloride':0,
                                                      'Calcium_tungstate':0,'Calcium_acetate':0,
                                                      'Cobalt_hydroxide':0,'HCl2':0,'Oxygen':1,
                                                      'Nitrogen':1,'Carbon_dioxide':1,'Malonic_acid':1,
                                                      'Propanoic_acid':1,'Methyl_oxo_nonanoicacid':1,'Nonanal':1
                                                      }))
    
    
#the organic phase contains some water and other low boiling acids which get separated out
    D401 = bst.BinaryDistillation(ID = 'D401', ins = L400-0,
                                  P = 10000,
                                  Lr = 0.999,
                                  Hr = 0.999,
                                  k = 2, outs = ('recovered_moisture_and_nonanal',
                                                 dried_crude_fatty_acids),
                                  LHK = ('Nonanal','Pelargonic_acid'))
    D401.check_LHK = False    
    
    HX403 = bst.HXutility(ID = 'HX403',ins = D401-0, T = 25+275,outs = 'cooled_moisture_nonanal_mixed_stream', rigorous = True) 
    
    P401 = bst.Pump(ID = 'P401', ins = HX403-0, outs = 'moisture_nonanal_stream_at_1atm_to_BT901',P = 101325)          
                                                               
#Below are steps for recovering the precipitates of the cobalt catalyst and tungstic 
    T400 = bst.StorageTank(ID = 'T400',
                           ins = sodium_hydroxide_stream,
                           outs = ('sodium_hydroxide_stream_for_catalyst_sep'))
    def adjust_NaOH():
        L400.run()
#The molar ratio of NaOH needed is 5-20 times that of cobalt acetate moles and 8-15 times that of tungstic acid moles [18]
        moles_of_NaOH_per_TA = 10 
        moles_of_NaOH_per_CA = 15
        total_moles = moles_of_NaOH_per_CA*L400.outs[1].imol['Cobalt_acetate_tetrahydrate']+ moles_of_NaOH_per_TA*L400.outs[1].imol['Tungstic_acid']
        T400.ins[0].imol['Sodium_hydroxide'] = total_moles
        T400.run()
    L400.add_specification(adjust_NaOH)

#Mix tank for making sodium hydroxide 40% wt/wt that is later added to the reaction liqor to make the liqor alkaline [18]
#Assuming it takes 15 mins for preparing NaOH solution
    M400 =  bst.MixTank(ID = 'M400',
                        ins = (T400-0,
                               water_for_NaOH_soln_prep),
                        outs = ('sodium_hydroxide_solution'),
                        tau = 15/60                        
                        ) 
 
    HX400 = bst.HXutility(ID = 'HX400',
                          ins = M400-0,
                          outs = ('heated_aqueous_liquor_to_40degs'),
                          T = 40+273.15)#Based on example 4 in [18]
    
    def adjust_water_conc():
        #adjusting water conc to make 40wt% NaOH
        T400.run()
        NaOH_mass = T400.outs[0].imass['Sodium_hydroxide']
        Water_mass =  NaOH_mass/0.6
        water_for_NaOH_soln_prep.imass['Water'] = Water_mass
        M400.run()
        HX400.run()
    T400.add_specification(adjust_water_conc) 
 
#Mixer to mix NaOH solution and reaction liqor mixture    
    M401 =  units_baseline.Sodium_hydroxide_tank(ID = 'M401',
                                                    ins = (L400-1,
                                                           HX400-0),
                                                    outs = ('cobalt_catalyst_precipitate_mixture'),
                                                    tau = 40/60,#Based on example 4 in [18]
                                                    )  
#Assuming clear separation between the aqueous phase and cobalt catalyst precipitate
    L401 = bst.LiquidsSplitCentrifuge(ID = 'L401',
                                ins = M401-0,
                                outs = ('suspended_cobalt_catalyst',
                                        'dissolved_tungstic_acid_solution',
                                         ),
                                split = {'Hydrogen_peroxide': 0.0,   
                                        'Water': 0.0,
                                        'Tungstic_acid': 0,
                                        'Cobalt_acetate_tetrahydrate':0,
                                        #products arising out of catalyst separation
                                        'Sodium_hydroxide':0,
                                        'Cobalt_hydroxide':1,
                                        'Malonic_acid':0,
                                        'Sodium_tungstate':0,
                                        'HCl2':0})
    
    recycled_water_for_washing1 = bst.Stream(ID = 'recycled_water_for_washing1',
                                             Water = 1,
                                             units = 'kg/hr'
                                             )
    M402 = bst.MixTank(ID = 'M402',
                       ins = (L401-0,
                              recycled_water_for_washing1),                       
                       outs =('suspended_cobalt_hydroxide'))
    
#Amount of water required for three times of precipitate washing mentioned in Ex 4[18]
#The precipitate is washed 3 times, the water is assumed to be recycled and reused
    def water_for_washing1():
        recycled_water_for_washing1.imass['Water'] = 3*L401.outs[0].imass['Cobalt_hydroxide']
        M402._run()
    L401.add_specification(water_for_washing1,run = True)       

#The recovered mix of cobalt is recycled back
    L402 = bst.LiquidsSplitCentrifuge(ID = 'L402',
                                ins = M402-0,
                                outs = ('recovered_mixture_of_cobalt_catalyst_to_pump',
                                        recycled_water_for_washing1,
                                         ),
                                split = {'Cobalt_hydroxide':1,
                                         'Water':0
                                        })  
    P400 = bst.Pump(ID = 'P400',
                    ins = L402-0,
                    outs = recovered_mixture_of_cobalt_catalyst,
                    P = 2e+06)#Pressure of the oxidative cleavage reactor (R300)
        
 #The alkali earth metal compound, here calcium chloride, can be anywhere between 2-15 times the tungsten moles[18]
    T401 =  bst.StorageTank(ID = 'T401',
                         ins = calcium_chloride_for_cat_sept,
                         outs = ('calcium_chloride_to_acid_preci'))
   
    M403 = units_baseline.Acid_precipitation_tank(ID = 'M403',
                                                  ins = (L401-1,
                                                         T401-0),
                                                  outs = ('calcium_tungstate_soln'),
                                                  tau = 1)
    
    def precipitation_reaction_2(calcium_chloride_per_TA_moles):
        Tungstic_acid_moles = L401.outs[1].imol['Sodium_tungstate']
        calcium_chloride_for_cat_sept.imol['Calcium_chloride'] = calcium_chloride_per_TA_moles*Tungstic_acid_moles        
        T401.run()        
    M403.add_specification(precipitation_reaction_2,args = [2],run=True)
#The tungstic acid precipitate was heated for 30mins and the cooled for another 30mins
#Under these conditions TA acid precipitated completely    
    HX401 = bst.HXutility(ID = 'HX401',
                          ins = M403-0, 
                          outs = ('aqueous_tungstic_acid_soln_at_60deg'),
                          T = 60+273.15)#based on [18]
 
    
    T402 =  bst.StorageTank(ID = 'T402',
                         ins = HX401-0,
                         outs = ('suspended_caclium_tungstate'),
                         tau = 30+30)#Assumed 30mins for heating and 30mins for cooling [18]
     
#Assuming clean separation between wastewater and moist calcium tungstate
    L403 = bst.LiquidsSplitCentrifuge(ID = 'L403',
                                ins = (T402-0),
                                outs = ('moist_calcium_tungstate',
                                        wastewater_from_cat_sep_1),
                                split = {'Hydrogen_peroxide': 0, 'Water': 0,
                                         'Tungstic_acid': 0,
                                         'Cobalt_chloride':0,
                                         'Calcium_hydroxide':0,'Calcium_chloride':0,
                                         'Calcium_tungstate':1,'Calcium_acetate':0,
                                         'Cobalt_hydroxide':0,'HCl2':0,'Malonic_acid':0})
    
    recycled_water_for_washing2 = bst.Stream(ID = 'recycled_water_for_washing2',
                                             Water = 1,
                                             units = 'kg/hr'
                                             )
    M404 = bst.MixTank(ID = 'M404',
                        ins = (L403-0,
                               recycled_water_for_washing2),
                        outs =('suspended_calcium_tungstate'))
    def water_for_washing2():
        recycled_water_for_washing2.imass['Water'] = 3*L403.outs[0].imass['Calcium_tungstate']
    M404.add_specification(water_for_washing2,run= True)     
 
    L404 = bst.LiquidsSplitCentrifuge(ID = 'L404',
                                ins = (M404-0),
                                outs = ('moist_calcium_tungstate',
                                         recycled_water_for_washing2
                                         ),
                                split = {'Hydrogen_peroxide': 0.0,   
                                                'Water': 0.2,
                                                'Tungstic_acid': 0,
                                                'Cobalt_chloride':0,'Calcium_hydroxide':0,
                                                'Calcium_chloride':0,'Calcium_tungstate':1,
                                                'Calcium_acetate':0,'Cobalt_hydroxide':0,
                                                'HCl2':0})           
                        
                       
    D403 = bst.DrumDryer(ID = 'D403',
                         ins = (L404-0,'air_1','natural_gas_1'),
                         outs = ('dry_calcium_tungstate',
                                 hot_moisture_1,
                                 emissions_from_dryer_1),
                         split = {'Hydrogen_peroxide': 1,   
                                         'Water': 1,
                                         'Tungstic_acid': 1,
                                         'Cobalt_chloride':1,
                                         'Calcium_hydroxide':0,
                                         'Calcium_chloride':1,'Calcium_tungstate':0,
                                         'Calcium_acetate':1,'Cobalt_hydroxide':1,
                                         'HCl2':1}) 

#Once the calcium tungstate is precipitated out followed by drying
#Then it is acidified to convert calcium tungstate to tungstic acid
    
    M405 = units_baseline.Tungstic_acid_precipitation_tank(ID = 'M405',
                       ins = (D403-0,
                              conc_hydrochloric_acid),
                       outs = ('acidified_calcium_tungstate_mixture'),
                       tau = 30/60 #Assuming that the precipitation happens in an hour
                       )
    def adjusting_amount_of_acid():  
#Amount of HCl added was adjusted to neutralise calcium tungstate completely      
#Conc HCl required is 35 wt.%  
            moles_of_HCl_required = D403.outs[0].imol['Calcium_tungstate'] 
            M405.ins[1].imass['HCl2'] = HCl2 = moles_of_HCl_required*36.46*3000/1000
            M405.ins[1].imass['Water'] = (65/35)*HCl2 
    M405.add_specification(adjusting_amount_of_acid,run = True)
    
    HX402 = bst.HXutility(ID = 'HX402',
                          ins = M405-0,
                          outs =('hot_mixture_of_calcium_tungstate'),
                          T = 90+273.15)#based on [18]

#The tungstic acid precipitate is diluted with water to obtain the precipitate #example 2 [18]
    M406 = bst.MixTank(ID = 'M406',
                       ins =(HX402-0,
                             water_for_dilution),
                       outs = 'tungstic_acid_mixture_for_washing')
    
    def adjusting_water_for_dilution():
        HX402._run()
        M406.ins[1].imass['Water'] = 3*M406.ins[0].imass['Tungstic_acid']
    M406.add_specification(adjusting_water_for_dilution, run = True)
    
    recycled_water_for_washing3 = bst.Stream(ID = 'recycled_water_for_washing3',
                                             Water = 1,
                                             units = 'kg/hr'
                                             )
#The precipitate obtained needs to be washed three times   
    M407 = bst.MixTank(ID ='M407',
                       ins = (M406-0,
                              recycled_water_for_washing3),
                       outs = ('suspended_tungstic_acid')
                       )
    
    def water_for_washing3():
        recycled_water_for_washing3.imass['Water'] = M406.outs[0].F_mass
    M407.add_specification(water_for_washing3,run = True)        
 
#The tungstic acid is centrifuged out, dried and recycled back
#According to [18] only 95% of tungstic acid can be recovered
    L405 = bst.LiquidsSplitCentrifuge(ID = 'L405',
                                ins = (M407-0),
                                outs = ('moist_tungstic_acid',
                                        'wastewater_from_cat_sep_2'),
                                split = {'Hydrogen_peroxide': 0.0,   
                                        'Water': 0.1,
                                        'Tungstic_acid': 0.95,
                                        'Cobalt_chloride':0,'Calcium_hydroxide':0,
                                        'Calcium_chloride':0,'Calcium_tungstate':0,
                                        'Calcium_acetate':0,'Cobalt_hydroxide':0,
                                        'HCl2':0},
                                        )  
    D404 = bst.DrumDryer(ID = 'D404',
                         ins = (L405-0,'air_2','natural_gas_2'),
                         outs =(recovered_tungstic_acid,
                                hot_moisture_2,
                                emissions_from_dryer_2),
                         split = {'Hydrogen_peroxide': 1,   
                                         'Water': 1,
                                         'Tungstic_acid': 0,
                                         'Cobalt_chloride':1,
                                         'Calcium_hydroxide':0,
                                         'Calcium_chloride':1,'Calcium_tungstate':1,
                                         'Calcium_acetate':1,'Cobalt_hydroxide':1,
                                         'HCl2':1}) 


    
#[18] in the Novomont patent number 5,599,514,Title: PROCESS FOR RECOVERING COBALT AND TUNGSTEN FROM REACTION LIQUORS   
#########################################################################################################    
# Nonanoic acid (Pelargonic acid) (500 level)
# Because of the heatsensitivity fatty acids need to be separateed at lower pressures [19]
# Novomont's patent does not specify the pressures for separation of pelargonic acid and monomethyl azelate
# The information was obtained from other patents


@SystemFactory(
    ID = 'nonanoic_acid_fraction_separation',
    ins = [dict(ID='dried_crude_fatty_acids')],       
    outs = [
            dict(ID ='recovered_C5_to_C8_MCA_fraction'),
            dict(ID = 'pelargonic_acid_rich_fraction'),            
            dict(ID = 'heavy_fatty_acids'),
            ],
    fixed_outs_size = True,     
              )


def nonanoic_acid_fraction_separation(ins,outs):
    dried_crude_fatty_acids, = ins
    C5_to_C8_fraction,pelargonic_acid_rich_fraction,heavy_fatty_acids, = outs

    H501 = bst.HXutility(ID = 'H501',
                          ins = dried_crude_fatty_acids,
                          outs = ('dried_crude_fatty_acids'),
                          T = 20 + 273)

#Pelargonic acid is separated under vaccuum of 25 mm Hg i.e 5000 Pa pressures in conventional processes [20]
#The top stream of the distillation column can be further purified [21]
#When pelargonic acid is seperated from azelaic acid, the crude azelaic acid contains about 15-20% of monocarboxylics [22]
    D501 = bst.ShortcutColumn('D501',
                                    ins = H501-0,
                                    outs = ('pelargonic_acid_for_further_purification',
                                            'heavy_fatty_acids_bottoms'),
                                    LHK = (
                                          'Methyl_oxo_nonanoicacid',
                                          'Malonic_acid'
                                          ),
                                    Lr = 0.999,
                                    Hr = 0.999,
                                    P = 2000,
                                    k = 2,
                                  )
    D502 = bst.ShortcutColumn('D502',
                                  ins = D501-0,
                                  outs = (C5_to_C8_fraction,
                                          pelargonic_acid_rich_fraction),
                                  LHK = ('Hexanoic_acid',
                                          'Pelargonic_acid'),
                                  Lr = 0.999,
                                  Hr = 0.999,
                                  P = 5000,
                                  k = 2,
                                  ) 
    
  
    P501 = bst.Pump('P501', ins = D501-1,
                      outs = heavy_fatty_acids)  

#[19] Heatsensitivity of fatty acids is mentioned in: Oleochemicals: all time players of green chemistry By Antonio Zarli
#[20] US patent 2818113, Method for making Azelaic acid  
#[21] US patent  2,890,230: PROCESS FOR PURIFICATICATION OF PELARGONIC ACID
#[22] US 9.248,381 B2, METHOD OF PURIFYING A DICARBOXYLIC 5,399,749 A 3, 1995 Rebrovic ACD   
#########################################################################################################
# Recovery of azelaic acid
#The reaction mixture contains monomethyl azelate that needs to be hydrolysed to obtain azelaic acid
#Area 600
@SystemFactory(
    ID = 'azelaic_acid_production',
    ins =  [
            dict(ID  = 'crude_heavy_fatty_acids'),
            dict(ID = 'water_for_emulsification1'),
            dict(ID = 'water_for_emulsification2'),
            dict(ID = 'water_for_emulsification3'),
            dict(ID = 'water_for_azelaicacid_extraction'),
            dict(ID = 'solvent_for_extraction'),
            ],  
    outs = [ dict(ID = 'wastewater3'),
             dict(ID = 'crude_methanol'),
             dict(ID = 'recycled_diols_and_other_fatty_acids'),
             dict(ID = 'azelaic_acid_product_stream'),
             dict(ID = 'fatty_acid_blend'),
            ],
    fixed_outs_size = True,     
              )
def azelaic_acid_production(ins,outs):
    crude_heavy_fatty_acids,water_for_emulsification1,water_for_emulsification2,water_for_emulsification3,water_for_azelaicacid_extraction,solvent_for_extraction,= ins
    wastewater3,crude_methanol,recycled_diols_and_other_fatty_acids,azelaic_acid_product_stream,fatty_acid_blend, = outs

    
    T602 = bst.StorageTank(ID = 'T602',
                            ins = bst.Stream( ID = 'polystyrene_based_catalyst',
                                              polystyrene_based_catalyst= 1,
                                              units = 'kg/hr'),
                            outs = ('resin_to_HydrolysisSystem'))
    
    S606 = bst.ReversedSplitter(ID = 'S606',ins = T602-0,
                                outs = ('resin_for_hydrolysis_1',
                                        'resin_for_hydrolysis_2',
                                        'resin_for_hydrolysis_3'))
#Hydrolysis process is based on [23]
#The resin used for hydrolysis is based on [24]
#The resin reuse was assumed to be 10 based on data available for esterification of FFAs [25]
#Specific reuse data particular to hydrolysis of FAME's to FFA was not found
    Monomethyl_azelate_for_recovery = bst.Stream('Monomethyl_azelate_for_recovery')
    R605 = units_baseline.HydrolysisReactor(ID = 'R605',
                                             ins = (crude_heavy_fatty_acids,
                                                    water_for_emulsification1,
                                                    Monomethyl_azelate_for_recovery
                                                    ),
                                              outs = ('methanol_water_mixture_for_separation',
                                                     'organic_mixture_to_holding_tank_1'),
                                              T = 120+273.15,                                        
                                              tau = 6.5, #considers regeneration time of 30 mins and reaction time of 6 hours [23],[24]
                                              P = 1000000,#Based on [23]
                                              V = 3785,
                                              cycles_of_reuse = 10,
                                              conc_of_active_sites = 4.7
                                              )
    def calculating_water_for_hydrolysis_1():
        #included 'Monomethyl azelate' twice to account for two hydrolysis sites in the FAME
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        mass_of_acids = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R605.ins[0].imol[i])
            mass_of_acids.append(F.R605.ins[0].imass[i])
            sum_moles.append(F.R605.ins[2].imol[i])
            mass_of_acids.append(F.R605.ins[2].imass[i])
        R605.ins[1].imass['Water'] = 5*sum(mass_of_acids)/85 #90% of the mixture is FAs and water,
        # water is 5% of the total[23]
    R605.add_specification(calculating_water_for_hydrolysis_1,run = True)
    
    def calculating_resin_for_hydrolysis(cycles_of_reuse):
        #Assuming the resin after regeneration does not lose significant amount of capacity
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R605.ins[0].imol[i])
            sum_moles.append(F.R605.ins[2].imol[i])
        #concentration of active sites in the catalyst are 4.7 [24]
        S606.outs[0].imass['polystyrene_based_catalyst'] = (sum(sum_moles)/4.7)/cycles_of_reuse
    S606.add_specification(calculating_resin_for_hydrolysis,args = [10], run = True)

    T606 = bst.StorageTank(ID = 'T606',
                           ins = R605-1,
                           outs = ('organic_mixture_to_second_hydrolysis_column'),
                           tau = 6.5)

    R606 = units_baseline.HydrolysisReactor(ID = 'R606',
                                            ins = (T606 -0,water_for_emulsification2,
                                                   ),
                                            outs = ('to_process_water_center_1',
                                                   'organic_mixture_to_holding_tank_2'),
                                            T = 120+273.15,                                        
                                            tau = 6.5, #considers regeneration time,
                                            P = 1000000,#Based on [23]
                                            V = 3785,
                                            cycles_of_reuse = 10,
                                            conc_of_active_sites = 4.7
                                            )
    def calculating_water_for_hydrolysis_2():
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        mass_of_acids = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R606.ins[0].imol[i])
            mass_of_acids.append(F.R606.ins[0].imass[i])
            sum_moles.append(F.R606.ins[2].imol[i])
            mass_of_acids.append(F.R606.ins[2].imass[i])
        R606.ins[1].imass['Water'] = 5*sum(mass_of_acids)/85 #90% of the mixture is FAs and water, water is 5% of the total[23]
    R606.add_specification(calculating_water_for_hydrolysis_2,run = True)
    
    def calculating_resin_for_hydrolysis(cycles_of_reuse):
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R606.ins[0].imol[i])
        S606.outs[1].imass['polystyrene_based_catalyst'] = (sum(sum_moles)/4.7)/cycles_of_reuse  
    S606.add_specification(calculating_resin_for_hydrolysis,args = [10], run = True)

    
    T607 = bst.StorageTank(ID = 'T607',
                           ins = R606-1,
                           outs = ('organic_mixture_to_third_hydrolysis_column'),
                           tau = 6.5)
    
    R607 = units_baseline.HydrolysisReactor(ID = 'R607',
                                            ins = (T607-0,water_for_emulsification3
                                                   ),
                                            outs = ('to_process_water_center_2',
                                                   'organic_mixture_to_holding_tank_2'),
                                            T = 120+273.15,                                        
                                            tau = 6.5, #considers regeneration time,
                                            P = 1000000,#Based on [23]
                                            V = 3785,
                                            cycles_of_reuse = 10,
                                            conc_of_active_sites = 4.7)
    def calculating_water_for_hydrolysis_3():
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        mass_of_acids = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R607.ins[0].imol[i])
            mass_of_acids.append(F.R607.ins[0].imass[i])
            sum_moles.append(F.R607.ins[2].imol[i])
            mass_of_acids.append(F.R607.ins[2].imass[i])
        R607.ins[1].imass['Water'] = 5*sum(mass_of_acids)/85
        #90% of the mixture is FAs and water, water is 5% of the total[23]
    R607.add_specification(calculating_water_for_hydrolysis_3,run = True)
    
    def calculating_resin_for_hydrolysis(cycles_of_reuse):
        list_of_acids_getting_hydrolysed = ['Monomethyl_azelate','Methyl_palmitate','Methyl_stearate',
                                            'Methyl_linoleate','Methyl_linolenate',
                                            'Methyl_oleate','Monomethyl_azelate']
        sum_moles = []
        for i in list_of_acids_getting_hydrolysed:
            sum_moles.append(F.R607.ins[0].imol[i])
        S606.outs[2].imass['polystyrene_based_catalyst'] = (sum(sum_moles)/4.7)/cycles_of_reuse    
    S606.add_specification(calculating_resin_for_hydrolysis,args = [10], run = True)

 
    T601 = bst.StorageTank(ID = 'T601',
                            ins = bst.Stream(ID = 'Liquid_HCl',
                                            Liquid_HCl = 0.35, 
                                            Water = 1-0.35,
                                            units = 'kg/hr'),
                            outs = ('regeneration_acid_to_pump'),
                            tau = 24*7)
    P601 =  bst.Pump(ID = 'P601',
                      ins = T601-0,
                      outs = 'regeneration_acid_to_HydrolysisSystem') 
       
    def calculating_acid_for_regeneration(cycles_of_reuse,BV_per_h):
        T602.run()
        density_of_resin_in_kg_per_m3 = 0.77 #[24]
        total_resin_required = T602.ins[0].F_mass
        T601.ins[0].F_vol = (total_resin_required*BV_per_h/density_of_resin_in_kg_per_m3)/cycles_of_reuse #BV_per_h based on [9]
    T601.add_specification(calculating_acid_for_regeneration,args = [10,2], run = True)
 

#Mix tank to collect all the methanol
#Selling biomethanol might be more beneficial than recycling 
#it because it sells at a higher price than conventional methanol [26]

    M608 = bst.Mixer(ID = 'M608',
                    ins = (R605-0,R606-0,R607-0),
                    outs = ('to_separate_out_methanol'),
                    )
    
    S607 = units_baseline.Methanolseparationsystem(ID = 'S607',
                                                   ins = M608-0,
                                                   outs = ('crude_methanol',
                                                           wastewater3))
    T603 = bst.MixTank( ID = 'T603',
                        ins = S607-0,
                        outs = (crude_methanol))
    
# Generally temperatures about 280 C.are used at pressures between 1.0 to 30mm Hg are used for azelaic acid [27]
    HX601 = bst.HXutility(ID = 'HX601',
                          ins = R607-1,
                          outs = 'heated_azelaic_acid_rich_stream',
                          T = 200+273.15) #[27]
    P605 = bst.Pump(ID = 'P605',
                  ins = HX601-0,
                  outs = 'azelaic_stream_for_heavy_acid_removal',
                  P = 10000)
  
    D604 =  bst.BinaryDistillation('D604',
                                  ins = P605-0,
                                  outs = ('azelaic_acid_rich_fraction',
                                          'diols_and_other_fatty_acids_for_recycling_for_cooling'
                                          ),
                                  LHK = ('Monomethyl_azelate',
                                         'MDHSA'
                                          ),
                                  Lr=0.95,
                                  Hr=0.95,
                                  P = 3000, #about 30 mm Hg, which is 
                                  #the max recommended
                                  k = 2,
                                  partial_condenser= True
                                  )
    D604.check_LHK = False
    
    H604 = bst.HXutility(ID = 'H604',
                          ins= D604-1,
                          outs = 'recycled_diols_and_other_fatty_acids_to_pump',                        
                          T = 333.15)
    P611 = bst.Pump(ID = 'P611',
                         ins = H604-0,
                         outs = recycled_diols_and_other_fatty_acids,
                         P = 2e+06)
    
# Hot water extraction to separate out azelaic acid because azelaic acid shows solubility in water
# The top stream of D604 distillation column is the prepurified azelaic acid stream
   
    T605 = bst.StorageTank(ID = 'T605',
                            ins = solvent_for_extraction,
                            outs = 'solvent_for_extraction_to_mixer',
                            vessel_material='Stainless steel')

#reaction mixture is coming in from D604 at 6000Pa
    HX603 =  bst.HXutility(ID = 'HX603', ins = D604-0, 
                            outs = ('reaction_mixture'),
                            T = 273.15 + 15,
                            rigorous = True
                            ) 

    P603 = bst.IsentropicCompressor(ID = 'P603',
                                    ins = HX603.outs[0],
                                    P = 101325,
                                    outs = 'reaction_mix_at_atm_P',
                                    vle = True)
    
    recycled_solvent_for_extraction = bst.Stream(ID = 'recycled_solvent_for_extraction')

#Below HX was added to reduce the temperature as the Capcost of P60 was very high    
    H612 = bst.HXutility(ID = 'H612', ins = recycled_solvent_for_extraction,
                        outs = 'cooled_solvent_Stream',
                        T = 25+273,
                        cool_only=True,
                        )
    
    P610 = bst.Pump(ID ='P610',ins = H612-0, 
                   P = 101325,
                   outs = 'recylec_solvent_to_M606',
                   pump_type='Gear')
   
    M606 = bst.Mixer('M606',ins = (P603-0,T605-0,P610-0),
                      outs = ('solvent_organics_mixture_for_extraction'))
    
    # The water is adjusted to make sure azelaic acid is 13% of total added water [27] 
#The solvent added is about 2.2 times mass of prepurified azelaic acid stream [28]   
    def solvent_for_extraction(solvent_factor):
        # M606.run()
        # 0.3:1 to 2.5:1 ratio of weight of solvent: weight of azelaic acid #[27]
        Total_required_solvent = solvent_factor*D604.outs[0].imass['Azelaic_acid']
        if Total_required_solvent-M606.ins[2].imass['Heptane'] < 0:
            M606.ins[1].imass['Heptane']  = 0
            M606.ins[2].imass['Heptane']  = Total_required_solvent
        else:
            M606.ins[1].imass['Heptane']  = Total_required_solvent-M606.ins[2].imass['Heptane']    
    M606.add_specification(solvent_for_extraction,args = [0.3], run = True) 
    
    H608 = bst.HXutility(ID = 'H608', 
                          ins = M606-0,
                          outs = 'heated_combined_organics_mixture',
                          T = 90+273.15
                          ) 
    
    recycled_water_for_LLE = bst.Stream('recycled_water_for_LLE') 
    M605 = bst.Mixer('M605',ins = (water_for_azelaicacid_extraction,
                                    recycled_water_for_LLE),
                      outs =('combined_water_for_LLE'))  
    
    HX602 = bst.HXutility(ID = 'HX602',
                          ins = M605.outs[0],
                          outs = 'hot_water_for_extraction',
                          T = 90+273.15)     
    P608 = bst.Pump(ID = 'P608',ins = HX602-0,P = 101325,outs = 'heated_combined_water_stream')
# The partition coefficients for the multistage mixer settler are based on [27]
    MMS601 = bst.units.MultiStageMixerSettlers(ID = 'MMS601',
                                   ins = (H608-0, P608-0),
                                   outs = ('solvent_monocarboxylics_mixture','Water_AA_extract'),
                                   partition_data={'rafinate_chemicals': ('Water'),
                                                   'extract_chemicals': ('Heptane','Caprylic_acid','Hexanoic_acid',
                                                                         'Heptanoic_acid','Pelargonic_acid',
                                                                         'Methyl_palmitate','Methyl_stearate',
                                                                         'Methyl_linoleate','Methyl_linolenate', 
                                                                         'Methyl_oleate','MDHSA','Tetrahydroxy_octadecanoate',
                                                                         'Palmitic_acid','Stearic_acid',
                                                                         'Linoleic_acid','Propanoic_acid',
                                                                         'Hexahydroxy_octadecanoate',
                                                                         'Linolenic_acid','Oleic_acid'),
                                                 'IDs': (
                                                         'Malonic_acid',#<C8 DCA
                                                         'Monomethyl_suberate',#C8 DCA
                                                         'Azelaic_acid',#C9 DCA
                                                         'Monomethyl_azelate',#C9 DCA
                                                         ),
                                                   'K': np.array([
                                                                  0.020384404,
                                                                  0.082896576,
                                                                  0.085755078,
                                                                  0.085755078,  
                                                                  
                                                                  ]),
                                                   },N_stages= 12)#[27]
    def water_for_extraction(x_water_fraction):
        D604.run()
        #Weight of water to azelaic acid, 3.5:1 to 20:1 [27]
        total_water_required = x_water_fraction*D604.outs[0].imass['Azelaic_acid']
        if total_water_required-M605.ins[1]['l'].imass['Water'] < 0:
            M605.ins[0].imass['Water']  = 0
            M605.ins[1]['l'].imass['Water']  = total_water_required
        else:
            M605.ins[0].imass['Water']  = total_water_required-M605.ins[1]['l'].imass['Water']
    M605.add_specification(water_for_extraction,args = [5.5],run = True)
    
#Evaportation Drying zone [27]   
    
    P607 = bst.Pump(ID = 'P607',
                    ins=MMS601-1, 
                    P= 10000)
    H605 = bst.HXutility(ID = 'H605',
                        ins = P607-0,
                          outs = 'feed_at_bubble_point_',
                          T = 350)

#TODO: need to change LHK for the below to have a purer aa stream    
    
    E601 = bst.BinaryDistillation('E601',
                    ins= H605-0,
                     outs=('recovered_water_stream',
                           'azelaic_acid_stream',
                           ),
                     
                     LHK = (
                         'Water',
                         'Malonic_acid',
                     ),
                     Lr=0.99,
                     Hr=0.99,
                     P = 4000,#Using highest pressure 30mmHg to reduce costs
                     k = 1.25,
                     partial_condenser= True,
                     is_divided= True,
                     vacuum_system_preference= 'Steam-jet ejector')
          
#Splitter to ensure 75% of the wastewater is being recycled as mentioned in [27]
    S605 = bst.Splitter(ID = 'S605',
                        ins = E601-0,
                        outs = ('water_for_LLE',
                                'wastewater'),
                        split = 0.75) 
    
    HX606 = bst.HXutility(ID = 'HX606',
                          outs = 'recycled_water_to_pump' ,
                          ins = S605-0,
                          T = 25+273.15,
                          rigorous = True
                          )  
    P609 = bst.Pump(ID = 'P609',
                         ins = HX606-0,
                         outs = recycled_water_for_LLE,
                         P = 101325)
    
    HX605 = bst.HXutility(ID = 'HX605',
                          ins = E601-1,#P602-0,
                          outs = 'heated_aa_mix_for_sep',
                          T = 280+273)
  
    D605 = bst.units.ShortcutColumn(ID = 'D605',
                                        ins = HX605-0,
                                        outs = ('heavy_boiling_azelaic_acid_stream',
                                                Monomethyl_azelate_for_recovery,
                                                
                                                ),
                                        LHK = (
                                            'Azelaic_acid',
                                            'Monomethyl_azelate',
                                        ),
                                        Lr=0.999,
                                        Hr=0.999,
                                        P = 3999.67105,#Using highest pressure 30mmHg to reduce costs
                                        k = 1.25,
                                        partial_condenser= True                                        
                                        )
    # D605.check_LHK = False
   
    HX604 = bst.HXutility(ID = 'HX604',
                          ins = D605.outs[0],
                          outs = 'Pre_cooled_stream',
                          T = 100 +273.15)


    D607 = units_baseline.SolidsFlaker(ID = 'D607',
                                        ins = HX604.outs[0],
                                        outs = azelaic_acid_product_stream,
                                        T_out = 60 + 273.15,#Lower than the melting point of Stearic acid
                                        ) 

###Recycling the solvent

    P610 = bst.Pump(ID = 'P610', ins = MMS601-0,
                                 P = 4000)
        

    F608 = bst.Flash(ID = 'F608',
                        ins = P610-0 ,
                        outs = (recycled_solvent_for_extraction,
                                'fatty_acid_blend_for_mixing'),
                        P = 4000,
                        T = 373)
    
    M607 = bst.MixTank(ID = 'M607',
                       ins = (F608-1,),
                       outs = fatty_acid_blend)
    def change_phasefromLtol():
        MMS601.run()
        MMS601.outs[0].phase = 'l'
    MMS601.add_specification(change_phasefromLtol)
    
#TODO: try separating out MDHSA

#[23]: #based on the possible hydrolysis method patent: WO 03/087027
#[24]: https://www.lenntech.com/Data-sheets/Rohm-&-Haas-Amberlyst-15wet-L.pdf   
#[25]: http://dx.doi.org/10.1016/j.biortech.2009.07.084    
#[26]: https://www.biofuelsdigest.com/bdigest/2017/08/24/methanol-and-bio-economy-now-and-the-future/
#[27]: US patent (2003/0032825 A1),METHOD FOR PURIFYING AZELAIC ACID
#[28]: US patent(2,998,439 ): PROCESS FOR THE SEPARATION AND RECOVERY OF MONOBASIC AND DIBASIC ACIDS      

###########################################################################################################################################################################
#The baseline process is production of azelaic acid and pelargonic acid from high oleic soybean oil (vistive brand)
#Other compositions were used in the uncertainity and sensitivity analyses
#The phopholipid content (1%), FFA content (0.95%) and Water content (0.05%) were assumed to be constant across all varieites of feedstock

@SystemFactory(ID = 'aa_baseline_sys',
               )
def aa_baseline_sys(ins,outs,tag_compositions):
    recovered_tungstic_acid = bst.Stream(ID = 'recovered_tungstic_acid')
    recycled_diols_and_other_fatty_acids = bst.Stream(ID = 'recycled_diols_and_other_fatty_acids')
    recovered_mixture_of_cobalt_catalyst = bst.Stream(ID = 'recovered_mixture_of_cobalt_catalyst')  
    
    ob0 = crude_HO_oil_to_biodiesel(ins = (bst.Stream(ID='crude_vegetable_oil',
                                                        PPP = tag_compositions['PPP'],
                                                        SSS=  tag_compositions['SSS'],
                                                        OOO=  tag_compositions['OOO'],
                                                        LLL=  tag_compositions['LLL'],
                                                        LnLnLn = tag_compositions['LnLnLn'],
                                                        PL= 1,
                                                        MAG=0,
                                                        DAG=0,
                                                        Water=0.05,
                                                        Oleic_acid=0.95, 
                                                        total_flow = 34635.99842,
                                                        units = 'kg/hr',
                                                        phase = 'l'),
                                             bst.Stream(ID = 'base_for_saponification_of_FFA',
                                                        Sodium_hydroxide = 1,
                                                        units = 'kg/hr',
                                                        ),
                                             bst.Stream(ID = 'water_for_degumming',
                                                        Water = 1,
                                                        T = 25 + 273.15,
                                                        units = 'kg/hr'), 
                                             bst.Stream(ID = 'citricacid_for_degumming',
                                                        Citric_acid = 1,
                                                        T = 25+273.15,
                                                        units = 'kg/hr',
                                                        ),
                                             bst.Stream(ID = 'water_for_degumming_2',
                                                        Water = 1,
                                                        T= 25+ 273.15,
                                                        units = 'kg/hr'),
                                             bst.Stream(ID = 'water_for_sodium_oleate_sep',
                                                        Water = 1,
                                                        T = 25+273.15,
                                                        units = 'kg/hr')),
                                              X_tes = 0.95)#Transesterification reaction conversion discussed in Area 100
    
    ob1 = dihydroxylation_system(ins = (bst.Stream(ID='fresh_HP',
                                                Hydrogen_peroxide = 0.5,
                                                Water = 0.5,
                                                T = 298.15,
                                                units = 'kg/hr'),
                                    bst.Stream(ID = 'fresh_tungsten_catalyst',
                                                Tungstic_acid = 1),
                                    recovered_tungstic_acid,
                                    ob0.outs[1] #biodiesel from previous section
                                    ))
    
    ob2 = oxidative_cleavage_system(ins = (ob1.outs[1],#diol product from previous section
                                            bst.Stream(ID ='fresh_cobalt_catalyst_stream', #catalyst for oxidative cleavage
                                                        Cobalt_acetate_tetrahydrate  = 1.5/100,
                                                        Water = 1- 1.5/100,
                                                        units = 'kg/hr',
                                                        ),
                                            recovered_mixture_of_cobalt_catalyst,
                                            bst.Stream(ID = 'air_for_oxidative_cleavage',
                                                        Oxygen = 0.21,
                                                        Nitrogen = 0.79,
                                                        phase = 'g',
                                                        units = 'kg/hr',
                                                        P = 2e+06),
                                            recycled_diols_and_other_fatty_acids,
                                            ))
    ob3 = organic_phase_separation_and_catalyst_recovery(ins = (ob2.outs[0],
                                                          bst.Stream(ID ='sodium_hydroxide_for_cat_sep',
                                                                    Sodium_hydroxide = 1,
                                                                    units = 'kg/hr'), 
                                                          bst.Stream(ID = 'water_for_NaOH_soln_prep',
                                                                    Water = 1,
                                                                    units = 'kg/hr'),
                                                        bst.Stream(ID = 'calcium_chloride_for_cat_sep',
                                                                    Calcium_chloride = 1,
                                                                    units = 'kg/hr'),
                                                          bst.Stream(ID ='conc_hydrochloric_acid', 
                                                                    Liquid_HCl = 35/100,
                                                                    Water = 65/100,
                                                                    units = 'kg/hr'),
                                                          bst.Stream(ID = 'water_for_dilution',
                                                                    Water = 1,
                                                                    units = 'kg/hr')),                                                                 
                                                          outs = (
                                                                  bst.Stream(ID = 'dried_crude_fatty_acids'),
                                                                  recovered_mixture_of_cobalt_catalyst, 
                                                                  bst.Stream(ID = 'wastewater_from_cat_sep_1'),
                                                                  bst.Stream(ID = 'hot_moisture_1'),
                                                                  bst.Stream(ID = 'emissions_from_dryer_1'),                                                                 
                                                                  recovered_tungstic_acid,
                                                                  bst.Stream(ID = 'hot_moisture_2'),
                                                                  bst.Stream(ID = 'emissions_from_dryer_2')  
                                                                  ))
    ob5 = nonanoic_acid_fraction_separation(ins = (ob3.outs[0]))
                                            
    ob6 = azelaic_acid_production(ins = (ob5.outs[2],
                                          bst.Stream(ID ='water_for_emulsification1',
                                                      Water = 1,
                                                      units = 'kg/hr'),
                                          bst.Stream(ID ='water_for_emulsification2',
                                                      Water = 1,
                                                      units = 'kg/hr'),
                                          bst.Stream(ID ='water_for_emulsification3',
                                                      Water = 1,
                                                      units = 'kg/hr'),
                                          bst.Stream(ID = 'water_for_azelaicacid_extraction',
                                                      Water = 1,
                                                      units = 'kg/hr'),
                                          bst.Stream(ID = 'solvent_for_extraction',
                                                    Heptane = 1,
                                                      units = 'kg/hr')),
                                        outs = (
                                          bst.Stream(ID = 'wastewater3'),
                                          bst.Stream(ID = 'crude_methanol'),    
                                          recycled_diols_and_other_fatty_acids,
                                          bst.Stream(ID = 'azelaic_acid_product_stream', units='kg/hr'),
                                          bst.Stream(ID = 'fatty_acid_blend',units = 'kg/hr')))
    
##########################################################################################################################################################################################################################################################################################################################################    
# All the Facilities (Area 900)

        
##########################################################################################################################################################################################################################################################################################################################################    
    MT902 = bst.Mixer(ID = 'MT902',
                      ins = (F.wastewater_from_cat_sep_2,
                             F.wastewater_from_cat_sep_1,
                             F.moisture_nonanal_stream_at_1atm_to_BT901,
                             F.wastewater
                             ))
                      
#High rate wastewater treatment system available in biosteam was designed specifically for biorefinery wastewater
    WWT901 = bst.create_conventional_wastewater_treatment_system(ID = 'WWT901',
                                                                  ins = MT902-0,
                                                                  outs = ('biogas_from_wastewater_treatment',
                                                                          'sludge_from_wastewater_treatment',
                                                                          'RO_treated_water_from_wastewater_treatment',
                                                                          'brine_from_wastewater_treatment'),#brine goes to waste
                                                                  autopopulate=False
                                                                  )
#TODO; methane not being produced somehow    
#TODO; try to figure out the high rate wastewater treatment issue    
    # WWT901 = bst.create_high_rate_wastewater_treatment_system(ID = 'WWT901',
    #                                                           ins = F.MT902-0,
    #                                                             outs = ('RNG','biogas',
    #                                                                     'sludge',
    #                                                                     'RO_treated_water',
    #                                                                     'brine'),#brine goes to waste
    #                                                             autopopulate=False,
    #                                                             autorename= False,
    #                                                             process_ID = 9,
    #                                                             )
                      
#Streams to boiler turbogenerator,Liquid/Solid waste streams mixer
    M901 = bst.Mixer( ID = 'M901',
                      ins = (
                               F.polar_lipids_to_boilerturbogenerator, 
                               F.free_fatty_acid_waste_mixture,
                               F.waste_to_boilerturbogenerator,
                               WWT901.outs[1],#sludge from WWT
                               ),
                        outs = ('total_effluent_to_be_burned')
                        )
    
#This unit burns the streams provided to it to generate heat and electricity
    BT901 = bst.BoilerTurbogenerator(ID ='BT901',
                                     ins = (M901-0,
                                                WWT901.outs[0],#biogas from WWT
                                                'boiler_makeup_water',
                                                bst.Stream(ID ='natural_gas',units = 'kg/hr'),
                                                bst.Stream(ID ='lime_boiler',units = 'kg/hr'),
                                                bst.Stream(ID ='boiler_chems', units = 'kg/hr'),
                                                ),
                                     outs = (bst.Stream('emissions_from_boilerturbogen',price = 0, units = 'kg/hr'),
                                                bst.Stream('rejected_water_and_blowdown_to_PWT',price = 0, units = 'kg/hr'), #this can be reused as process water
                                                bst.Stream(ID='ash_disposal' , units = 'kg/hr')),
                                     turbogenerator_efficiency=0.85,
                                     boiler_efficiency = 0.8,
                                     satisfy_system_electricity_demand =  True,
                                      
                                        )
    CW901 = bst.ChilledWaterPackage('CW901') #Chilled water package for cooling requirements                                 
    CT901 = bst.CoolingTower(ID ='CT901')
    CT901.outs[1].price = 0 #'cooling_tower_blowdown'
    CT901.outs[2].price = 0 #'cooling_tower_evaporation'
    CT901.ins[0].price = 0 
    CT901.outs[0].price = 0 
#All the streams that are required in the different sections for production of azelaic acid
    process_water_streams_available = (
                                          F.stream.water_for_emulsification1,#Water used for hydrolysis and emulsification
                                          F.stream.water_for_emulsification2,#Water used for hydrolysis
                                          F.stream.water_for_emulsification3,#Water used for hydrolysis
                                          F.stream.water_for_degumming,#Water used for degumming the oils from the polar lipids
                                          F.stream.water_for_degumming_2,#Second Water stream used for degumming the oils from the polar lipids
                                          F.stream.biodiesel_wash_water, #Wash water for biodiesel
                                          F.stream.water_for_azelaicacid_extraction,                                                                        
                                          CT901.outs[1],#Cooling_tower_blowdown_from_cooling tower
                                          BT901.outs[1],#rejected_water_and_blowdown from boilerturbogen   
                                          )                         


    makeup_water_streams_available = (F.stream.cooling_tower_makeup_water,#This is the second inlet to cooling tower
                                      F.stream.boiler_makeup_water #This is the second inlet to boilerturbogen
                                        )

    system_makeup_water = bst.Stream('system_makeup_water')
 

    MT901 = bst.Mixer(ID = 'MT901',
                      ins = (F.R200.outs[0],
                             F.wastewater3,
                             ))
                      
    
    PWT901 = bst.ProcessWaterCenter(ID = 'PWT901',
                              ins = ('clean_water',
                                      system_makeup_water,
                                      MT901-0,
                                      WWT901.outs[2] #RO water from WWT901
                                      ),
                              outs = (bst.Stream(ID = 'process_water', units ='kg/hr'),
                                      bst.Stream(ID ='unused_clean_water', price = 0, units = 'kg/hr')),
                              makeup_water_streams = makeup_water_streams_available,
                              process_water_streams = process_water_streams_available 
                               )
    
    plant_air_in =  bst.Stream('plant_air_in',
                                phase='g', Nitrogen=0.79, 
                                Oxygen=0.21,units='kg/hr')
    ADP901 = bst.AirDistributionPackage(ID='ADP901',
                                          ins=plant_air_in,
                                          outs = 'plant_air_out')
    @ADP901.add_specification(run=True)
    def adjust_plant_air(): 
        total_air_required = sum([F.air_1.F_mass,
                                  F.air_2.F_mass,
                                  F.air_for_oxidative_cleavage.F_mass,
                                  F.air_lagoon.F_mass
                                  ])
        plant_air_in.imass['Oxygen'] = total_air_required*0.22
        plant_air_in.imass['Nitrogen'] = total_air_required*0.78

#TODO: discuss the heat exchanger network        
        
    
    # HXN901 = bst.facilities.HeatExchangerNetwork('HXN901',ignored  = [F.D604.reboiler,
    #                                                             F.D605.reboiler,
                                                                # F.D501.reboiler,
                                                                # F.D502.reboiler,
                                                                # F.D401.reboiler,

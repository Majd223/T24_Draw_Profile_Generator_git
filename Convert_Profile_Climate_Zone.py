# -*- coding: utf-8 -*-
"""
Created on Thursday Oct 31 10:30 AM

This script recreates the T24 hot water draw profiles for residential buildings
based on a change in the climate zone required.It aims to give the user the ability
to move a set of profiles from one zone to another.

Depending on the user's needs, the script can convert any number of files in a single run,
and converts every one of those files to the specified range of climate zones provided, at once.

Currently, the script does not group the output files together. They are simply
stored in /DrawProfiles/[Building_Type]/[Water]/ like the input file

It is also completely acceptable to change the defined water temperatures in the
%##---CONSTANTS--- section; The script recalculates all of the numbers that are based
on these.

Timing insights ( Nathan's Computer - one profile, approx 27000 rows long):
Total time - 1.4 sec.
importing one weather file - 37 ms (3%)
all work on weather file including importing the file - 40 ms (3%)
deleting unneeded columns in dataframe - 2 ms (0%)
inputting the new climate data (27000 rows) - 600 ms (vs approx 800 ms with swifter) (42%-55%)
other final datframe manipulations to get back to the original format - 27 ms (3%)
print the final dataframe to csv -  470 ms (33%)

Timing insights ( Nathan's Computer - one profile, approx 800 rows long):
Total time - 0.09 sec.
importing one weather file - 37 ms
all work on weather file including importing the file - 40 ms
deleting unneeded columns in dataframe - 2 ms
inputting the new climate data (27000 rows) - 19 ms
other final datframe manipulations to get back to the original format - 27 ms
print the final dataframe to csv -  20 ms

Timing insights (Nathan's Computer - convert to all climate zones, approx 27000 rows long):
total time - 17 sec. with swifter, 21 sec. without swifter
each weather data swap with swifter - 900 ms
each weather data swap without swifter - 600 ms

Timing insights (Nathan's Computer - convert to all climate zones, approx 800 rows long):
total time - 17 sec. with swifter, 21 sec. without swifter
each weather data swap with swifter - 900 ms
each weather data swap without swifter - 600 ms

@author: Nathan Iltis
"""
#%%-------------------------------IMPORT STATEMENTS--------------------------
import pandas as pd
import sys
import os
import time
import swifter
from linetimer import CodeTimer
#%%------------------------------TIMER--------------------------------------
start_time = time.time() # mark the beginning of the execution time for reference back to later
#%%------------------------------INPUTS--------------------------------------
#Folder paths - assumes the profile has been created and is in the appropriate folder
#file to convert to a new climate zone:
Folder = os.path.dirname(__file__) + os.sep #The path to the folder where you have the base files for this script stored
Folder_WeatherData = Folder + os.sep + 'WeatherFiles' #This states the folder that CBECC weather data files are stored in

Possible_Climate_Zones = list(range(1,17)) # list of all possible climate zones
New_Climate_Zones = list(range(2,17)) #specify which climate zones to convert the file to - can be a number from 1-16
#file to convert to a new climate zone:
File = "Bldg=Single_CZ=1_Wat=Hot_Prof=5_SDLM=Yes_CFA=3500_Inc=['F', 'S', 'C', 'D', 'B'].csv" # mjust use double-quotations since string has singles already
Split_Up = File.replace(".csv","").split(sep = '_')
Specifier_Dict = {each.split(sep = "=")[0] : each.split(sep = "=")[1] for each in Split_Up}

Building_Type = Specifier_Dict['Bldg'] #Either 'Single' for a single family or 'Multi' for a multi-family building
SDLM = Specifier_Dict['SDLM'] #Either 'Yes' or 'No'. This flag determines whether or not the tool has added SDLM into the water flow calculations
Water = Specifier_Dict['Wat'] #Either 'Mixed' or 'Hot'. Use 'Mixed' to retrieve the water exiting the fixture, having mixed both hot and cold streams. Use 'Hot' to retrieve only the hot water flow
Conditioned_Area = Specifier_Dict['CFA']
ClimateZone = Specifier_Dict['CZ']

File_Location = Folder + os.sep + 'DrawProfiles' + os.sep + Building_Type + os.sep + Water + os.sep + File
Folder_Output = File_Location
#%%-----------------------------ERROR CHECKING-------------------------------
#If the user has tried to convert a mixed water profile
if Water != 'Hot': #must be a hot water draw profile
    print("Must be a Hot water draw profile, this is mixed so the climate doesn't matter") #Return an error
    sys.exit() #And exit the program
if len(set(Possible_Climate_Zones) & set(New_Climate_Zones)) == 0:
    print("At Least One Climate Zone in the range of 1-16 Must Be Provided") #Return an error
    sys.exit() #And exit the program
if max(New_Climate_Zones) > 16 or min(New_Climate_Zones) < 1:
    print("Please Provide Valid Climate Zone Numbers (in range 1-16)") #Return an error
    sys.exit() #And exit the program
#%%-----------------CONSTANTS---------------------------
#Hot water temperature constants are taken from pg B-3 of the 2016 CBECC ACM reference manual
#These constants can be changed if wanting to try different arrangements (E.g. A different water heater set temperature)
Temperature_Shower = 105 #deg F
Temperature_Bath = 105 #deg F
Temperature_Supply_WaterHeater = 115 #deg F

#%%-----------------DEFINITIONS---------------------------
def Calculate_Fraction_HotWater(Temperature_Supply_WaterHeater, Data):

#This function estimates the fraction of hot water at various fixtures using the assumptions in the 2016 version of CBECC. Page B-3

    #Hot water fractions are taken from pg B-3 of the 2016 CBECC ACM reference manual
    Fraction_HotWater_Faucet = 0.5
    Fraction_HotWater_ClothesWasher = 0.22
    Fraction_HotWater_DishWasher = 1

    Data['BooleanMask'] = Data['Fixture'] == 'FAUC' #Creates a new column named BooleanMask that is True if Fixture in that row is FAUC
    Data['Fraction Hot Water'] = Data['BooleanMask'] * Fraction_HotWater_Faucet #Sets Fraction Hot Water for the rows where BoolenaMask = True to Fraction_HotWater_Faucet
    Data['BooleanMask'] = Data['Fixture'] == 'CWSH' #Resets BooleanMask = True if Fixture in that row = CWSH
    Data['Fraction Hot Water'] = Data['Fraction Hot Water'] + Data['BooleanMask'] * Fraction_HotWater_ClothesWasher #Adds BooleanMask * Fraction_HotWater_ClothesWasher to Fraction Hot Water. The column now contains the fraction of hot water for both faucet and dish washer uses
    Data['BooleanMask'] = Data['Fixture'] == 'DWSH' #Repeates the same process for the dishwasher
    Data['Fraction Hot Water'] = Data['Fraction Hot Water'] + Data['BooleanMask'] * Fraction_HotWater_DishWasher
    Data['BooleanMask'] = Data['Fixture'] == 'BATH'
    Data['Fraction Hot Water'] = Data['Fraction Hot Water'] + Data['BooleanMask'] * (Temperature_Bath - Data['Mains Temperature (deg F)']) / (Temperature_Supply_WaterHeater  - Data['Mains Temperature (deg F)']) #Calculates the fraction of hot water in a bath based on the CBECC-Res assumed temperature for baths and the mains water temperature
    Data['BooleanMask'] = Data['Fixture'] == 'SHWR'
    Data['Fraction Hot Water'] = Data['Fraction Hot Water'] + Data['BooleanMask'] * (Temperature_Shower - Data['Mains Temperature (deg F)']) / (Temperature_Supply_WaterHeater  - Data['Mains Temperature (deg F)']) #Calculates the fraction of hot water in a shower based on the CBECC-Res assumed temperature for showers and the mains water temperature

    del Data['BooleanMask'] #Delete the BoolenaMask column because it adds no value beyond this function

    return Data

def Calculate_FlowWater_Hot(DrawProfile):
#This function calculates the flow of hot water using the provided draw profile and fraction of hot water

    DrawProfile['Hot Water Flow Rate (gpm)'] = DrawProfile['Fraction Hot Water'] * DrawProfile['Flow Rate (gpm)'] #Calculates the flow rate using the draw profile and assumed fraction of hot water
    DrawProfile['Hot Water Volume (gal)'] = DrawProfile['Hot Water Flow Rate (gpm)'] * DrawProfile['Duration (min)'] #Calculates the total flow using the flow rate and duration

    return DrawProfile

#%%-----------------LOAD WEATHER DATA---------------------------
#gather the climate zone's weaher data and create T_Mains - which only includes one temperature for each day of the year (is 365 long)
#do this for every requested climate zone

with CodeTimer('all weather data work'):
    Zones_Dict = {} #dictionary to store the T_mains data by climate zone
    for each in New_Climate_Zones:
        start_text = 'CTZ0' if len(str(each)) == 1 else 'CTZ'  #Identifying the correct file is done differently if the climate zone number is less than 10
        File_WeatherData = os.sep + start_text + str(each) + 'S13b.CSW' #Create a string stating the location of the weather file. Note the 0 following CTZ in climate zones < 10
        Path_WeatherData = Folder_WeatherData + File_WeatherData #Combine Folder and File to create a path stating the location of the weather data
        with CodeTimer('import csv weather data'):
            WeatherData = pd.read_csv(Path_WeatherData, header = 26, usecols = ['Hour','T Ground','31-day Avg lag DB']) #Read the weather data, ignoring the first 25 lines of header

        First_Hour = WeatherData[WeatherData["Hour"] == 1] #filter data to only include the fist hour of every day
        First_Hour = First_Hour.set_index([pd.Index(range(365))]) #set index as zero-based day of year
        T_Mains = 0.65 * First_Hour['T Ground'] + 0.35 * First_Hour['31-day Avg lag DB'] #Equation 10, ACM, Appendix B. Returns the mains water temperature as a function of the ground temper
        Zones_Dict[each] = T_Mains

#%%---------------------------GENERATE AND SAVE REQUESTED DRAW PROFILES---------
Data = pd.read_csv(File_Location) #Read the file to be converted
proper_order = Data.columns.to_list() #reference correct column order
for each in New_Climate_Zones: #repeat for each new zone required
    with CodeTimer('deleting data from previous'):
        del Data['Fraction Hot Water'] #we are going to recalculate this column
        del Data['Hot Water Volume (gal)'] #we are going to recalculate this column
        del Data['Hot Water Flow Rate (gpm)'] #we are going to recalculate this column
        del Data['Mains Temperature (deg F)'] #we are going to recalculate this column

    Zone_T_Mains = Zones_Dict[each] #get T_Mains Temperature data from previously created dictionary
    if len(Data) > 40000: #use swifter module to speed up coed if it's a long file, because swifter actually slows it down if it's below this threshold
        with CodeTimer('swap climate data (swifter)'):
            Data['Mains Temperature (deg F)'] = Data.swifter.apply(lambda x: Zone_T_Mains[x['Day of Year (Day)']-1], axis = 1)
    else: #do not use swifter module to speed up code if it's a short file
        with CodeTimer('swap climate data (vanilla .apply)'):
            Data['Mains Temperature (deg F)'] = Data.apply(lambda x: Zone_T_Mains[x['Day of Year (Day)']-1], axis = 1)
    #recalculate the fileds that were caluclated using the ground temperature (T_Mains):

    with CodeTimer('manipulate weather dataframe'):
        Data = Calculate_Fraction_HotWater(Temperature_Supply_WaterHeater, Data) #Calculate the fraction of hot water for each draw in the draw profile
        Data = Calculate_FlowWater_Hot(Data) #Calculate the flow of hot water for each draw in the draw profile
        #reorder
        Data = Data[proper_order]

    Output_File_Name = File.replace("CZ={}".format(ClimateZone),"CZ={}".format(each))
    with CodeTimer('csv data to file'):
        Data.to_csv(Folder_Output.replace(File, Output_File_Name), index = False)

print("time to run = {}".format(time.time() - start_time))

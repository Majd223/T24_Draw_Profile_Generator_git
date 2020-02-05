# -*- coding: utf-8 -*-
"""
Created on Tuesday January 7 9:00 AM
@author: Nathan Iltis

This script reads the provided weather files for all 16 zones in California and
consolidates them as the user sees fit. One can choses to store them in various time steps,
print them all to the same excel file, print only certain columns, etc.
"""
#%%-------------------------------IMPORT STATEMENTS--------------------------
import pandas as pd
import sys
import os

#%%------------------------------INPUTS--------------------------------------
#Folder paths - assumes the profile has been created and is in the appropriate folder
#file to convert to a new climate zone:
Folder = os.path.dirname(__file__)#The path to the folder where you have the base files for this script stored
Folder_WeatherData_Path = Folder + os.sep + 'WeatherFiles' #This states the folder that CBECC weather data files are stored in

Possible_Climate_Zones = list(range(1,17)) # list of all possible climate zones
Climate_Zones = list(range(1,17)) #specify which climate zones to convert the file to - can be a number from 1-16, must be a list

#columns to include in analysis: please just comment out columns not needed
include_columns = [
    'Month',
    'Day',
    'Hour',
    'TDV Elec',
    'TDV NatGas',
    'TDV Propane',
    'Dry Bulb',
    'Wet Bulb',
    'Dew Point',
    '31-day Avg lag DB',
    '14-day Avg lag DB',
    '7-day Avg lag DB',
    'T Ground',
    "previous day's peak DB",
    'T sky',
    'Wind direction',
    'Wind speed',
    'Global Horizontal Radiation',
    'Direct Normal Radiation',
    'Diffuse Horiz Radiation',
    'Total Sky Cover'
    ]

Folder_Output = os.path.dirname(__file__) + os.sep + 'Weather_Data_Manipulated'
Output_File_Name = 'AllZones_AllWeather.xlsx' #needs to end in .xlsx
Output_Path = Folder_Output + os.sep + Output_File_Name

#%%-----------------LOAD WEATHER DATA---------------------------
#gather the climate zone's weaher data
#do this for every requested climate zone
#this portion of the script should not change

Zones_Dict = {} #dictionary to store the T_mains data by climate zone
for each in Climate_Zones:
    start_text = 'CTZ0' if len(str(each)) == 1 else 'CTZ'  #Identifying the correct file is done differently if the climate zone number is less than 10
    frame_name = start_text + str(each)
    File_WeatherData = start_text + str(each) + 'S13b.CSW' #Create a string stating the location of the weather file. Note the 0 following CTZ in climate zones < 10
    Path_WeatherData = Folder_WeatherData_Path + os.sep + File_WeatherData #Combine Folder and File to create a path stating the location of the weather data
    WeatherData = pd.read_csv(Path_WeatherData, header = 26, usecols = include_columns) #Read the weather data, ignoring the first 25 lines of header
    # WeatherData = pd.read_csv(Path_WeatherData, header = 26)
    Zones_Dict[frame_name] = WeatherData

#%%-----------------Special Analyses---------------------------
# monthly_rolling_average_dict = {} #dictionary to store the average monthly temperatures
# # minimum_monthly_rolling_average_values_dict = {}
# #this method uses multiindices:
# for each in Zones_Dict:
#     this_frame = Zones_Dict[each].copy()
#     this_frame = this_frame.set_index(['Month','Day','Hour'])
#     this_frame.index = this_frame.index.get_level_values('Month')
#     this_frame = this_frame.groupby('Month').mean()
#     this_frame.loc[0] = this_frame.loc[this_frame.index[-1]]
#     this_frame.loc[13] = this_frame.loc[this_frame.index[0]]
#     this_frame = this_frame.sort_index()
#     this_frame = this_frame.rolling(3,center=True).mean()
#     this_frame = this_frame.drop(index = [0,13])
#     monthly_rolling_average_dict[each] = this_frame
#     # minimum = this_frame['Dry Bulb'].min()
#     # minimum_monthly_rolling_average_values_dict.

# %%-----------------WRITE TO FILE---------------------------
#print all to the same file if desired:
writer = pd.ExcelWriter(Output_Path, engine='xlsxwriter')

# for writing full data sheets
for each in Zones_Dict:
    this_frame = Zones_Dict[each].copy()
    this_frame.to_excel(writer, sheet_name = each, index = False)

# #for writing monthly average sheets
# for each in monthly_rolling_average_dict:
#     this_frame = monthly_rolling_average_dict[each].copy()
#     this_frame.to_excel(writer, sheet_name = each, index = True)

writer.save()

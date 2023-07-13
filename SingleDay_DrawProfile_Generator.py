# -*- coding: utf-8 -*-
"""
Created on Mon Oct  3 10:20:52 2022

Creates draw profiles for a single day in the T24 datset. Implements methods similar to T24_Draw_Profile_Generator.py.
See documentation in that script for more comprehensive information.

@author: Peter Grant
"""

# %%--------------------IMPORT STATEMENTS----------------

import pandas as pd
import os
import time
import ast
from T24_Draw_Profile_Generator import (
    Calculate_Fraction_HotWater,
    Calculate_FlowWater_Hot,
    Modify_Profile_SDLM,
)
from Event_To_Timestep_Converter import Convert_Profile_SingleDay


try:
    root = os.path.dirname(os.path.abspath(__file__))
except:
    root = os.getcwd()

# %%--------------------INPUTS---------------------------

Version = 2019
ClimateZone = 12
Number_Occupants = 1
Building_Type = "Single"
Include_Faucet = "Yes"
Include_Shower = "Yes"
Include_Clothes = "Yes"
Include_Dish = "Yes"
Include_Bath = "Yes"
Day_Of_Year = 200
SquareFootage_Dwelling = 1897
Water = "Hot"
Distribution_System_Type = "Trunk and Branch"


# %%-----------------CONSTANTS---------------------------

# Hot water temperature constants are taken from pg B-3 of the 2016 CBECC ACM reference manual
# These constants can be changed if wanting to try different arrangements (E.g. A different water heater set temperature)
Temperature_Shower = 105  # deg F
Temperature_Bath = 105  # deg F
Temperature_Supply_Hot_AtFixture = 115  # deg F. CSE assumes 115 deg F hot water at the fixture, per 1/28/2020 email with Aaron Boranian

# %%--------------------LOAD WEATHER DATA----------------------------------

# Read from WeatherFiles folder, depending on ClimateZone CTZ + climate zone + S13b.CSW
# Read the weather data, ignoring the first 25 lines of header
# Read 31-day avg lag DB
# take the first hour of each day 
# set index of first_hour to number of days
# calculate T_Mains using equation 10, ACM, Appendix B
def Calculate_TMains(ClimateZone):
    # Folder paths
    Folder = (
        os.path.dirname(__file__) + os.sep
    )  # The path to the folder where you have the base files for this script stored
    # Folder_Output = Folder + os.sep + 'DrawProfiles' #The output folder, where you want the draw profiles to be saved
    Folder_WeatherData = os.path.join(
        root, "WeatherFiles"
    )  # Folder + os.sep + 'WeatherFiles' #This states the folder that CBECC weather data files are stored in

    # gather the climate zone's weaher data and create T_Mains - which only includes one temperature for each day of the year (is 365 long)
    start_text = (
        "CTZ0" if len(str(ClimateZone)) == 1 else "CTZ"
    )  # Identifying the correct file is done differently if the climate zone number is less than 10
    File_WeatherData = (
        os.sep + start_text + str(ClimateZone) + "S13b.CSW"
    )  # Create a string stating the location of the weather file. Note the 0 following CTZ in climate zones < 10
    Path_WeatherData = (
        Folder_WeatherData + File_WeatherData
    )  # Combine Folder and File to create a path stating the location of the weather data

    WeatherData = pd.read_csv(
        Path_WeatherData, header=26, usecols=["Hour", "T Ground", "31-day Avg lag DB"]
    )  # Read the weather data, ignoring the first 25 lines of header

    First_Hour = WeatherData[
        WeatherData["Hour"] == 1
    ]  # Creates a data frame containing only data from the first hour of each day in the weather file
    First_Hour = First_Hour.set_index(
        [pd.Index(range(365))]
    )  # Sets the index of First_Hour to be the number of days in the year/number of entries in First_Hour

    T_Mains = (
        0.65 * First_Hour["T Ground"] + 0.35 * First_Hour["31-day Avg lag DB"]
    )  # Equation 10, ACM, Appendix B. Returns the mains water temperature as a function of the ground temper

    return T_Mains


# %%--------------------DEFINE FUNCTIONS-----------------------------------


def Create_Hot_Profiles(
    Building_Type,
    Profile_List,
    ClimateZone,
    Include_Faucet,
    Include_Shower,
    Include_Clothes,
    Include_Dish,
    Include_Bath,
    Version,
    T_Mains,
    Day_Of_Year,
    Temperature_Bath,
    Temperature_Shower,
    SquareFootage_Dwelling,
    Water,
    Distribution_System_Type,
):
    Folder = (
        os.path.dirname(__file__) + os.sep
    )  # The path to the folder where you have the base files for this script stored
    if Version == 2016:
        if Building_Type == "Single":
            Daily_Profiles = pd.read_csv(
                Folder
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DailyProfilesSF.csv"
            )  # Reads the .csv file containing information about the daily profiles used in CBECC-Res
        elif Building_Type == "Multi":
            Daily_Profiles = pd.read_csv(
                Folder
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DailyProfilesMF.csv"
            )  # Reads the .csv file containing information about the daily profiles used in CBECC-Res
    elif Version == 2019:
        Daily_Profiles = pd.read_csv(
            Folder
            + os.sep
            + "SourceData"
            + os.sep
            + str(Version)
            + os.sep
            + "DailyProfiles.csv"
        )  # Reads the .csv file containing information about the daily profiles used in CBECC-Res

    Draw_Profiles = {}

    for Day in Profile_List:
        temp = Daily_Profiles[Daily_Profiles["Day"] == Day].reset_index(drop=True)
        temp["Mains Temperature (deg F)"] = T_Mains[Day_Of_Year]
        temp["Start Time of Year (hr)"] = temp["Start time (hr)"] + (24 * Day_Of_Year)
        temp = Calculate_Fraction_HotWater(
            Temperature_Supply_Hot_AtFixture, Temperature_Bath, Temperature_Shower, temp
        )
        temp = Calculate_FlowWater_Hot(temp)
        temp = Modify_Profile_SDLM(
            temp, SquareFootage_Dwelling, Water, Distribution_System_Type
        )
        Draw_Profiles[Day] = temp

    return Draw_Profiles


# %%----------------------------------EXECUTE CODE FOR TESTING-----------------------------

if __name__ == "__main__":
    start_time = time.time()

    T_Mains = Calculate_TMains(ClimateZone)
    Binned_Profiles = pd.read_csv(
        os.path.join(os.getcwd(), "..", "hpwhs", "Profiles_Binned_ByAvgElecPerDay.csv"),
        index_col=0,
    )
    for group in Binned_Profiles.index[0:1]:
        Profile_List = ast.literal_eval(Binned_Profiles.loc[group, "Profiles"])

        Profiles = Create_Hot_Profiles(
            "Single",
            Profile_List,
            ClimateZone,
            Include_Faucet,
            Include_Shower,
            Include_Clothes,
            Include_Dish,
            Include_Bath,
            Version,
            T_Mains,
            Day_Of_Year,
            Temperature_Bath,
            Temperature_Shower,
            SquareFootage_Dwelling,
            Water,
            Distribution_System_Type,
        )
        TimestepBased = {}

        for key in Profiles.keys():
            TimestepBased[key] = Convert_Profile_SingleDay(
                Profiles[key], Day_Of_Year, 15, ClimateZone
            )

    print(time.time() - start_time)

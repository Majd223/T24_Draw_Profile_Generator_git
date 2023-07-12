# -*- coding: utf-8 -*-
"""
Created on Mon Apr 10 12:08:46 2023

@author: Peter Grant

This example shows how to create draw profiles for single dwellings. 

At this time the code only uses Title 24's CA weather data files when calculating
hot water flows. This can be updated in future versions.

"""

import os
import datetime
import pandas as pd
import numpy as np
from SingleDay_DrawProfile_Generator import Create_Hot_Profiles, Calculate_TMains
from Event_To_Timestep_Converter import Convert_Profile_SingleDay

# %%-----------------------DEFINE INPUTS------------------------------------

# Set details for draw profiles
ClimateZone = 3  # Specify the CEC climate zone used in these calculations
Include_Faucet = (
    "Yes"  # State whether ('Yes') or not ('No') to include faucets in the draw profile
)
Include_Shower = (
    "Yes"  # State whether ('Yes') or not ('No') to include showers in the draw profile
)
Include_Clothes = "Yes"  # State whether ('Yes') or not ('No') to include clothes washers in the draw profile
Include_Dish = "Yes"  # State whether ('Yes') or not ('No') to include dish washers in the draw profile
Include_Bath = (
    "Yes"  # State whether ('Yes') or not ('No') to include baths in the draw profile
)
Version = 2019  # State which version of the Title 24 draw profiels to use (2016 or 2019 at this time)
Temperature_Bath = (
    105  # State the temperature of hot water occupants use when taking baths. deg F
)
Temperature_Shower = (
    105  # State the temperature of hot water occupants use when taking showers. deg F
)
SquareFootage_Dwelling = 1897  # State the conditioned floor area of the dwelling. ft^2
Water = "Hot"  # 'Hot' water from the water heater or 'Mixed' water from the fixture
Distribution_System_Type = (
    "Trunk and Branch"  # The type of distribution system taking water to the fixtures
)
Timestep = 15  # Timestep to use when converting profiles to timestep-based. Seconds

Date = datetime.datetime(
    2022, 1, 1, 0, 0, 0
)  # The date at the start of the draw profile
Day_Of_Year = Date.timetuple().tm_yday
T_Mains = Calculate_TMains(
    ClimateZone
)  # Calcualte the inlet water temperature. Modify to enable nationwide calculations
Daily_Profiles = pd.read_csv(
    os.path.join(
        os.getcwd(),
        "..",
        "T24_Draw_Profile_Generator",
        "SourceData",
        "2019",
        "DailyProfiles.csv",
    ),
    index_col=0,
)
Profile_List = np.unique(Daily_Profiles.index)
print(Profile_List)
print("Creating profiles")
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

print("Converting profiles to timestep-based")
for key in Profiles.keys():
    Profiles[key] = Convert_Profile_SingleDay(
        Profiles[key], Day_Of_Year, Timestep, ClimateZone
    )

print("Saving draw profiles to .csv")
for key in Profiles.keys():
    Profiles[key].to_csv(
        os.path.join(os.getcwd(), "DrawProfiles", "{}.csv".format(key))
    )


# %%

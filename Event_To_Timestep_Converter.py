# -*- coding: utf-8 -*-
"""
Created on Mon Apr 11 11:51:14 2022

This script converts event-based Title 24 draw profiles to timestep-based
Title 24 draw profiles

@author: Peter Grant
"""


# %%-----------------------IMPORT STATEMENTS----------------------------

import pandas as pd
import datetime as dt
import numpy as np
import os
import sys
import glob

try:
    root = os.path.dirname(os.path.abspath(__file__))
except:
    root = os.getcwd()

sys.path.append(os.path.join(root, "..", "hpwhs", "Utilities"))
import Conversions as Conversions

# %%----------------------INPUTS----------------------------------------

SI = True  # True = outputs in SI units, False = outputs in IP units

Timestep = 15  # Desired output timestep in seconds
Start = dt.datetime(2022, 1, 1, 0, 0, 0)  # Start datetime of the draw profile
End = dt.datetime(2023, 1, 1, 0, 0, 0)  # End datetime of the draw profile

# The path to the desired T24 draw profile
Folder = os.path.join(root, "DrawProfiles")
# File = 'Bldg=Single_CZ=3_Wat=Hot_Prof=2_SDLM=Yes_CFA=1897_Inc=FSCDB_Ver=2019.csv'
Files = glob.glob(Folder + "/*.csv")

# %%----------------DEFINE CONVERSION FUNCTION------------------


def Convert_Profile_SingleDay(
    EventBased, Day_Of_Year, Timestep, ClimateZone, SI=True, interpolate=False
):
    """
    Day_Of_Year starts at 1 (e.g. Jan 1 is Day #1, not Day #0)
    """

    sys.path.append(os.path.join(root, "..", "..", "References"))

    # Read the CSE weather data
    if ClimateZone < 10:
        CZ = "0{}".format(str(ClimateZone))
    else:
        CZ = ClimateZone

    FileName = "CTZ{}S13b.CSW".format(str(CZ))

    Year = 2022
    Month = dt.datetime.strptime(str(Day_Of_Year), "%j").month
    Day = dt.datetime.strptime(str(Day_Of_Year), "%j").day
    Start = dt.datetime(Year, Month, Day, 0, 0, 0)

    End = Start + pd.Timedelta(1, unit="day")

    WeatherData = pd.read_csv(os.path.join(root, "WeatherFiles", FileName), skiprows=26)

    # Calculate the mains water temperature using CSE assumptions
    # Equation 10, ACM, Appendix B. Returns the mains water temperature as a function of the ground temperature
    WeatherData["T_Mains"] = (
        0.65 * WeatherData["T Ground"] + 0.35 * WeatherData["31-day Avg lag DB"]
    )

    # Create datetime index, interpolate to desired timestep
    WeatherData.loc[0, "Timestamp"] = dt.datetime(Start.year, 1, 1, 0)
    WeatherData.loc[1:, "Timestamp"] = WeatherData.loc[
        0, "Timestamp"
    ] + pd.to_timedelta(WeatherData.index[1:], unit="h")
    WeatherData = WeatherData.set_index("Timestamp")
    WeatherData = WeatherData.resample("{}S".format(Timestep)).interpolate(
        method="linear" if interpolate else "ffill"
    )

    TimestepBased_Index = pd.date_range(
        Start, End, freq="{}T".format(Timestep / Conversions.seconds_in_minute)
    )

    TimestepBased = pd.DataFrame(
        0,
        index=TimestepBased_Index,
        columns=["Hot Water Draw Volume (gal)", "Mains Temperature (deg F)"],
    )

    # For each draw in the T24 draw profile
    for Draw in EventBased.index:
        # Gather draw data from the event-based data set
        Start_Time = Start + pd.Timedelta(
            EventBased.loc[Draw, "Start time (hr)"], unit="h"
        )
        Duration = EventBased.loc[Draw, "Duration (min)"]
        End_Time = (
            EventBased.loc[Draw, "Start time (hr)"]
            + Duration / Conversions.minutes_in_hour
        )
        Flow_Rate = EventBased.loc[Draw, "Hot Water Flow Rate (gpm)"]

        # Identify the start/end bin and draw duration during each of those bins
        Bin_Start = int(
            np.floor(
                EventBased.loc[Draw, "Start time (hr)"]
                / (
                    Timestep
                    / (Conversions.seconds_in_minute * Conversions.minutes_in_hour)
                )
            )
        )

        Time_Start_Bin = (
            TimestepBased.index[Bin_Start + 1] - Start_Time
        ).total_seconds() / Conversions.seconds_in_minute

        Bin_End = int(
            np.floor(
                End_Time
                / (
                    Timestep
                    / (Conversions.seconds_in_minute * Conversions.minutes_in_hour)
                )
            )
        )
        End_Timestamp = Start + pd.Timedelta(End_Time, unit="h")
        Time_End_Bin = (
            End_Timestamp - TimestepBased.index[Bin_End]
        ).total_seconds() / Conversions.seconds_in_minute

        # Assign the hot water draw volume to each bin
        if Bin_End == Bin_Start:
            TimestepBased.loc[
                TimestepBased.index[Bin_Start], "Hot Water Draw Volume (gal)"
            ] += (Duration * Flow_Rate)
        else:
            TimestepBased.loc[
                TimestepBased.index[Bin_Start], "Hot Water Draw Volume (gal)"
            ] += (Time_Start_Bin * Flow_Rate)

        if Bin_End - Bin_Start >= 1:  # If the draw doesn't end during the start bin
            TimestepBased.loc[
                TimestepBased.index[Bin_End], "Hot Water Draw Volume (gal)"
            ] += (Time_End_Bin * Flow_Rate)
        if Bin_End - Bin_Start >= 2:  # If there are bins between start and end
            TimestepBased.loc[
                TimestepBased.index[Bin_Start + 1] : TimestepBased.index[Bin_End - 1],
                "Hot Water Draw Volume (gal)",
            ] += Flow_Rate * (Timestep / Conversions.seconds_in_minute)

    # Add mains temperature data to the output
    TimestepBased["Mains Temperature (deg F)"] = WeatherData["T_Mains"]
    TimestepBased["Mains Temperature (deg F)"] = TimestepBased[
        "Mains Temperature (deg F)"
    ].ffill()

    # Add outdoor temperature data to the output
    TimestepBased["Outdoor Temperature (deg F)"] = WeatherData["Dry Bulb"]
    TimestepBased["Outdoor Temperature (deg F)"] = TimestepBased[
        "Outdoor Temperature (deg F)"
    ].ffill()

    # Add timestep data to the output
    TimestepBased["Timestep (min)"] = Timestep / Conversions.seconds_in_minute

    # Convert to SI units
    if SI == True:
        TimestepBased["Hot Water Draw Volume (gal)"] = (
            TimestepBased["Hot Water Draw Volume (gal)"] * Conversions.L_in_gal
        )
        TimestepBased["Mains Temperature (deg F)"] = (
            TimestepBased["Mains Temperature (deg F)"] - 32
        ) / 1.8
        TimestepBased["Outdoor Temperature (deg F)"] = (
            TimestepBased["Outdoor Temperature (deg F)"] - 32
        ) / 1.8
        TimestepBased = TimestepBased.rename(
            columns={
                "Hot Water Draw Volume (gal)": "Hot Water Draw Volume (L)",
                "Mains Temperature (deg F)": "Mains Temperature (deg C)",
                "Outdoor Temperature (deg F)": "Outdoor Temperature (deg C)",
            }
        )

    return TimestepBased


# %%----------------CONVERT PROFILES--------------------

if __name__ == "__main__":
    for File in Files:
        # Read the climate zone from the draw profile
        ClimateZone = File.split("CZ=")[-1].split("_")[0]

        # State the output folder
        Output_Folder = os.path.join(root, "DrawProfiles", "Timestep_Based")

        # %%---------------------READ WEATHER DATA----------------------------------

        # Read the CSE weather data
        if len(ClimateZone) < 2:
            CZ = "0{}".format(ClimateZone)
        else:
            CZ = ClimateZone

        FileName = "CTZ{}S13b.CSW".format(CZ)

        WeatherData = pd.read_csv(
            os.path.join(root, "WeatherFiles", FileName), skiprows=26
        )

        # Calculate the mains water temperature using CSE assumptions
        # Equation 10, ACM, Appendix B. Returns the mains water temperature as a function of the ground temperature
        WeatherData["T_Mains"] = (
            0.65 * WeatherData["T Ground"] + 0.35 * WeatherData["31-day Avg lag DB"]
        )

        # Create datetime index, interpolate to desired timestep
        WeatherData.loc[0, "Timestamp"] = dt.datetime(Start.year, 1, 1, 0)
        WeatherData.loc[1:, "Timestamp"] = WeatherData.loc[
            0, "Timestamp"
        ] + pd.to_timedelta(WeatherData.index[1:], unit="h")
        WeatherData.index = WeatherData["Timestamp"]
        WeatherData = WeatherData.resample("{}S".format(Timestep)).interpolate(
            method="ffill"
        )

        # %%------------------DECLARE CONSTANTS------------------------------------

        # Read the event-based T24 darw profile
        Path = os.path.join(Folder, File)
        EventBased = pd.read_csv(Path)

        # Create the timestep-based dataframe with the desired index
        TimestepBased_Index = pd.date_range(
            Start, End, freq="{}T".format(Timestep / Conversions.seconds_in_minute)
        )
        TimestepBased = pd.DataFrame(
            0,
            index=TimestepBased_Index,
            columns=["Hot Water Draw Volume (gal)", "Mains Temperature (deg F)"],
        )

        # For each draw in the T24 draw profile
        for Draw in EventBased.index:
            # Gather draw data from the event-based data set
            Start_Time = Start + pd.Timedelta(
                EventBased.loc[Draw, "Start Time of Year (hr)"], unit="h"
            )
            Duration = EventBased.loc[Draw, "Duration (min)"]
            End_Time = (
                EventBased.loc[Draw, "Start Time of Year (hr)"]
                + Duration / Conversions.minutes_in_hour
            )
            Flow_Rate = EventBased.loc[Draw, "Hot Water Flow Rate (gpm)"]

            # Identify the start/end bin and draw duration during each of those bins
            Bin_Start = int(
                np.floor(
                    EventBased.loc[Draw, "Start Time of Year (hr)"]
                    / (
                        Timestep
                        / (Conversions.seconds_in_minute * Conversions.minutes_in_hour)
                    )
                )
            )
            Time_Start_Bin = (
                TimestepBased.index[Bin_Start + 1] - Start_Time
            ).total_seconds() / Conversions.seconds_in_minute

            Bin_End = int(
                np.floor(
                    End_Time
                    / (
                        Timestep
                        / (Conversions.seconds_in_minute * Conversions.minutes_in_hour)
                    )
                )
            )
            End_Timestamp = Start + pd.Timedelta(End_Time, unit="h")
            Time_End_Bin = (
                End_Timestamp - TimestepBased.index[Bin_End]
            ).total_seconds() / Conversions.seconds_in_minute

            # Assign the hot water draw volume to each bin
            if Bin_End == Bin_Start:
                TimestepBased.loc[
                    TimestepBased.index[Bin_Start], "Hot Water Draw Volume (gal)"
                ] += (Duration * Flow_Rate)
            else:
                TimestepBased.loc[
                    TimestepBased.index[Bin_Start], "Hot Water Draw Volume (gal)"
                ] += (Time_Start_Bin * Flow_Rate)

            if Bin_End - Bin_Start >= 1:  # If the draw doesn't end during the start bin
                TimestepBased.loc[
                    TimestepBased.index[Bin_End], "Hot Water Draw Volume (gal)"
                ] += (Time_End_Bin * Flow_Rate)
            if Bin_End - Bin_Start >= 2:  # If there are bins between start and end
                TimestepBased.loc[
                    TimestepBased.index[Bin_Start + 1] : TimestepBased.index[
                        Bin_End - 1
                    ],
                    "Hot Water Draw Volume (gal)",
                ] += Flow_Rate * (Timestep / Conversions.seconds_in_minute)

        # Add mains temperature data to the output
        TimestepBased["Mains Temperature (deg F)"] = WeatherData["T_Mains"]
        TimestepBased["Mains Temperature (deg F)"] = TimestepBased[
            "Mains Temperature (deg F)"
        ].ffill()

        # Add outdoor temperature data to the output
        TimestepBased["Outdoor Temperature (deg F)"] = WeatherData["Dry Bulb"]
        TimestepBased["Outdoor Temperature (deg F)"] = TimestepBased[
            "Outdoor Temperature (deg F)"
        ].ffill()

        # Add timestep data to the output
        TimestepBased["Timestep (min)"] = Timestep / Conversions.seconds_in_minute

        # Convert to SI units
        if SI == True:
            TimestepBased["Hot Water Draw Volume (gal)"] = (
                TimestepBased["Hot Water Draw Volume (gal)"] * Conversions.L_in_gal
            )
            TimestepBased["Mains Temperature (deg F)"] = (
                TimestepBased["Mains Temperature (deg F)"] - 32
            ) / 1.8
            TimestepBased["Outdoor Temperature (deg F)"] = (
                TimestepBased["Outdoor Temperature (deg F)"] - 32
            ) / 1.8
            TimestepBased = TimestepBased.rename(
                columns={
                    "Hot Water Draw Volume (gal)": "Hot Water Draw Volume (L)",
                    "Mains Temperature (deg F)": "Mains Temperature (deg C)",
                    "Outdoor Temperature (deg F)": "Outdoor Temperature (deg C)",
                }
            )

        # Gather specifics about the event-based draw profile, create output filename
        Bldg = File.split("=")[1].split("_")[0][0]
        Wat = File.split("=")[3].split("_")[0]
        Prof = File.split("=")[4].split("_")[0]
        SDLM = File.split("=")[5].split("_")[0]
        CFA = File.split("=")[6].split("_")[0]
        Inc = File.split("=")[7].split("_")[0]
        Ver = File.split("=")[8].split(".")[0]

        if SI == True:
            Output_File = (
                Bldg
                + "_"
                + CZ
                + "_"
                + Wat
                + "_"
                + Prof
                + "_"
                + SDLM
                + "_"
                + CFA
                + "_"
                + Inc
                + "_"
                + Ver
                + "_SI.csv"
            )
        else:
            Output_File = (
                Bldg
                + "_"
                + CZ
                + "_"
                + Wat
                + "_"
                + Prof
                + "_"
                + SDLM
                + "_"
                + CFA
                + "_"
                + Inc
                + "_"
                + Ver
                + ".csv"
            )

        TimestepBased.to_csv(os.path.join(Output_Folder, Output_File))

        print("Finished: {}".format(Output_File))

# -*- coding: utf-8 -*-
"""
Created on Thu Jun 23 12:55:47 2016

This script reads draw profile base data provided as a .txt by the Wilcox team, parses it, and saves it as .csv files
The .csv files are more human friendly, and can be used to analyze different technologies

It works for both SF and MF, with both 2016 and 2019 versions. The code was developed for the 2019 version,
and there are LIKELY TO STILL BE SOME BUGS IN THE 2016 VERSION. The 2016 version has not been used or tested
for SF homes, so expect to need to update the Headers in the Flags section

@author: pgrant
"""

# %%--------------------FLAGS----------------

Create_Annual_Profiles = 1
Create_Daily_Profiles = 0
Building_Type = "Single"
Version = 2016

if Building_Type == "Single":
    Building = "SF"
    Row_Header_Annual_2016 = 12
    Row_Header_Daily_2016 = 104
    Row_Header_Annual_2019 = 47
    Row_Header_Daily_2019 = 859
elif Building_Type == "Multi":
    Building = "MF"
    Row_Header_Annual_2016 = 12
    Row_Header_Daily_2016 = 404
    Row_Header_Annual_2019 = 47
    Row_Header_Daily_2019 = 859
else:
    print("Builting_Type not recognized. Either 'Single' or 'Multi")

# %%-------------------IMPORT---------------

import pandas as pd
import os

# %%---------------CREATE ANNUAL PROFILES-----------------

if Create_Annual_Profiles == 1:
    if Version == 2016:
        if Building_Type == "Multi":
            Raw_Data = pd.read_table(
                os.path.dirname(__file__)
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DHWDUMF.txt",
                header=Row_Header_Annual_2016,
            )
        elif Building_Type == "Single":
            Raw_Data = pd.read_table(
                os.path.dirname(__file__)
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DHWDUSF.txt",
                header=Row_Header_Annual_2016,
            )
    elif Version == 2019:
        Raw_Data = pd.read_table(
            os.path.dirname(__file__)
            + os.sep
            + "SourceData"
            + os.sep
            + str(Version)
            + os.sep
            + "DHWDU.txt",
            header=Row_Header_Annual_2019,
        )

    Pattern_Draw = []
    Row_Data = []
    Name_Column = ""

    if Version == 2016:
        if Building == "SF":
            Range = range(0, 62)
        elif Building == "MF":
            Range = range(0, 360)
    elif Version == 2019:
        if Building == "SF":
            Range = range(2, 62)
        elif Building == "MF":
            Range = range(62, 782)

    for i in Range:
        if Version == 2016:
            Row = (
                Raw_Data.loc[i, "//365 day DHW Profile by number of Bedrooms"]
                .replace('"', "")
                .replace(")", "")
            )
        elif Version == 2019:
            Row = (
                Raw_Data.loc[
                    i,
                    "////////////////////////////////////////////////////////////////////////////////",
                ]
                .replace('"', "")
                .replace(")", "")
            )

        if Row[8:11] == "DHW":
            if (
                Name_Column == "DHW1BR"
                and Building == "SF"
                or Name_Column == "DHW0BRa"
                and Building == "MF"
            ):
                Annual_Profile = pd.DataFrame(index=range(len(Pattern_Draw)))
                Annual_Profile[Name_Column] = Pattern_Draw
            elif Name_Column != "":
                Annual_Profile[Name_Column] = Pattern_Draw
            if Building == "SF":
                Name_Column = Row[8:14]
            else:
                Name_Column = Row[8:15]
            Pattern_Draw = []
            Row_Data = Row.split(",")[1:25]
            for j in Row_Data:
                Pattern_Draw.append(j)
        elif Row == "///////////////////////////////////////////////////////////////":
            break
        else:
            Row_Data = Row.split(",")[0:31]
            for j in Row_Data:
                Pattern_Draw.append(j)

    #    if Name_Column != "":
    #        Annual_Profile[Name_Column] = Pattern_Draw[0] + Pattern_Draw[1] + Pattern_Draw[2] + Pattern_Draw[3] + Pattern_Draw[4] + Pattern_Draw[5] + Pattern_Draw[6] + Pattern_Draw[7] + Pattern_Draw[8] + Pattern_Draw[9] + Pattern_Draw[10] + Pattern_Draw[11]

    Annual_Profile[Name_Column] = Pattern_Draw

##%%--------------------CREATE DAILY PROFILES-----------------------

if Create_Daily_Profiles == 1:
    Daily_Profiles = pd.DataFrame(
        columns=[
            "Day",
            "Fixture",
            "Start time (hr)",
            "Duration (min)",
            "Flow Rate (gpm)",
        ]
    )
    Day = []
    Fixture = []
    StartTime_Event = []
    Duration_Event = []
    FlowRate_Event = []

    if Version == 2016:
        if Building_Type == "Multi":
            Raw_Data = pd.read_table(
                os.path.dirname(__file__)
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DHWDUMF.txt",
                header=Row_Header_Daily_2016,
            )
        elif Building_Type == "Single":
            Raw_Data = pd.read_table(
                os.path.dirname(__file__)
                + os.sep
                + "SourceData"
                + os.sep
                + str(Version)
                + os.sep
                + "DHWDUSF.txt",
                header=Row_Header_Daily_2016,
            )
    elif Version == 2019:
        Raw_Data = pd.read_table(
            os.path.dirname(__file__)
            + os.sep
            + "SourceData"
            + os.sep
            + str(Version)
            + os.sep
            + "DHWDU.txt",
            header=Row_Header_Daily_2019,
        )

    #    Raw_Data = pd.read_table(r'C:\Users\Peter Grant\Documents\Python Scripts\Hot Water Draw Profiles\CBECC-Res\DHWDU.txt', header = Row_Header_Daily)

    for i in range(len(Raw_Data)):
        Row = Raw_Data.loc[
            i,
            "//=============================================================================================",
        ]
        if Row[0:9] == "DHWDAYUSE":
            Day_Event = Row[11:14]
        elif Row[0] == " ":
            Row_Data = (
                Row[2:-1]
                .replace("(", ",")
                .replace(")", ",")
                .replace(" ", "")
                .split(",")
            )
            Number_Draws = int(len(Row_Data) / 5)
            for j in range(Number_Draws):
                Day.append(Day_Event)
                Fixture.append(Row_Data[5 * j])
                StartTime_Event.append(Row_Data[5 * j + 1])
                Duration_Event.append(Row_Data[5 * j + 2])
                FlowRate_Event.append(Row_Data[5 * j + 3])

    Daily_Profiles["Day"] = Day
    Daily_Profiles["Fixture"] = Fixture
    Daily_Profiles["Start time (hr)"] = StartTime_Event
    Daily_Profiles["Duration (min)"] = Duration_Event
    Daily_Profiles["Flow Rate (gpm)"] = FlowRate_Event


# %%----------------SAVE DATA-------------------

if Create_Annual_Profiles == 1:
    Annual_Profile.to_csv(
        os.path.dirname(__file__)
        + os.sep
        + "SourceData"
        + os.sep
        + str(Version)
        + os.sep
        + "AnnualProfile"
        + Building
        + ".csv",
        index=False,
    )
    print(
        os.path.dirname(__file__)
        + os.sep
        + "SourceData"
        + os.sep
        + str(Version)
        + os.sep
        + "AnnualProfile"
        + Building
        + ".csv"
    )

if Create_Daily_Profiles == 1:
    if Version == 2016:
        Daily_Profiles.to_csv(
            os.path.dirname(__file__)
            + os.sep
            + "SourceData"
            + os.sep
            + str(Version)
            + os.sep
            + "DailyProfiles"
            + Building
            + ".csv",
            index=False,
        )
    elif Version == 2019:
        Daily_Profiles.to_csv(
            os.path.dirname(__file__)
            + os.sep
            + "SourceData"
            + os.sep
            + str(Version)
            + os.sep
            + "DailyProfiles.csv",
            index=False,
        )

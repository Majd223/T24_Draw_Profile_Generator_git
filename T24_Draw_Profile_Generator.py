# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 10:52:11 2019

This script recreates the T24 hot water draw profiles for residential buildings. It aims to give the user the ability to generate draw profiles for any combination
of the following:   
    -Single or multi-family buildings
    -Individual dwelling units (E.g. One house or one apartment) or groups of dwelling (E.g. a SF house neighborhood, or an apartment building)
    -Profiles including or excluding the Standard Distribution Loss Multiplier
    -Either the hot water profile leaving the water heater or the mixed water leaving the fixture
    -The various climate zones around California
    -A user selected array of fixtures (So long as those fixtures are represented in the T24 draw profiles)

The various options in the INPUTS section are thoroughly documented, informing the user of how to set up the script to change the profiles and outputs.

The scripts are assembled using the information presented in DHWDU.txt. That information essentially consists of tables that 1) Present a list of individual days
    for each type of dwelling and b) Present detailed draw profiles for those individual days. For instance (Not an actual example, merely a description of the
    concepts): A draw profiles might have '1H1' set for Jan 1, '1D2' for Jan 2, and '3D1' for Jan 3. The script will look up daily draw profile '1H1', paste it into
    the annual draw profile, then find the draw profile for '1D2' and paste that into the file, then do the same for '3D1'. In this way it builds annual profiles one
    day at a time by appending each day to the profile.

The script uses a number of different functions to accomplish its flexible goals. They are as follows:
    -Create_Mixed_Profile_NoSDLM - This is a pretty clearly named script. It creates a draw profile showing the mixed water flow rate in the draw profile, and does
        not include the Standard Distribution Loss Multiplier
    -Create_Hot_Profile_NoSDLM - This is another pretty clearly named script. It does the same thing, but creates a hot water draw profile instead of mixed water
    -Modify_Profile_SDLM - This script takes a draw profile, either mixed or hot, calcualtes the SDLM for the dwelling in question, and modifies the flow rate
        of the profile accordingly. It return a new draw profile that include SDLM.
    -Read_TMains - This is a supporting function, used in creating a hot water draw profile. It reads the mains water temperature so that Create_Hot_Profile_NoSDLM
        can perform an energy balance and the fixture, identify the ratio of hot and cold water, and return the hot water flow information
    -Calculate_Fraction_Hot_Water - This is another supporting function. It takes the draw information from a mixed water profile, the hot water temperature, and the
        mains water temperature from Read_TMains then calculates the fraction of water at the fixture that is hot water. This is then added as a new column in the draw
        profile so Create_Hot_Profile_NoSDLM can work it's magic
    -Calculate_FlowWater_Hot - Another support function. This one calculates the hot water flow rate and volume using the provided profile and hot water fraction
    -Combine_Profiles - This is a very long and complex function. Reading the comments and documentation included in the function itself is strongly recommended.
        It combines profiles from multiple dwellings into a single profile by: 1) Concatenating all of the data frames into a single data frame, 2) Sorting the data
        frame by the start time (Out of 8760 hours in a year) so that all draws are ordered sequentially, 3) Checking the start/end times of each draw and combining
        draws that overlap as needed.
    -Filter_DataSet_ByFixture - This function will include or remove fixtures from the profile as desired, and as specified by the user. For instance, a user could
        desire a draw profile that only includes showers. Or both showers and dishwashers. Or all of the fixtures.
    -Determine_Next_Change - This supports the Combine_Profiles function. It is called when overlapping draws are identified, and looks to identify the next change.
        It could identify that the next change in the draw profile is either a new draw beginning, or that a currently active draw is ending.
    -New_Draw_Beginning - This is another support function for Combine_Profiles. It modifies the draw profile as needed when another active draw begins before any
        currently active draw ends
    -Active_Draw_Ending - This is another support function for Combine_Profiles. It modifies the draw profile as needed when a currently active draw ends before the
        the next draw begins

Known issues with this script:
    -There are still some issues with Combine_Profiles when many different draws start/end around the same time. Especially when several all start at the exact same
        time with some ending before others. This can cause issues with calculated flow rates and durations, and results in errors in flow volumes. Watch out for this
        issue when creating profiles with many dwelling units. Profiles with faucets (Many draws) and clotheswashers (Repeated short draws in a short period of time)
        are also susceptible. Some manual manipulation of draw profiles may be necessary. Look for draws where the volume of the draw is 0 gal
    -Create_Hot_Profile_NoSDLM and Combine_Profiles can get SSSSLLLOOOOWWW. In the case of Create_Hot_Profile_NoSDLM this is believed to be because the mains inlet
        temperature is not being identified and copied in using the most efficient method. Combine_Profiles gets slow because it's iterating through each line of a draw
        profile, potentially hundreds of thousands of lines. When creating large, hot profiles plan on running it overnight. I'm not sure of what potential solutions
        could be better

@author: Peter Grant
"""

#%%-------------------------------IMPORT STATEMENTS--------------------------

import pandas as pd
import sys
import os
import time
from bokeh.plotting import figure, save, gridplot, output_file


#%%------------------------------TIMER--------------------------------------
start_time = time.time() # mark the beginning of the execution time for reference back to later
end_laggard_hot, start_laggard_hot, end_laggard_mixed, start_laggard_mixed = 0, 0, 0, 0
#%%------------------------------INPUTS--------------------------------------

#Describe the building. All lists describing the building need to be the same length for this script to work correctly

Building_Type = 'Single' #Either 'Single' for a single family or 'Multi' for a multi-family building
SDLM = 'No' #Either 'Yes' or 'No'. This flag determines whether or not the tool adds SDLM into the water flow calculations
Water = 'Mixed' #Either 'Mixed' or 'Hot'. Use 'Mixed' to retrieve the water exiting the fixture, having mixed both hot and cold streams. Use 'Hot' to retrieve only the hot water flow
NumberBedrooms_Dwellings = [1] #The number of bedrooms in each dwelling. Is a list because multi-family buildings need multiple specifications
SquareFootage_Dwellings = [750] #The square footage of each dwelling in the building. Is a list because multi-family buildings need multiple specifications
ClimateZone = 3 #The CA climate zone used in the simulation. This must be entered as an integer (Not a string), and there must be an available weather data file for this climate zone in C:\Users\Peter Grant\Dropbox (Beyond Efficiency)\Peter\Python Scripts\Hot Water Draw Profiles\CBECC-Res\WeatherFiles

#Describe the final profile format

Combined = 'No' #Either 'Yes' or 'No'. If 'No', will print one file for each dwelling in the lists. If 'Yes', will combine the profiles for all dwellings into a single file
Combined_LargeBuilding = 'No' #Either 'Yes' or 'No'. The script for combining profiles can be slow, take a long time to run. This function provides a less precise, faster version
Include_Faucet = 'Yes' #Either 'Yes' or 'No'. If 'Yes', entries to these fixtures will be included in the final draw profile. If 'No', they will be removed from the data set
Include_Shower = 'No' #Either 'Yes' or 'No'. If 'Yes', entries to these fixtures will be included in the final draw profile. If 'No', they will be removed from the data set
Include_Clothes = 'No' #Either 'Yes' or 'No'. If 'Yes', entries to these fixtures will be included in the final draw profile. If 'No', they will be removed from the data set
Include_Dish = 'Yes' #Either 'Yes' or 'No'. If 'Yes', entries to these fixtures will be included in the final draw profile. If 'No', they will be removed from the data set
Include_Bath = 'No' #Either 'Yes' or 'No'. If 'Yes', entries to these fixtures will be included in the final draw profile. If 'No', they will be removed from the data set

#Folder paths
Folder = os.path.dirname(__file__) + os.sep #The path to the folder where you have the base files for this script stored
Folder_Output = Folder + os.sep + 'DrawProfiles' #The output folder, where you want the draw profiles to be saved
Folder_WeatherData = Folder + os.sep + 'WeatherFiles' #This states the folder that CBECC weather data files are stored in

#%%-----------------CONSTANTS---------------------------

#Hot water temperature constants are taken from pg B-3 of the 2016 CBECC ACM reference manual
#These constants can be changed if wanting to try different arrangements (E.g. A different water heater set temperature)
Temperature_Shower = 105 #deg F
Temperature_Bath = 105 #deg F
Temperature_Supply_WaterHeater = 115 #deg F

#%%-----------------LOAD WEATHER DATA---------------------------
#gather the climate zone's weaher data and create T_Mains - which only includes one temperature for each day of the year (is 365 long)
start_text = 'CTZ0' if len(str(ClimateZone)) == 1 else 'CTZ'  #Identifying the correct file is done differently if the climate zone number is less than 10
File_WeatherData = os.sep + start_text + str(ClimateZone) + 'S13b.CSW' #Create a string stating the location of the weather file. Note the 0 following CTZ in climate zones < 10
Path_WeatherData = Folder_WeatherData + File_WeatherData #Combine Folder and File to create a path stating the location of the weather data

WeatherData = pd.read_csv(Path_WeatherData, header = 26) #Read the weather data, ignoring the first 25 lines of header

First_Hour = WeatherData[WeatherData["Hour"] == 1] #Creates a data frame containing only data from the first hour of each day in the weather file
First_Hour = First_Hour.set_index([pd.Index(range(365))]) #Sets the index of First_Hour to be the number of days in the year/number of entries in First_Hour
T_Mains = 0.65 * First_Hour['T Ground'] + 0.35 * First_Hour['31-day Avg lag DB'] #Equation 10, ACM, Appendix B. Returns the mains water temperature as a function of the ground temper

#%%-----------------------------ERROR CHECKING-------------------------------

#If the user has entered a Building_Type that does not exist
if Building_Type != 'Single' and Building_Type != 'Multi':
    print('Building_Type must be either "Single" or "Multi"') #Return an error
    sys.exit() #And exit the program

#If the user has entered an invalid number of bedrooms
if Building_Type == 'Single' and min(NumberBedrooms_Dwellings) < 1 or max(NumberBedrooms_Dwellings) > 5:
    print('Each NumberBedrooms_Dwellings entry must be >= 1 if single family, <= 5 regardless of building type.') #Return an error
    sys.exit() #And exit the program

if SDLM != 'Yes' and SDLM != 'No':
    print("SDLM must be either 'Yes' or 'No' #Return an error
    sys.exit() #And exit the program

if len(NumberBedrooms_Dwellings) != len(SquareFootage_Dwellings): #If the lists for number of bedrooms in each dwelling and square footage of each dwelling don't match
    print('NumberBedrooms_Dwellings and SquareFootage_Dwellings must have the same number of entries') #Print an error message
    sys.exit() #Exit the program

#%%----------------------------FUNCTION DECLARATIONS-------------------------

#This function creates the mixed hot water draw profile for a single dwelling
def Create_Mixed_Profile_NoSDLM(Building_Type, NumberBedrooms_Dwelling, Variant, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath): #It needs the type of building, number of bedrooms in the dwelling, and current variant of the building as inputs

    Daily_Profiles = pd.read_csv(Folder + os.sep + 'DailyProfiles.csv') #Reads the .csv file containing information about the daily profiles used in CBECC-Res

    if Building_Type == 'Single': #If simulating a single family building
        Annual_Profiles = pd.read_csv(Folder + os.sep + 'AnnualProfileSF.csv') #Open the file containing annual profile information for single family buildings

        Profile = 'DHW' + str(NumberBedrooms_Dwelling) + 'BR' #Create a string stating the name of the annual profile used in CBECC-Res. This is done by adding 'DHW' before the number of bedrooms and 'BR' after
        Annual_Profile = Annual_Profiles[Profile] #Filter the Annuak_Profiles data frame to only show data from this building draw profile

        Dwelling_Profile = pd.DataFrame(columns = ['Day', 'Fixture', 'Start time (hr)', 'Duration (min)', 'Flow Rate (gpm)']) #Create a new data frame representing the draw profile data for this dwelling

        start_laggard_mixed = time.time() #testing runtime
        for i in range(len(Annual_Profile)): #Perform this process for each row in Annual_Profile. Each row corresponds to a single day of the year
            Daily_Profile = Daily_Profiles[Daily_Profiles['Day'] == Annual_Profile[i]].copy() #Create a dataframe containing only data from the current day in the annual profile
            Daily_Profile['Mains Temperature (deg F)'] = T_Mains[i] #Calculate mains water temperature forthe active day, add a new column expressing it to Daily_Profile. THIS LINE CAUSES THE SCRIPT TO RUN SLOWLY, CAUSED BY REFERENCING [24 * i]. THIS .loc METHOD WAS SUPPOSED TO SOLVE THAT BUT DIDN'T. NEED TO FIND A BETTER SOLUTION.
            Daily_Profile['Start Time of Year (hr)'] = Daily_Profile['Start time (hr)'] + (24 * i) #Create a new column that states the time of year, relative to midnight on Jan 1, that this draw starts. This is needed for the Combiner function
            Daily_Profile['Day of Year (Day)'] = i + 1 #Add a new column stating the day of the year that this profile is representing
            Dwelling_Profile = Dwelling_Profile.append(Daily_Profile) #Add the data from Daily_Profiles corresponding to the current day in Annual_Profile (Represented by i) to Dwelling_Profile. This leads to Dwelling_Profile containing all draw data for that dwelling by adding the daily profiles from each day
        end_laggard_mixed = time.time() #testing runtime

        Dwelling_Profile = Dwelling_Profile.reset_index() #After appending data into Dwelling_Profile, the index of the data frame will be all janky. These two lines fix it
        del Dwelling_Profile['index']

    else: #If Building_Type is not 'Single', it must be 'Multi'. This code creates a profile for a dwelling in a multi-family building
        Annual_Profiles = pd.read_csv(Folder + os.sep + 'AnnualProfileMF.csv') #Read the annual profiles for multi-family buildings

        Profile = 'DHW' + str(NumberBedrooms_Dwelling) + 'BR' + str(Variant) #Create a string storing the name of the draw profile by appending 'DHW' to the start of the draw profile and 'BR' to the end
        Annual_Profile = Annual_Profiles[Profile] #Filter Annual_Profile to only contain data for the desired profile

        Dwelling_Profile = pd.DataFrame(columns = ['Day', 'Fixture', 'Start time (hr)', 'Duration (min)', 'Flow Rate (gpm)']) #Create a blank data frame to store the draw profile for this dwelling

        start_laggard_mixed = time.time()
        for i in range(len(Annual_Profile)): #For each row in Annual_Profile (Remember that each row respresents a day)
            Daily_Profile = Daily_Profiles[Daily_Profiles['Day'] == Annual_Profile[i]].copy() #Create a dataframe containing only data from the current day in the annual profile
            Daily_Profile['Mains Temperature (deg F)'] = T_Mains[i] #Calculate mains water temperature forthe active day, add a new column expressing it to Daily_Profile. THIS LINE CAUSES THE SCRIPT TO RUN SLOWLY, CAUSED BY REFERENCING [24 * i]. THIS .loc METHOD WAS SUPPOSED TO SOLVE THAT BUT DIDN'T. NEED TO FIND A BETTER SOLUTION.
            Daily_Profile['Start Time of Year (hr)'] = Daily_Profile['Start time (hr)'] + (24 * i) #Create a new column that states the time of year, relative to midnight on Jan 1, that this draw starts. This is needed for the Combiner function
            Daily_Profile['Day of Year (Day)'] = i + 1 #Add a new column stating the day of the year that this profile is representing
            Dwelling_Profile = Dwelling_Profile.append(Daily_Profile) #Append the profile for this day into the annual profile for the dwelling
        end_laggard_mixed = time.time()

        Dwelling_Profile = Dwelling_Profile.reset_index() #After appending the index will be messed up. These two lines fix that
        del Dwelling_Profile['index']

    if Include_Faucet == 'No' or Include_Shower == 'No' or Include_Clothes == 'No' or Include_Dish == 'No' or Include_Bath == 'No': #Unless the user said they do not want to filter draws by fixture
        Dwelling_Profile, Included_Code = Filter_DataSet_ByFixture(Dwelling_Profile, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath) #Call the Filter_DataSet_ByFixture function to limit the resulting profile to only contain draws that match the specified filter
    else: #If everything is included
        Included_Code = ['F','S','C','D','B'] #Use Included_Code to show that all are included, don't filter data set

    Dwelling_Profile = Dwelling_Profile.sort_values(['Start Time of Year (hr)']) #Sorts the draws in chronological order

    return Dwelling_Profile, Included_Code #Return the Dwelling_Profile data frame and the list of profiles when this function is finished

def Create_Hot_Profile_NoSDLM(Building_Type, NumberBedrooms_Dwelling, Variant, ClimateZone, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath): #It needs the type of building, number of bedrooms in the dwelling, and current variant of the building as inputs

    Daily_Profiles = pd.read_csv(Folder + os.sep + 'DailyProfiles.csv') #Reads the .csv file containing information about the daily profiles used in CBECC-Res

    if Building_Type == 'Single': #If simulating a single family building
        Annual_Profiles = pd.read_csv(Folder + os.sep + 'AnnualProfileSF.csv') #Open the file containing annual profile information for single family buildings

        Profile = 'DHW' + str(NumberBedrooms_Dwelling) + 'BR' #Create a string stating the name of the annual profile used in CBECC-Res. This is done by adding 'DHW' before the number of bedrooms and 'BR' after
        Annual_Profile = Annual_Profiles[Profile] #Filter the Annuak_Profiles data frame to only show data from this building draw profile

        Dwelling_Profile = pd.DataFrame(columns = ['Day', 'Fixture', 'Start time (hr)', 'Duration (min)', 'Flow Rate (gpm)']) #Create a new data frame representing the draw profile data for this dwelling

        start_laggard_hot = time.time()
        for i in range(len(Annual_Profile)): #Perform this process for each row in Annual_Profile. Each row corresponds to a single day of the year
            Daily_Profile = Daily_Profiles[Daily_Profiles['Day'] == Annual_Profile[i]].copy() #Create a data frame containing the draw profile for the current day
            Daily_Profile['Mains Temperature (deg F)'] = T_Mains[i] #Calculate mains water temperature forthe active day, add a new column expressing it to Daily_Profile. THIS LINE CAUSES THE SCRIPT TO RUN SLOWLY, CAUSED BY REFERENCING [24 * i]. THIS .loc METHOD WAS SUPPOSED TO SOLVE THAT BUT DIDN'T. NEED TO FIND A BETTER SOLUTION.
            Daily_Profile['Start Time of Year (hr)'] = Daily_Profile['Start time (hr)'] + (24 * i) #Create a new column that states the time of year, relative to midnight on Jan 1, that this draw starts. This is needed for the Combiner function
            Daily_Profile['Day of Year (Day)'] = i + 1 #Add a new column stating the day of the year that this profile is representing
            Dwelling_Profile = Dwelling_Profile.append(Daily_Profile) #Append the profile for the current day to the data frame for the annual draw profile
        end_laggard_hot = time.time()

        Dwelling_Profile = Calculate_Fraction_HotWater(Temperature_Supply_WaterHeater, Dwelling_Profile) #Calculate the fraction of hot water for each draw in the draw profile
        Dwelling_Profile = Calculate_FlowWater_Hot(Dwelling_Profile) #Calculate the flow of hot water for each draw in the draw profile

        Dwelling_Profile = Dwelling_Profile.reset_index() #After appending data into Dwelling_Profile, the index of the data frame will be all janky. These two lines fix it
        del Dwelling_Profile['index']

    else: #If Building_Type is not 'Single', it must be 'Multi'. This code creates a profile for a dwelling in a multi-family building
        Annual_Profiles = pd.read_csv(Folder + os.sep + 'AnnualProfileMF.csv') #Read the annual profiles for multi-family buildings

        Profile = 'DHW' + str(NumberBedrooms_Dwelling) + 'BR' + str(Variant) #Create a string storing the name of the draw profile by appending 'DHW' to the start of the draw profile and 'BR' to the end
        Annual_Profile = Annual_Profiles[Profile] #Filter Annual_Profile to only contain data for the desired profile

        Dwelling_Profile = pd.DataFrame(columns = ['Day', 'Fixture', 'Start time (hr)', 'Duration (min)', 'Flow Rate (gpm)']) #Create a blank data frame to store the draw profile for this dwelling

        start_laggard_hot = time.time()
        for i in range(len(Annual_Profile)): #Perform this process for each row in Annual_Profile. Each row corresponds to a single day of the year
            Daily_Profile = Daily_Profiles[Daily_Profiles['Day'] == Annual_Profile[i]].copy() #Create a data frame containing the draw profile for the current day
            Daily_Profile['Mains Temperature (deg F)'] = T_Mains[i] #Calculate mains water temperature forthe active day, add a new column expressing it to Daily_Profile. THIS LINE CAUSES THE SCRIPT TO RUN SLOWLY, CAUSED BY REFERENCING [24 * i]. THIS .loc METHOD WAS SUPPOSED TO SOLVE THAT BUT DIDN'T. NEED TO FIND A BETTER SOLUTION.
            Daily_Profile['Start Time of Year (hr)'] = Daily_Profile['Start time (hr)'] + (24 * i) #Create a new column that states the time of year, relative to midnight on Jan 1, that this draw starts. This is needed for the Combiner function
            Daily_Profile['Day of Year (Day)'] = i + 1 #Add a new column stating the day of the year that this profile is representing
            Dwelling_Profile = Dwelling_Profile.append(Daily_Profile) #Append the profile for the current day to the data frame for the annual draw profile
        end_laggard_hot = time.time()

        Dwelling_Profile = Calculate_Fraction_HotWater(Temperature_Supply_WaterHeater, Dwelling_Profile) #Calculate the fraction of hot water for each draw in the draw profile
        Dwelling_Profile = Calculate_FlowWater_Hot(Dwelling_Profile) #Calculate the flow of hot water for each draw in the draw profile

        Dwelling_Profile = Dwelling_Profile.reset_index() #After appending the index will be messed up. These two lines fix that
        del Dwelling_Profile['index']

    if Include_Faucet == 'No' or Include_Shower == 'No' or Include_Clothes == 'No' or Include_Dish == 'No' or Include_Bath == 'No': #Unless the user said they do not want to filter draws by fixture
        Dwelling_Profile, Included_Code = Filter_DataSet_ByFixture(Dwelling_Profile, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath) #Call the Filter_DataSet_ByFixture function to limit the resulting profile to only contain draws that match the specified filter
    else: #If everything is included
        Included_Code = ['F','S','C','D','B'] #Use Included_Code to show that all are included, don't filter data set
    
    Dwelling_Profile = Dwelling_Profile.sort_values(['Start Time of Year (hr)']) #Sorts the draws in the in chronological order

    return Dwelling_Profile, Included_Code #Return the Dwelling_Profile data frame and the list of profiles when this function is finished

def Modify_Profile_SDLM(Dwelling_Profile, SquareFootage_Dwelling, Water): #This function calculates the total mixed water flow rate by taking SDLM into account

    Standard_Distribution_Loss_Multiplier = 1.0032 + 0.0001864 * min(2500, SquareFootage_Dwelling) - 0.00000002165 * min(2500, SquareFootage_Dwelling) ** 2 #Calculated per Equation 6 in the ACM. Believe that there is a typo in the ACM, and it should be +1.0032, not =1.0032. Based on both results of equation and comparing to previous versions
    Dwelling_Profile['Flow Rate (gpm)'] = Dwelling_Profile['Flow Rate (gpm)'] * Standard_Distribution_Loss_Multiplier #Multiply the flow rate of water by SDLM, matching the calculations in CBECC (This is a silly way to do it, I think they should have applied SDLM to duration instead, but I don't get to make the rules)

    if Water == 'Hot': #If the user wants to generate a hot water draw profile
        Dwelling_Profile['Hot Water Flow Rate (gpm)'] = Dwelling_Profile['Hot Water Flow Rate (gpm)'] * Standard_Distribution_Loss_Multiplier #Also apply the SDLM to the hot water flow rate
        Dwelling_Profile['Hot Water Volume (gal)'] = Dwelling_Profile['Hot Water Volume (gal)'] * Standard_Distribution_Loss_Multiplier #Also apply the SDLM to the volume of hot water consumed

    return Dwelling_Profile #Return the modified Dwelling_Profile

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

def Combine_Profiles(Profiles, Water):
    Combined_Profile = pd.concat(Profiles) #Creates a concatenated dataframe of the profiles in the list. This enables handling all of them in a single data frame
    Combined_Profile = Combined_Profile.sort_values(['Start Time of Year (hr)']) #Sorts the draws in the combined draw profile by the yearly start time to combine all dwelling draw profiles in chronological order

    Combined_Profile = Combined_Profile.reset_index() #Updates the index to match the newly sorted draw profile
    del Combined_Profile['index']

    Combined_Profile['End Time of Year (hr)'] = Combined_Profile['Start Time of Year (hr)'] + Combined_Profile['Duration (min)'] / 60. #Calculates that ending time of each draw by adding the duration of that draw to its start time

    Result_Profile = pd.DataFrame(columns = Combined_Profile.columns) #Creates a data frame to use as the final output after the following calculations are performed

    if Water == 'Hot': #If the user wants a profile showing the hot water draw pattern
        Column_Name = 'Hot Water Flow Rate (gpm)' #Inform the program that we need to perform calculations on this column
    elif Water == 'Mixed': #If the user wants a profile showing the mixed water draw pattern
        Column_Name = 'Flow Rate (gpm)' #Inform the program that we need to perform calculations on this column

    Skip = 0 #Creates a new variable that will be used to skip lines of the dataframe if they have already been added elsewhere

    #This code cycles through all of the draws in Combined_Profile and adds them to Result_Profile. It handles the draws in different ways depending on the situations. There are several situations. 1) The current draw ends before the next draw begins, 2) The next draw begins before the current draw ends, and ends after the current draw ends, 3) The next draw both begins and ends before the current draw ends, 4) The current and following draws both start and end at the same time
    for i in range(len(Combined_Profile.index)-1):

        if Skip > 0: #If this line has already been handled by one of the "overlapping draw" routines
            Skip -=1 #Skip this line, and reduce the number of lines in skip by 1

        elif Combined_Profile.loc[i+1, 'Start Time of Year (hr)'] >= Combined_Profile.loc[i, 'End Time of Year (hr)']: #If the next draw begins after the current draw ends
            Result_Profile = Result_Profile.append(Combined_Profile.loc[i]) #Add the current draw to the Result_Profile

            Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
            del Result_Profile['index']
            Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 1
        elif Combined_Profile.loc[i+1, 'Start Time of Year (hr)'] == Combined_Profile.loc[i, 'Start Time of Year (hr)'] and Combined_Profile.loc[i+1, 'End Time of Year (hr)'] == Combined_Profile.loc[i, 'End Time of Year (hr)']: #IF the current draw and following draw both start and end at the same time
            Result_Profile = Result_Profile.append(Combined_Profile.loc[i]) #Add the draw to Result_Profile

            Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
            del Result_Profile['index']
            Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 2
            Result_Profile.loc[Result_Profile.index.max(), Column_Name] = Combined_Profile.loc[i, Column_Name] + Combined_Profile.loc[i+1, Column_Name] #Combine the two flow rates and update Result_Profile accordingly

            Skip = 1

        elif Combined_Profile.loc[i+1, 'End Time of Year (hr)'] < Combined_Profile.loc[i, 'End Time of Year (hr)']: #If the next draw ends before the current draw ends

            Index_Next_Draw_Post_Current_Draw = Combined_Profile[Combined_Profile['Start Time of Year (hr)'].gt(Combined_Profile.loc[i, 'End Time of Year (hr)'])].index[0] #Finds the first draw that starts that starts AFTER the current draw ends. For example: If the current draw is a long shower, the following four draws are short faucet draws, and three of those faucet draws occur during the shower, this line identifies the index of the fourth faucet draw that starts after the shower ends
            Overlapping_Draws = Index_Next_Draw_Post_Current_Draw - i #Calculates the number of draws that occur during this first draw
            Active_Draw_Indices = [] #Create a list to hold the indices of all currently active draws

            j = 0 #Set j = 0 before starting a while llop
            while j < Overlapping_Draws or len(Active_Draw_Indices) > 0: #Creates a for loop going through each of the overlapping draws, and continuing until all of the active draws have ended

                Next_Change = Determine_Next_Change(Combined_Profile, Active_Draw_Indices, i+j) #Identify the next change in the draw profile (Either a new draw beginning, or an active draw ending)
                if Next_Change == 'New draw beginning': #If the next change represents a new draw starting
                    Result_Profile, Active_Draw_Indices = New_Draw_Beginning(Combined_Profile, Result_Profile, Active_Draw_Indices, i+j) #Call the New_Draw_Beginning function to amend the Result_Profile dataframe and Active_Draw_Indices list
                    j += 1 #Add 1 to j indicating that the next draw has been handled, and the script can move on to the next j
                if Next_Change == 'Active draw ending': #If the next change is a draw ending
                    Result_Profile, Active_Draw_Indices = Active_Draw_Ending(Combined_Profile, Result_Profile, Active_Draw_Indices, i+j) #Call the Active_Draw_Ending function to modify the Result_Profile dataframe and Active_Draw_Indices list

            Skip = Overlapping_Draws - 1 #Skip each of the draws in the overlapping list

        elif Combined_Profile.loc[i+1, 'Start Time of Year (hr)'] < Combined_Profile.loc[i, 'End Time of Year (hr)'] and Combined_Profile.loc[i, 'End Time of Year (hr)'] < Combined_Profile.loc[i+1, 'End Time of Year (hr)']: #If the next draw starts before the current draw ends, and the current draw ends before the next draw ends
            Result_Profile = Result_Profile.append(Combined_Profile.loc[i]) #Add a new row in Result_Profile with the parameters of the current draw in Combined_Profile. This draw represents the period when the first draw is active before the second draw begins

            Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
            del Result_Profile['index']
            Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 4
            Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] = Combined_Profile.loc[i+1, 'Start Time of Year (hr)']  #Sets end time of the current draw in Result_Profile to the start time of the next draw in Combined_Profile
            Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Combined_Profile.loc[i+1, 'Start Time of Year (hr)'] - Combined_Profile.loc[i, 'Start Time of Year (hr)']) * 60 #Sets the duration of the next draw in Result_Profile to the time before the next draw in Combined_Profile starts

            Result_Profile = Result_Profile.append(Combined_Profile.loc[i+1]) #Adds a new draw in Result_Profile with the characteristics of the next draw in Combined_Profile. This draw represents the period when both draws are active

            Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
            del Result_Profile['index']
            Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 4
            Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] = Combined_Profile.loc[i, 'End Time of Year (hr)'] #Set the end time of the draw in Result_Profile to the end time of the current draw in Combined_Profile
            Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Combined_Profile.loc[i, 'End Time of Year (hr)'] - Combined_Profile.loc[i+1, 'Start Time of Year (hr)'])*60 #Sets the duration of the draw to the end time of the current draw minus the start time of the next draw
            Result_Profile.loc[Result_Profile.index.max(), Column_Name] = Combined_Profile.loc[i, Column_Name] + Combined_Profile.loc[i+1, Column_Name] #Sets the water flow rate equal to the two draw flow rates combined

            Result_Profile = Result_Profile.append(Combined_Profile.loc[i+1]) #Create another row in Result_Profile. Use the information from the second draw b/c it holds the right flow rate and end time This draw represents the period when only the second draw is active

            Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
            del Result_Profile['index']
            Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 4
            Result_Profile.loc[Result_Profile.index.max(), 'Start Time of Year (hr)'] = Combined_Profile.loc[i, 'End Time of Year (hr)'] #Set the end time of the draw in Result_Profile to the end time of the current draw in Combined_Profile
            Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Combined_Profile.loc[i+1, 'End Time of Year (hr)'] - Combined_Profile.loc[i, 'End Time of Year (hr)']) * 60 #Set the duration of the draw in Result_Profile to the difference in the two end times

            Skip = 1


    Result_Profile = Result_Profile.append(Combined_Profile.loc[Combined_Profile.index.max()])
    Result_Profile = Result_Profile.reset_index()
    del Result_Profile['index']

    Result_Profile['Start time (hr)'] = Result_Profile['Start Time of Year (hr)'] % 24 #Update the 'Start time (hr)' column

    Result_Profile = Result_Profile.reset_index() #Reset the index to match the new data frame
    del Result_Profile['index']

    if Water == 'Hot': #If the user wants to generate a hot water draw profile
        Result_Profile['Hot Water Flow Rate (gpm)'] = Result_Profile['Flow Rate (gpm)'] * Result_Profile['Fraction Hot Water'] #Calculate the new, combined hot water flow rates in rach draw
        Result_Profile['Hot Water Volume (gal)'] = Result_Profile['Hot Water Flow Rate (gpm)'] * Result_Profile['Duration (min)'] #Calculate the volume of hot water in each draw

    return Result_Profile, Combined_Profile #Return the data frame as the result of the function

def Filter_DataSet_ByFixture(Dwelling_Profile, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath): #Filters the data set to only include the fixtures requested by the user. User requests a fixture by setting the appropriate input to 'Yes'

    Included_Code = [] #Create an empty list to store information on what fixtures are included in this draw profile
    Profile = pd.DataFrame(columns = Dwelling_Profile.columns) #Create a new dataframe for the output draw profile that has the same columns as the input draw profile
    if Include_Faucet == 'Yes': #If the user selects to include faucets
        Included_Code.append('F') #Add 'F' to the list of included fixtures
        Profile = Profile.append(Dwelling_Profile[Dwelling_Profile['Fixture'] == 'FAUC']) #Select the data for faucet draws, add it to the profile
    if Include_Shower == 'Yes': #If the user selects to incldue shower draws
        Included_Code.append('S') #Add 'S' to the list of included fixtures
        Profile = Profile.append(Dwelling_Profile[Dwelling_Profile['Fixture'] == 'SHWR']) #Select the data for shower draws, add it to the profile
    if Include_Clothes == 'Yes': #If the user selects that they want to include draws for clothes washers
        Included_Code.append('C') #Add 'C' to the list of included fixtures
        Profile = Profile.append(Dwelling_Profile[Dwelling_Profile['Fixture'] == 'CWSH']) #Select the data for clothes washers, add it to the profile
    if Include_Dish == 'Yes': #If the user selects to include dishwasher draws
        Included_Code.append('D') #Add 'D' to the list of included fixtures
        Profile = Profile.append(Dwelling_Profile[Dwelling_Profile['Fixture'] == 'DWSH']) #Select the data for dishwashers, add it to the profile
    if Include_Bath == 'Yes': #If the user selects to include bath draws
        Included_Code.append('B') #Add 'B' to the list of included fixtures
        Profile = Profile.append(Dwelling_Profile[Dwelling_Profile['Fixture'] == 'BATH']) #Select the data for baths, add it to the profile

    Profile = Profile.sort_values('Start Time of Year (hr)') #Sort the dataframe such that the data is presented in chronological order
    Profile = Profile.reset_index() #Reset the index since it got out of order when resetting the index
    del Profile['index'] #Delete the new column called 'index' because that's a silly thing for pandas to do anyway

    return Profile, Included_Code

def Determine_Next_Change(Combined_Profile, Active_Draw_Indices, Next_Draw_Index): #This function looks at the next draw in the profile and determines what happens next. It observes any draws that may currently be active, and the next draw
    if len(Active_Draw_Indices) == 0: #If there are no currently active draws
        return 'New draw beginning' #Then the next line must be a new draw
    elif Combined_Profile.loc[Active_Draw_Indices, 'End Time of Year (hr)'].min() < Combined_Profile.loc[Next_Draw_Index, 'Start Time of Year (hr)']: #Look at the currently active draws, find the time of the one that ends first. If it ends before the next one begins
        return 'Active draw ending' #Then that draw ending is the next change in the profile
    else: #If a new draw starts before any of the currently active draws ends
        return 'New draw beginning' #Then the next change in the profile is a new draw beginning

def New_Draw_Beginning(Combined_Profile, Result_Profile, Active_Draw_Indices, Next_Draw_Index): #This function edits the resulting profile by adding a newly beginning draw to it
    if len(Active_Draw_Indices) == 0: #If there are no active draws, merely append the next draw to the end of the profile
        Active_Draw_Indices.append(Next_Draw_Index) #Append the index of the draw to the list of active draws

        Result_Profile = Result_Profile.append(Combined_Profile.loc[Next_Draw_Index]) #Append the draw to the end of the draw profile
        Result_Profile = Result_Profile.reset_index() #Fix the index
        del Result_Profile['index']

        Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 3 #State the type of the draw for debuggin purposes

    else: #If there are other currently active draws, then add the new draw to the current draws

        Active_Draw_Indices.append(Next_Draw_Index) #Append the index of the draw to the list of active draws
        Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] = Combined_Profile.loc[Next_Draw_Index, 'Start Time of Year (hr)'] #Set the end time of the last draw to be the starting time of the new draw
        Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Combined_Profile.loc[Next_Draw_Index, 'Start Time of Year (hr)'] - Result_Profile.loc[Result_Profile.index.max(), 'Start Time of Year (hr)']) * 60. #Recalculate the duration of the last draw accordingly

        Result_Profile = Result_Profile.append(Combined_Profile.loc[Next_Draw_Index]) #Add a new line to the profile, representing the new draw
        Result_Profile = Result_Profile.reset_index() #Fix the index
        del Result_Profile['index']

        Result_Profile.loc[Result_Profile.index.max(), 'Flow Rate (gpm)'] = Combined_Profile.loc[Active_Draw_Indices, 'Flow Rate (gpm)'].sum() #Set the flow rate of the new draw equal to the sum of all currently active draws
        Result_Profile.loc[Result_Profile.index.max(), 'Fixture'] = Combined_Profile.loc[Active_Draw_Indices, 'Fixture'].str.cat() #Set the fixture of the current draw equal to the concatenated list of all active draws
        Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 3 #Set the fixture type = 3 for debugging purposes

    return Result_Profile, Active_Draw_Indices

def Active_Draw_Ending(Combined_Profile, Result_Profile, Active_Draw_Indices, Next_Draw_Index): #This function modifies the draw profile accordingly when the next change is an active draw ending
    #Are these two lines necessary? Were they not taken care of previously?
    Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] = Combined_Profile.loc[Active_Draw_Indices, 'End Time of Year (hr)'].min() #Set the end time of the most recent draw equal to the minimum end time of all active draws
    Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Combined_Profile.loc[Active_Draw_Indices, 'End Time of Year (hr)'].min() - Result_Profile.loc[Result_Profile.index.max(), 'Start Time of Year (hr)'])*60. #Calculate the duration of the last draw accordingly

    Index_Ending_Draw = Combined_Profile.loc[Active_Draw_Indices, 'End Time of Year (hr)'].idxmin() #Identify the index of the draw that is ending first
    Active_Draw_Indices.remove(Index_Ending_Draw) #Remove that value from Active_Draw_Indices

    if len(Active_Draw_Indices) > 0: #If there are still active draws (I.e. If the ending draw wasn't the only active draw)

        Result_Profile = Result_Profile.append(Combined_Profile.loc[Active_Draw_Indices[0]]) #Add a new row to Result_Profile containing the information of one active draw
        Result_Profile = Result_Profile.reset_index() #Fix the index
        del Result_Profile['index']

        Result_Profile.loc[Result_Profile.index.max(), 'Flow Rate (gpm)'] = Combined_Profile.loc[Active_Draw_Indices, 'Flow Rate (gpm)'].sum() #Set the flow rate of the active draw equal to the sum of all active draw flow rates
        Result_Profile.loc[Result_Profile.index.max(), 'Fixture'] = Combined_Profile.loc[Active_Draw_Indices, 'Fixture'].str.cat() #Set the fixture of the active draw equal to the concatenated string of all active draws
        Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] =  Combined_Profile.loc[Active_Draw_Indices, 'End Time of Year (hr)'].min() #Set the end time of the active draw equal to the end time of the first ending draw
        Result_Profile.loc[Result_Profile.index.max(), 'Start Time of Year (hr)'] =  Result_Profile.loc[Result_Profile.index.max()-1, 'End Time of Year (hr)'] #Set the start time of the active draw equal to the end time of the previous draw
        Result_Profile.loc[Result_Profile.index.max(), 'Duration (min)'] = (Result_Profile.loc[Result_Profile.index.max(), 'End Time of Year (hr)'] -  Result_Profile.loc[Result_Profile.index.max(), 'Start Time of Year (hr)'])*60. #Calculate the duration of the active draw accordingly
        Result_Profile.loc[Result_Profile.index.max(), 'Type'] = 3 #Set Type = 3 for debugging purposes

    return Result_Profile, Active_Draw_Indices

def Combined_Profile_LargeBuilding(Profiles, Water):
    Combined_Profile = pd.concat(Profiles) #Creates a concatenated dataframe of the profiles in the list. This enables handling all of them in a single data frame
    Combined_Profile = Combined_Profile.sort_values(['Start Time of Year (hr)']) #Sorts the draws in the combined draw profile by the yearly start time to combine all dwelling draw profiles in chronological order
    
    Combined_Profile = Combined_Profile.reset_index() #Updates the index to match the newly sorted draw profile
    del Combined_Profile['index']
    
    Combined_Profile['End Time of Year (hr)'] = Combined_Profile['Start Time of Year (hr)'] + Combined_Profile['Duration (min)'] / 60. #Calculates that ending time of each draw by adding the duration of that draw to its start time):
    
    Combined_Profile['Start time (hr)'] = Combined_Profile['Start Time of Year (hr)'] % 24 #Update the 'Start time (hr)' column

    if Water == 'Hot': #If the user wants to generate a hot water draw profile
        Combined_Profile['Hot Water Flow Rate (gpm)'] = Combined_Profile['Flow Rate (gpm)'] * Combined_Profile['Fraction Hot Water'] #Calculate the new, combined hot water flow rates in rach draw
        Combined_Profile['Hot Water Volume (gal)'] = Combined_Profile['Hot Water Flow Rate (gpm)'] * Combined_Profile['Duration (min)'] #Calculate the volume of hot water in each draw
    
    return Combined_Profile #Return the data frame as the result of the function    

#%%---------------------------GENERATE AND SAVE REQUESTED DRAW PROFILE---------

NumberBedrooms_Dwellings.sort() #Sorts the list of number of bedrooms in each dwelling to be from min to max

Variants = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'] #In multi-family buildings there are several different draw profiles for a dwelling with a given number of bedroom. This is to ensure that the different dwellings don't all do the exact same thing. This list of variants allows the script to iterate through the different draw profiles

Variant = 0 #Creates a starting value for variant as the first variant. Will increase as needed during processing, if there are multiple dwelling with the same number of bedrooms

Profiles = [] #Creates an empty list that will hold profiles to be combined. Is only useful if Combied == 'Yes'

for i in range(len(NumberBedrooms_Dwellings)): #For each entry in the list NumberBedrooms_Dwellings
    if Building_Type == 'Multi': #If the profile being generated is for multi-family buildings
        if i != 0: #If it is NOT the first time through this for loop
            if NumberBedrooms_Dwellings[i-1] == NumberBedrooms_Dwellings[i]: #And if the previous entry had the same number of bedrooms as the current entry
                if Variant == 9: #If the last draw profile used variant 'j', the last variant
                    Variant = 0 #Reset to 0 and start over at Variant 'a'
                else: #Otherwise
                    Variant += 1 #Advance to the next entry in the Variants list
            else: #If the previous entry did not have the same number of bedrooms, we know that the new dwelling has a different number of bedrooms and starts over at the new Variant
                Variant = 0

    if Water == 'Hot': #If the user is requesting how water information
        Dwelling_Profile, Included_Code = Create_Hot_Profile_NoSDLM(Building_Type, NumberBedrooms_Dwellings[i], Variants[Variant], ClimateZone, Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath)

    elif Water == 'Mixed': #If the user is requesting mixed water flow exiting the fixture
        Dwelling_Profile, Included_Code = Create_Mixed_Profile_NoSDLM(Building_Type, NumberBedrooms_Dwellings[i], Variants[Variant], Include_Faucet, Include_Shower, Include_Clothes, Include_Dish, Include_Bath) #Call the Create_Mixed_Profile_AtFixture function to create the draw profile for this dwelling. Note that this returns the mixed water profile without including SDLM

    if SDLM == 'Yes': #If SDLM == 'Yes' then  execute this code calcualting the SDLM and adding it to the flow rate in the draw profile
        Dwelling_Profile = Modify_Profile_SDLM(Dwelling_Profile, SquareFootage_Dwellings[i], Water) #Calls the Create_Mixed_Profile_SDLM to add the SDLM impacts into the draw profile. Note that this is still mixed temperature data
    
    if Combined == 'No' and Combined_LargeBuilding == 'No': #If the user does not want all draw profiles combined into a single file, use this code to print one file for each draw profile

        if not os.path.exists(Folder_Output + os.sep + Building_Type + os.sep + Water):
            os.makedirs(Folder_Output + os.sep + Building_Type + os.sep + Water)

        if Building_Type == 'Multi': #If it's a multi-family building
            if SDLM == 'Yes':
                Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Prof=' + str(NumberBedrooms_Dwellings[i]) + str(Variants[Variant]) + '_SDLM=' + SDLM + '_CFA=' + str(SquareFootage_Dwellings[i]) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name          
            elif SDLM == 'No':
                Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Prof=' + str(NumberBedrooms_Dwellings[i]) + str(Variants[Variant]) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name          
        elif Building_Type == 'Single': #If it's a single family building
            if SDLM == 'Yes':
                Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Prof=' + str(NumberBedrooms_Dwellings[i]) + '_SDLM=' + SDLM + '_CFA=' + str(SquareFootage_Dwellings[i]) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name          
            elif SDLM == 'No':
                Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Prof=' + str(NumberBedrooms_Dwellings[i]) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name          

    elif Combined == 'Yes' or Combined_LargeBuilding == 'Yes': #If the user wants the draw profiles to be combined then execute this code
            Profiles.append(Dwelling_Profile) #Add the draw profile to the list of draw profiles that we need to combine

if Combined == 'Yes': #If the user wants the draw profiles to be combined into one then execute this code
    Dwelling_Profile, Combined_Profile = Combine_Profiles(Profiles, Water) #Call the Combine_Profiles function to combine all of the profiles generated in this run

    if not os.path.exists(Folder_Output + os.sep + Building_Type + os.sep + Water):
        os.makedirs(Folder_Output + os.sep + Building_Type + os.sep + Water)     

    if SDLM == 'Yes':
        Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Profile=' + str(NumberBedrooms_Dwellings) + '_SDLM=' + SDLM + '_CFA=' + str(SquareFootage_Dwellings) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name
    elif SDLM == 'No':
        Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Wat=' + Water + '_Profile=' + str(NumberBedrooms_Dwellings) + '_Inc=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name

#   All of the following code is for debugging purposes

#    Dwelling_Profile['Volume (gal)'] = Dwelling_Profile['Duration (min)'] * Dwelling_Profile['Flow Rate (gpm)'] #For debugging
#    Combined_Profile['Volume (gal)'] = Combined_Profile['Duration (min)'] * Combined_Profile['Flow Rate (gpm)'] #For debugging
#        
#    p1 = figure(width=1200, height=600, x_axis_label='Time (hr)', y_axis_label = 'Volume (gal)')
#    p1.line(Dwelling_Profile['Start Time of Year (hr)'], Dwelling_Profile['Volume (gal)'].cumsum(), legend='Dwelling_Profile', color = 'red')   
#    p1.line(Combined_Profile['Start Time of Year (hr)'], Combined_Profile['Volume (gal)'].cumsum(), legend='Combined_Profile', color = 'blue')
#    p1.legend.location = 'top_left'
#    
#    p = gridplot([[p1]])
#    output_file(Folder_Output + '\Debugging.html', title = 'Volumes')
#    save(p)

if Combined_LargeBuilding == 'Yes': #If the user wants the draw profiles to be combined into one then execute this code
    Dwelling_Profile = Combined_Profile_LargeBuilding(Profiles, Water) #Call the Combine_Profiles function to combine all of the profiles generated in this run

    if not os.path.exists(Folder_Output + os.sep + Building_Type + os.sep + Water):
        os.makedirs(Folder_Output + os.sep + Building_Type + os.sep + Water)

    if SDLM == 'Yes':
        Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Water=' + Water + '_Profile=' + str(NumberBedrooms_Dwellings) + '_SDLM=' + SDLM + '_CFA=' + str(SquareFootage_Dwellings) + '_Included=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name
    elif SDLM == 'No':
        Dwelling_Profile.to_csv(Folder_Output + os.sep + Building_Type + os.sep + Water + os.sep + 'Bldg=' + Building_Type + '_CZ=' + str(ClimateZone) + '_Water=' + Water + '_Profile=' + str(NumberBedrooms_Dwellings) + '_Included=' + str(Included_Code) + '.csv', index = False) #Saves the data to the correct folder with a descriptive file name
        
#    p1 = figure(width=1200, height=600, x_axis_label='Time (hr)', y_axis_label = 'Volume (gal)')
#    p1.line(Dwelling_Profile['Start Time of Year (hr)'], Dwelling_Profile['Volume (gal)'].cumsum(), legend='Dwelling_Profile', color = 'red')
#    p1.line(Combined_Profile['Start Time of Year (hr)'], Combined_Profile['Volume (gal)'].cumsum(), legend='Combined_Profile', color = 'blue')
#    p1.legend.location = 'top_left'
#
#    p = gridplot([[p1]])
#    output_file(Folder_Output + os.sep + 'Debugging.html', title = 'Volumes')
#    save(p)

end_time = time.time()
print("total = {}, mixed = {}, hot = {}".format(end_time - start_time, end_laggard_mixed-start_laggard_mixed, end_laggard_hot-start_laggard_hot))


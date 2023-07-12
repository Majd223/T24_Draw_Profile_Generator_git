# -*- coding: utf-8 -*-
"""
Created on Tue Nov 29 09:08:06 2022

This script combines multiple timestep-based T24 draw profiles into a single file
It creates a column for each draw profile (named using the number of bedrooms and variant)
then sums the columns to find the total

CAUTION: This script is currently written for a specific project, and probably needs to be edited
prior to use for other projects

@author: Peter Grant
"""

import pandas as pd
import glob
import os
import datetime
import matplotlib.pyplot as plt

#%%------------------------INPUTS---------------------------------

Dymola_Export = True

cwd = os.getcwd()
Folder = os.path.join(cwd, 'DrawProfiles', 'Timestep_Based')
Files = glob.glob(Folder + '/*.csv')

Dates_Four = {
              'Low': datetime.date(2022, 5, 10),
              'Medium': datetime.date(2022, 1, 29),
              'High': datetime.date(2022, 1, 26)
             }

Dates_Six = {
             'Low': datetime.date(2022, 8, 14),
             'Medium': datetime.date(2022, 10, 1),
             'High': datetime.date(2022, 11, 13)
            }

Dates_Eight = {
          'Low': datetime.date(2022, 6, 1),
          'Medium': datetime.date(2022, 2, 9),
          'High': datetime.date(2022, 3, 31)
          }

#%%----------------FUNCTIONS--------------------------------------

def Change_Mains_Temperature():
    '''
    
    Overwrites the inlet water temperature to simulate TES charging times
    @Weiping - Please add code as needed here

    '''

def Convert_To_Dymola(Draw_Profile):
    
    temp = Draw_Profile.copy(deep = True)
    # temp['Mains Temperature (deg C)'] = 65.6
    temp['tvalue'] = temp.index
    temp['delta'] = (temp['tvalue'] - temp['tvalue'].shift()).dt.total_seconds()
    temp.loc[temp.index[0], 'delta'] = 0
    temp['delta'] = temp['delta'].astype(int)
    temp.index = temp['delta'].cumsum()
    temp = temp.drop(columns = ['tvalue', 'delta'])
    
    temp = temp[['Mains Temperature (deg C)', 'Timestep (min)', 'Building Hot Water Draw Volume (L)']]
    
    Number_Rows = len(temp.index)
    Number_Columns = len(temp.columns)
    Header = pd.DataFrame(index = ['#1', 'double'], columns = ['Mains Temperature (deg C)'])
    Header.loc['double', 'Mains Temperature (deg C)'] = 'tab1({},{})'.format(Number_Rows, Number_Columns + 1)
    
    temp = pd.concat([Header, temp])
    
    return temp

def Save_Result(Draw_Profile, Dymola_Export, Dates):
    
    Cols = [col for col in Draw_Profile.columns if '(L)' in col]
    if len(Cols) == 9:
        Size = 'Eight'
        Variants = '[abcd]'
    elif len(Cols) == 7:
        Size = 'Six'
        Variants = '[abc]'
    elif len(Cols) == 5:
        Size = 'Four'
        Variants = '[ab]'
    else:
        print('Unkown number of dwellings, len(cols) == {}'.format(len(Cols)))
        Size = 'Unknown'
    print(Size)

    if Dymola_Export == True:
        
        for Date in Dates.keys():
            print(Date)
            print(Dates[Date])
            Day_Profile = Draw_Profile.loc[Draw_Profile.index.date == Dates[Date]]
            print(Day_Profile['Building Hot Water Draw Volume (L)'].sum())
            Day_Profile = Convert_To_Dymola(Day_Profile)
            
            #@Weiping - Please add some content to the filename describing the charge/discharge times
            
            Day_Profile.to_csv(os.path.join(Folder, 'Compiled', 'CZ={}_CECPrototype_6960ft2_2008_{}Dwellings_Variants={}_{}_Cold.txt'.format(CZ, Size, Variants, Date)),
                                sep = '\t', header = False)
        
        Draw_Profile = Convert_To_Dymola(Draw_Profile)
        Draw_Profile.to_csv(os.path.join(Folder, 'Compiled', 'CZ={}_CECPrototype_6960ft2_2008_{}Dwellings_Variants={}_Cold.txt'.format(CZ, Size, Variants)),
                            sep = '\t', header = False)
    else:
        Draw_Profile.to_csv(os.path.join(Folder, 'Compiled', 'CZ={}_CECPrototype_6960ft2_2008_{}Dwellings_Variants={}_Cold.csv'.format(CZ, Size, Variants)))
        for Date in Dates.keys():
            Day_Profile = Profile.loc[Profile.index.date == Dates[Date]]
            Day_Profile = Convert_To_Dymola(Day_Profile)
            Day_Profile.to_csv(os.path.join(Folder, 'Compiled', 'CZ={}_CECPrototype_6960ft2_2008_{}Dwellings_Variants={}_{}_Cold.txt'.format(CZ, Size, Variants, Date)))        


#%%--------------------EXECUTE CODE--------------------

CZs = []
for File in Files:
    CZ = File.split('M_')[-1].split('_')[0]
    CZs.append(CZ)

CZs = list(set(CZs))

print(CZs)

# CZ = '03'
# if True:
for CZ in CZs:
    print(CZ)
    Files_CZ = [File for File in Files if File.split('M_')[-1].split('_')[0] == CZ]
    File = [File for File in Files_CZ if '_1a_' in File][0]
    Files_CZ.remove(File)
    
    Profile = pd.read_csv(File, index_col = 0)
    Profile.index = pd.to_datetime(Profile.index)
    Profile_Name = File.split('_')[7]
    Profile = Profile.rename(columns = {'Hot Water Draw Volume (L)': '{} (L)'.format(Profile_Name)})
    
    Four_Dwellings = Profile.copy(deep = True)
    Six_Dwellings = Profile.copy(deep = True)
    
    for File in Files_CZ:
        df = pd.read_csv(File, index_col = 0)
        df.index = pd.to_datetime(df.index)
        Profile_Name = File.split('_')[7]
        Profile['{} (L)'.format(Profile_Name)] = df['Hot Water Draw Volume (L)']
        if 'a' in Profile_Name or 'b' in Profile_Name:
            Four_Dwellings['{} (L)'.format(Profile_Name)] = df['Hot Water Draw Volume (L)']    
        if 'a' in Profile_Name or 'b' in Profile_Name or 'c' in Profile_Name:
            Six_Dwellings['{} (L)'.format(Profile_Name)] = df['Hot Water Draw Volume (L)']    
            
    cols = [col for col in Profile.columns if '(L)' in col]
    Profile['Building Hot Water Draw Volume (L)'] = Profile[cols].sum(axis = 1)
    cols = [col for col in Six_Dwellings.columns if '(L)' in col]
    Six_Dwellings['Building Hot Water Draw Volume (L)'] = Six_Dwellings[cols].sum(axis = 1)
    cols = [col for col in Four_Dwellings.columns if '(L)' in col]
    Four_Dwellings['Building Hot Water Draw Volume (L)'] = Four_Dwellings[cols].sum(axis = 1)
    
    # @Weiping - Please run Change_Mains_Temperature on [Profile, Six_Dwellings, Foud_Dwellings] here
    
    Save_Result(Profile, Dymola_Export, Dates_Eight)
    Save_Result(Six_Dwellings, Dymola_Export, Dates_Six)
    Save_Result(Four_Dwellings, Dymola_Export, Dates_Four)
    
    fig = plt.figure()
    plt.plot(Profile.index, Profile['Building Hot Water Draw Volume (L)'])
    plt.title('CZ={} - All'.format(CZ))
    
    fig = plt.figure()
    plt.plot(Profile.index, Six_Dwellings['Building Hot Water Draw Volume (L)'])
    plt.title('CZ={} - Six'.format(CZ))      
    
    fig = plt.figure()
    plt.plot(Profile.index, Four_Dwellings['Building Hot Water Draw Volume (L)'])
    plt.title('CZ={} - Four'.format(CZ))    
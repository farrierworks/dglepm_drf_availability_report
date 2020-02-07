import csv
import sys
from datetime import datetime
import os
import pandas as pd
import seaborn as sns


# def various functions
def dict_from_csv(file_path):
    with open(file_path, 'r') as f:
        reader = csv.reader(f, skipinitialspace=True, delimiter=',')
        next(reader)
        result = {}
        for row in reader:
            key = row[0]
            result[key] = row[1]
    return result


def list_from_csv(file_path):
    with open(file_path, 'r') as f:
        reader = csv.reader(f, skipinitialspace=True, delimiter=',')
        next(reader)
        list = []
        for row in reader:
            list.append(row[0])
    return list


def dict_str_to_float(dict):
    for k, v in dict.items():
        dict[k] = float(v)
    return dict


def dict_str_to_int(dict):
    for k, v in dict.items():
        dict[k] = int(v)
    return dict


# initialize variables with command line arguments or with defaults
if len(sys.argv) == 5:
    datestr1 = sys.argv[1]
    vor_tactical_report_filename = sys.argv[2]
    ie36_filename = sys.argv[3]
    zeiw29_filename = sys.argv[4]
elif len(sys.argv) == 1:
    datestr1 = datetime.now().strftime('%y%m%d')
    vor_tactical_report_filename = '/home/matthew/Desktop/vor_tactical_mpo_disposition_for_ps.xlsx'
    ie36_filename = '/home/matthew/Desktop/ie36.xlsx'
    zeiw29_filename = '/home/matthew/Desktop/zeiw29.xlsx'
    print("Using default input filenames and today's date.")
else:
    raise Exception("Expected 4 arguments.")

# initialize second date string variable
datetime_object = datetime.strptime(datestr1, '%y%m%d')
datestr2 = datetime_object.strftime('%d %b %y')

# create output directory for input and output files
output_dir = '/home/matthew/Desktop/test4/%s' % datestr1
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# read input files
vor_tactical_report = pd.read_excel(vor_tactical_report_filename, sheet_name='Sheet1')
ie36 = pd.read_excel(ie36_filename, sheet_name='Sheet1')
zeiw29 = pd.read_excel(zeiw29_filename, sheet_name='Sheet1')

# initialize list of disposal user status codes
disposal_user_status_code_list = list_from_csv('/home/matthew/Desktop/test4/disposal_user_status_code_list.csv')

# initialize various dictionaries
weapon_system_id_dict = dict_from_csv('/home/matthew/Desktop/test4/weapon_system_id_dict.csv')
np_drf_key_fleet_dict = dict_from_csv('/home/matthew/Desktop/test4/np_drf_key_fleet_dict.csv')
platform_dict = dict_from_csv('/home/matthew/Desktop/test4/platform_dict.csv')
maintenance_plant_dict = dict_from_csv('/home/matthew/Desktop/test4/maintenance_plant_dict.csv')
availability_target_dict = dict_from_csv('/home/matthew/Desktop/test4/availability_target_dict.csv')
availability_target_dict = dict_str_to_float(availability_target_dict)

# select relevant columns and rename them
vor_tactical_report = vor_tactical_report[['Equipment Number', 'Equip. Object Type', 'Maintenance plant', \
                                           'User & Info Statuses']]
vor_tactical_report.columns = ['equipment_number', 'equipment_object_type', 'maintenance_plant1', 'user_info_statuses']
ie36 = ie36[['Equipment', 'Description', 'Vehicle Type', 'Allocation Code']]
ie36.columns = ['equipment_number', 'description', 'equipment_object_type', 'allocation_code']
zeiw29 = zeiw29[['Equipment', 'Notification']]
zeiw29.columns = ['equipment_number', 'notification']

# merge dataframes, removing duplicate rows due to multiple notifications being open against a single piece of eqpt
df1 = pd.merge(vor_tactical_report, ie36, left_on=['equipment_number', 'equipment_object_type'], \
               right_on=['equipment_number', 'equipment_object_type'], how='left')
df1 = pd.merge(df1, zeiw29.drop_duplicates(subset=['equipment_number']), left_on='equipment_number', \
               right_on='equipment_number', how='left')

# create 'disposal_status' column containing inferred disposal status
df1['service_status'] = 'In Service'
df1.loc[(df1['allocation_code'].str.contains('M')) | \
        (df1['description'].str.contains('HARD TARGET')) | \
        (df1['user_info_statuses'].str.contains('|'.join(disposal_user_status_code_list))), 'service_status'] = \
    'Disposal'

# map weapon system IDs, NP & DRF key fleets and platforms to equipment object types
df1['weapon_system_id'] = df1['equipment_object_type'].map(weapon_system_id_dict)
df1['np_drf_key_fleet'] = df1['equipment_object_type'].map(np_drf_key_fleet_dict)
df1['platform'] = df1['equipment_object_type'].map(platform_dict)
df1['maintenance_plant2'] = df1['maintenance_plant1'].apply(str).map(maintenance_plant_dict)

# create 'disposition' column containing plant if eqpt is in service and disposal status otherwise
df1['disposition'] = df1['maintenance_plant2']
df1.loc[(df1['notification'] > 0), 'disposition'] = '202 WD'
df1.loc[(df1['service_status'] == 'Disposal'), 'disposition'] = 'Disposal'

# group by weapon system ID, NP & DRF key fleet, platform and disposition, and calculate quantities
df2 = pd.DataFrame({'quantity': df1.groupby(['weapon_system_id', 'np_drf_key_fleet', 'platform', \
                                             'disposition']).size()}).reset_index()

# create pivot table and rename columns
table1 = pd.pivot_table(df2, values='quantity', index=['weapon_system_id', 'np_drf_key_fleet', 'platform'], \
                        columns=['disposition'], fill_value=0).reset_index()
table1.columns = ['weapon_system_id', 'np_drf_key_fleet', 'platform', '202_wd', 'adm_mat', 'ca', 'cjoc', \
                  'disposal', 'mpc', 'rcaf', 'rcn', 'vcds']

# create columns containing # in inventory, # in service, # available, # unavailable, % available and % unavailable
table1['inventory'] = table1.sum(axis=1)
table1['in_service'] = table1['inventory'] - table1['disposal']
table1['#_available'] = table1[['ca', 'cjoc', 'mpc', 'rcaf', 'rcn', 'vcds']].sum(axis=1)
table1['#_unavailable'] = table1[['202_wd', 'adm_mat']].sum(axis=1)
table1['%_available'] = (100 * table1['#_available'] / table1['in_service']).round(1)
table1['%_unavailable'] = (100 * table1['#_unavailable'] / table1['in_service']).round(1)

# map availability targets to platform names in '%_planned' column and create column containing # planned
table1['%_planned'] = table1['platform'].map(availability_target_dict)
table1['#_planned'] = (table1['%_planned'] * table1['in_service'] / 100).astype('int')

# rearrange table1 columns
table1 = table1[['weapon_system_id', 'np_drf_key_fleet', 'platform', 'inventory', 'disposal', 'in_service', \
                 '%_planned', '#_planned', 'ca', 'cjoc', 'mpc', 'rcaf', 'rcn', 'vcds', '%_available', \
                 '#_available', '202_wd', 'adm_mat', '%_unavailable', '#_unavailable']]

# create table2
table2 = table1.groupby(['np_drf_key_fleet']).sum().reset_index()
table2 = table2[['np_drf_key_fleet', '#_available', '#_planned', 'in_service', 'disposal']]

# rename table1 columns
table1.columns = ['Weapon System ID', 'NP & DRF Key Fleet', 'Platform', 'Inventory [1]', 'Disposal [2]', \
                 'In Service [3]', '% Planned [4]', '# Planned [5]', 'CA', 'CJOC', 'MPC', 'RCAF', 'RCN', \
                 'VCDS', '% Available [7]', '# Available [8]', '202 WD', 'ADM (Mat)', '% Unavailable [10]', \
                 '# Unavailable [11]']

# add rows containing column sum totals and average percentages
column_sums = table1.select_dtypes(include='int').sum(axis=0)
column_averages = table1.select_dtypes(include='float').mean(axis=0).round(1)
table1.loc['Sum'] = column_sums
table1.loc['Average'] = column_averages

# write dataframe to Excel file in output directory
filename2 = output_dir + '/%s_availability_report_dglepm.xlsx' % datestr1
writer = pd.ExcelWriter(filename2, engine='xlsxwriter')
table1.to_excel(writer, sheet_name='Sheet1', startrow=3, index=False)
df1.to_excel(writer, sheet_name='Sheet2', index=False)
table2.to_excel(writer, sheet_name='Sheet3', index=False)
writer.save()
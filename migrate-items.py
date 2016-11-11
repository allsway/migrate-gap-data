#!/usr/bin/python
import requests
import sys
import csv
import ConfigParser
import xml.etree.ElementTree as ET
#from lxml import etree

def createurl(row):
	bib_id = row[0]
	holding_id = row[1]
	item_id = row[2]
	return '/almaws/v1/bibs/' + bib_id + '/holdings/'+ holding_id +'/items/' + item_id; 
	

# Read campus configuration parameters
config = ConfigParser.RawConfigParser()
config.read(sys.argv[1])

def get_key():
	return config.get('Params', 'apikey')
	
def get_campus_code():
	return config.get('Params', 'campuscode')
	
def get_sru_base():
	return config.get('Params', 'sru')
	
def get_base_url():
	return config.get('Params', 'baseurl')
	
def get_field_mapping():
	return config.get('Params', 'fieldmap')

"""
	Set up authoritative mapping:
		the mapping between the 'expected' alma fields and the API fields that correspond. 
		This can be done in a static way, it won't change, only the mapping between the expected and the local field name is dynamic
"""
def get_authoritative_mapping():
	dict = {'VOLUME':'description',
			'035|a': 'oclc',
			'COPY #':'copy_id', #holding
			'BARCODE':'barcode',
			'LOCATION':'location',
			'STATUS':'base_status',
			'I TYPE':'policy',
			'CREATED(ITEM)':'creation_date',
			'UPDATED(ITEM)':'modification_date',
			'INVDA':'',
			'PIECES':'pieces',
			'PRICE':'', # ??
			'PUBLIC_NOTE':'public_note',
			'FULFILMENT_NOTE':'fulfillment_note',
			'NON_PUBLIC_NOTE_1':'internal_note_1',
			'NON_PUBLIC_NOTE_2':'internal_note_2',
			'NON_PUBLIC_NOTE_3':'internal_note_3',
			'STAT_NOTE_1':'statistics_note_1',
			'STAT_NOTE_2':'statistics_note_2',
			'STAT_NOTE_3':'statistics_note_3'
	}
	return dict


"""
	Read in field_mapping.csv and map all item fields to Alma fields
"""
def read_mapping(mapping_file):
	field_mapping = {}
	f = open(mapping_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next() #skip header line
		for row in reader:
			if row[1]:
				field_mapping[row[1].strip()] = row[0].strip()
		return field_mapping
	finally:
		f.close()


"""
	Read in location_map.csv and create map between former locations and Alma locations
"""
def read_location_mapping(loc_map_file):
	location_mapping = {}
	f = open(loc_map_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next()
		for row in reader:
			# Mil/Sierra location => [Alma loc code, Alma call number type for loc]
			location_mapping[row[0].strip()] = [row[3].strip(),row[4].strip()]
		return location_mapping
	finally:
		f.close()



"""
	Read in status_map.csv and create map between old statuses and current base statuses, and description for note fields
"""
def read_status_mapping(status_map_file):
	status_mapping = {}
	f = open(status_map_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next()
		for row in reader:
			status_mapping[row[0].strip()] = [row[1].strip(),row[2].strip()]
		return status_mapping
	finally:
		f.close()


"""
	Read in itype_map.csv and create map between old itype values and current itype policy codes

"""
def read_itype_mapping(itype_map_file):
	itype_mapping = {}
	f = open(itype_map_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next()
		for row in reader:
			itype_mapping[row[0].strip()] = row[2].strip()
		return itype_mapping
	finally:
		f.close()


"""

"""
def set_fields(indices,row):
	if 'LOCATION' in indices:
		location = row[indices['LOCATION']]
	if 'BARCODE' in indices:
		barcode = row[indices['BARCODE']]
	if 'I TYPE' in indices:
		itype = row[indices['I TYPE']]
	if 'STATUS' in indices:
		status = row[indices['STATUS']]
	if 'CALL #(BIBLIO)' in indices:
		call_number = row[indices['CALL #(BIBLIO)']]
	if 'CREATED(ITEM)' in indices:
		created = row[indices['CREATED(ITEM)']]
	if 'UPDATED(ITEM)' in indices:
		updated = row[indices['UPDATED(ITEM)']]
	if 'FULFILMENT_NOTE' in indices:
		ful_note_1 = row[indices['FULFILMENT_NOTE']]
	if 'STAT_NOTE_1' in indices:				
		stat_note_1 = row[indices['STAT_NOTE_1']]
	if 'STAT_NOTE_2' in indices:
		stat_note_2 = row[indices['STAT_NOTE_2']]
	if 'STAT_NOTE_3' in indices:
		stat_note_3 = row[indices['STAT_NOTE_3']]
	if 'NON_PULIC_NOTE_1' in indices:
		int_note_1 = row[indices['NON_PUBLIC_NOTE_1']]
	if 'NON_PULIC_NOTE_2' in indices:
		int_note_2 = row[indices['NON_PUBLIC_NOTE_2']]
	if 'NON_PULIC_NOTE_3' in indices:
		int_note_3 = row[indices['NON_PUBLIC_NOTE_3']]

"""
	Read in item data in csv format (item_data.csv)
"""
def read_items(item_file):
	f  = open(item_file,'rt')
	try:
		reader = csv.reader(f)
		header = reader.next()
		indices = map_headers(header)
		for row in reader:
			oclc = '08387229' #row[1]
			# Check if bib record exists, based on OCLC number.  If it exists, get mms id  
			mms_id = find_mms_id(oclc)
			print mms_id
			if 'LOCATION' in indices:
				location = row[indices['LOCATION']]
			# Check if holding with same location as item exists.  If so, proceed to attach item
			holding_id = check_for_holdings(mms_id,location)
			# If holding doesn't already exist, create holding, then proceed to attach items
			if holding_id == 0:
				make_holding(mms_id)
			# create_item()
			print holding_id
			set_fields(indices,row)
	finally:
		f.close()

"""
	Set up item record CSV headers
"""


"""
	Maps authoritative headers to indices	
"""
def map_headers(header):
	index_map = {}
	field_map = read_mapping(get_field_mapping())
	print(field_map)
	position = 0
	for column in header:
		if column in field_map:
			index_map[field_map[column]] = position
		position += 1
	print(index_map)
	return index_map
		

"""
	Check if holding record exists
"""
def check_for_holdings(bib_mms_id,loc):
	holding_url = get_base_url() + '/bibs/' + str(bib_mms_id) + '/holdings?apikey=' + get_key()
	response = requests.get(holding_url)
	holdings = ET.fromstring(response.content)
	if response.status_code == 200:
		# Check if there are any holdings with a location match.  return holding mms_id if so
		for holding in holdings.findall("holding"):
			location = holding.find("location").text
			if location:
				# need to add a location mapping here. location_map(location)
				if location.strip() == loc.strip():
					return holding.find("holding_id").text
				else:
					return 0
			
""""
	Create holding record if it doesn't already exist
"""
def make_holding(bib_mms_id):
	post_url = get_base_url() + '/bibs/' + bib_mms_id + '/holdings?apikey=' + get_key()

"""
	Use SRU to find matching bib
"""
def find_mms_id(oclc):
	# set url and campus code from config later, and pass to function
	sru =  get_sru_base() + get_campus_code() + '?version=1.2&operation=searchRetrieve&query=alma.all_for_ui=' + oclc
	response = requests.get(sru)
	bib = ET.fromstring(response.content)
	if response.status_code == 200:
		for records in bib:
			for record in records:
				for recordData in record:
					for record in recordData:
						return record.find("./controlfield[@tag='001']").text



"""
	MAIN
	Check if item exists already in Alma
	If item doesn't exist, pull bib data based on OCLC number
	Create item and holding based on above mappings
	Send item XMl POST request to Alma 
"""

# set these in config file I think
mapping_file = sys.argv[3]
#location_file = sys.argv[2]
#status_file = sys.argv[3]
#itype_file = sys.argv[4]
items_file = sys.argv[2]

# read in and map all mappings. 
#field_mapping = read_mapping(mapping_file)
#print(field_mapping)
#auth_map = create_authoritative_mapping()
#location_mapping = read_location_mapping(location_file)
#print(location_mapping)
#status_mapping = read_status_mapping(status_file)
#print(status_mapping)
#itype_mapping = read_itype_mapping(itype_file)
#print(itype_mapping)
read_items(items_file)







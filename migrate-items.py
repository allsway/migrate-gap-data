#!/usr/bin/python
import requests
import sys
import csv
import ConfigParser
import xml.etree.ElementTree as ET

def createurl(row):
	bib_id = row[0]
	holding_id = row[1]
	item_id = row[2]
	return '/almaws/v1/bibs/' + bib_id + '/holdings/'+ holding_id +'/items/' + item_id; 
	

# Read campus configuration parameters
config = ConfigParser.RawConfigParser()
#config.read(sys.argv[1])
#apikey = config.get('Params', 'apikey')
#baseurl = config.get('Params','baseurl')
#campuscode =  config.get('Params', 'campuscode')

"""
	Set up authoritative mapping:
		the mapping between the 'expected' alma fields and the API fields that correspond. 
		This can be done in a static way, it won't change, only the mapping between the expected and the local field name is dynamic
"""



"""
	Read in field_mapping.csv and map all item fields to Alma fields
"""
def read_mapping (mapping_file):
	field_mapping = {}
	f = open(mapping_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next() #skip header line
		for row in reader:
			if row[1]:
				field_mapping[row[0]] = row[1]
		#print(field_mapping)
		return field_mapping
	finally:
		f.close()


"""
	Read in location_map.csv and create map between former locations and Alma locations
"""


"""
	Read in status_map.csv and create map between old statuses and current base statuses, and description for note fields
"""




"""
	Read in itype_map.csv and create map between old itype values and current itype policy codes

"""


"""
	MAIN
	Read in item data in csv format (item_data.csv)
	Check if item exists already in Alma
	If item doesn't exist, pull bib data based on OCLC number
	Create item and holding based on above mappings
	Send item XMl POST request to Alma 
"""

mapping_file = sys.argv[1]
field_mapping = read_mapping(mapping_file)
print(field_mapping)












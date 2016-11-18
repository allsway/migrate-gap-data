#!/usr/bin/python
import requests
import sys
import csv
import ConfigParser
import logging
import xml.etree.ElementTree as ET



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
	
def get_location_mapping():
	return config.get('Params', 'locationmap')
	
def get_status_mapping():
	return config.get('Params', 'statusmap')

def get_itype_mapping():
	return config.get('Params', 'itypemap')
	
	
def create_url(mms_id,holding_id):
	return get_base_url() +  '/bibs/' + mms_id + '/holdings/'+ holding_id +'/items?apikey=' + get_key(); 
		

"""
	Set up authoritative mapping:
		the mapping between the 'expected' alma fields and the API fields that correspond. 
		This can be done in a static way, it won't change, only the mapping between the expected and the local field name is dynamic
"""
def get_authoritative_mapping():
	dict = {
		'BARCODE':'barcode',
		'CREATED(ITEM)':'creation_date',
		'UPDATED(ITEM)':'modification_date',
		'STATUS':'base_status',
		'I TYPE':'policy',
		'VOLUME':'description',
		'oclc': 'oclc',
		'LOCATION':'location',
		'PIECES':'pieces',
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
	Mil/Sierra location => [Alma loc code, Alma Library, Alma call number type for loc]

"""
def read_location_mapping(loc_map_file):
	location_mapping = {}
	f = open(loc_map_file, 'rt')
	try:
		reader = csv.reader(f)
		reader.next()
		for row in reader:
			location_mapping[row[0].strip()] = {'location': row[3].strip(),'library': row[2].strip(), 'callnum' : row[4].strip()}
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
			status_mapping[row[0].strip()] = {'status_description': row[1].strip(),'base_status' : row[2].strip()}
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
	Posts complete XML to Alma, including bib_data, holding_data and item_data elements
"""
def post_item(item_url,item_xml):
	item = ET.Element('item')
	bib_data = ET.SubElement(item,'bib_data')
	bib_id = ET.SubElement(bib_data,'mms_id')
	bib_id.text = item_url.split("/")[6]
	holding_data = ET.SubElement(item,'holding_data')
	holding_id = ET.SubElement(holding_data,'holding_id')
	holding_id.text = item_url.split("/")[8]
	item.append(item_xml)
	print ET.tostring(item)
	headers = {"Content-Type": "application/xml"}
	r = requests.post(item_url,data=ET.tostring(item),headers=headers)
	print r.content


"""
	Read in item data in csv format (item_data.csv)
"""
def read_items(item_file):
	f  = open(item_file,'rt')
	try:
		reader = csv.reader(f)
		header = reader.next()
		indices = map_headers(header)
		itype_map = read_itype_mapping(get_itype_mapping())
		status_map = read_status_mapping(get_status_mapping())
		loc_row = read_location_mapping(get_location_mapping())
		for row in reader:
			item_url = create_bibs(row,indices,loc_row)
			if item_url:
				item_xml = make_item(row,indices,itype_map,status_map,loc_row)
				post_item(item_url,item_xml)
			else:
				logging.info("Failed to create holdings, current item URL: " + item_url)
	finally:
		f.close()

"""
	Get bib info and create/get holdings for the item we are adding to repository 
"""
def create_bibs(row,indices,loc_row):
	oclc =  row[indices['oclc']].strip()
	# Check if bib record exists, based on OCLC number.  If it exists, get mms id  
	mms_id = find_mms_id(oclc)
	if mms_id is not None:
		print mms_id
		if 'LOCATION' in indices:
			location = row[indices['LOCATION']].strip()
			holding_id = check_for_holdings(mms_id,loc_row[location])
		# If holding doesn't already exist, create holding
		if holding_id is None:
			holding_id = make_holding(mms_id,loc_row[location])
		print holding_id
		url = create_url(mms_id,holding_id)
		return url
	else:
		logging.info("Bib record with OCLC number " + oclc + " not currently in repository")


"""
	Create item_data xml content, based on mapping conditions.  
	Returns <item_data> Element
"""
def make_item(row,indices,itype_map,status_map,loc_map):
	mapping = get_authoritative_mapping()
	item = ET.Element('item_data')
	for key, value in mapping.iteritems():
		if key in indices:
			# exceptional mapping conditions
			if key == 'I TYPE':
				content = itype_map[row[indices[key]]]
			elif key == 'STATUS':
				content = status_map[row[indices[key]]]['base_status']
			elif key == 'LOCATION':
				content = loc_map[row[indices[key]].strip()]['location']
				library = ET.SubElement(item,'library')
				library.text = loc_map[row[indices[key]].strip()]['library']
			elif key == 'oclc':
				value = None
			elif key == 'NON_PUBLIC_NOTE_1' and row[indices['STATUS']]  != '-':
				content =  "Status: " + status_map[row[indices['STATUS']]]['status_description'] 
				if row[indices[key]]:
					content +=  " | " + row[indices[key]]
			else:
				content = row[indices[key]]
			element = ET.SubElement(item, value)
			element.text = content
	# also add physical_material_type in order to post item
	element = ET.SubElement(item,'physical_material_type')
	element.text = 'BOOK' # either map from ITYPE, try and get from bib or just set to default. 
	return item
	

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
				
	
		
""""
	Creates holding with the following XML structure
	<holding>
		<record>
			<datafield ind1='{call number type}' tag='852'>
				<subfield code='b'>{location}</subfield>
				<subfield code='c'>{library}</subfield>
			</datafield>
		</record>
	</holding>
	
	Returns holding XML 
"""
def get_holding_xml(loc_row):
	holding = ET.Element('holding')
	record = ET.SubElement(holding,'record')
	datafield = ET.SubElement(record,'datafield')
	datafield.set('ind1',loc_row['callnum'])
	datafield.set('tag','852')
	subfield1 = ET.SubElement(datafield,'subfield')
	subfield1.set('code','b')
	subfield1.text = loc_row['library']
	subfield2 = ET.SubElement(datafield,'subfield')
	subfield2.set('code','c')
	subfield2.text = loc_row['location']
	return holding


"""
	Creates post request with holding xml data to create new holding.  
	Returns holding MMS ID to be used for item creation
"""
def make_holding(bib_mms_id,loc_row):
	post_url = get_base_url() + '/bibs/' + str(bib_mms_id) + '/holdings?apikey=' + get_key()		
	headers = {"Content-Type": "application/xml"}
	holding = get_holding_xml(loc_row)
	print(ET.tostring(holding))
	r = requests.post(post_url,data=ET.tostring(holding),headers=headers)
	response = ET.fromstring(r.content)
	print(ET.tostring(response))
	if r.status_code == 200:
		return response.find("holding_id").text

			
	

"""
	Check if holding record exists
	Check if mapped location from current ILS to Alma location mapping matches with any current holdings
	Returns mms ID for holding if one exists
"""
def check_for_holdings(bib_mms_id,loc):
	holding_url = get_base_url() + '/bibs/' + str(bib_mms_id) + '/holdings?apikey=' + get_key()
	response = requests.get(holding_url)
	holdings = ET.fromstring(response.content)
	if response.status_code == 200:
		for holding in holdings.findall("holding"):
			location = holding.find("location").text
			if location:
				if location.strip() == loc['location'].strip():
					return holding.find("holding_id").text
				else:
					return None
			


"""
	Use SRU to find matching bib record based on OCLC number. 
	Returns MMS ID for the matching bib record. 
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

# Read campus configuration parameters
config = ConfigParser.RawConfigParser()
config.read(sys.argv[1])

logging.basicConfig(filename='status.log',level=logging.DEBUG)

items_file = sys.argv[2]
read_items(items_file)







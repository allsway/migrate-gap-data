#!/usr/bin/python
import requests
import sys
import re
import csv
import ConfigParser
import logging
import xml.etree.ElementTree as ET

"""
	Run as python ./migrate-items.py {config.txt} {item_data.csv}
	Takes in csv file of item data from Millennium or Sierra source system (could be modified to fit other source systems)
	Based on the field mapping form for your migration from Millennium/Sierra to Alma, maps the fields to the appropriate Alma fields
	Creates items and holdings for any items in the provided data file that don't exist in Alma. 
"""

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
	
"""
	Creates the Alma /items API link
"""	
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
		'STATUS':'base_status',
		'I TYPE':'policy',
		'VOLUME':'description',
		'COPY #':'copy_id',
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
	Maps authoritative headers to indices in delivered item CSV file	
"""
def map_headers(header):
	index_map = {}
	field_map = read_mapping(get_field_mapping())
	print(field_map)
	position = 0
	for column in header:
		if column in field_map:
			index_map[field_map[column]] = {'position' : position, 'itemheader' : column}
		position += 1
	return index_map


"""
	Check if the OCLC number is actually in the 035 field
	There are still some potential errors here, but there's not too much we can do about that. 
"""
def check_marc_field(oclc,r):
	fields = r.findall("./datafield[@tag='035']/subfield")
	for field in fields:
		print field.text
		if oclc in field.text:
			return True

"""
	Returns call number subfield from 050 field (could expand this to other call number fields)
"""
def get_call_num(r,subfield):
	if r.find("./datafield[@tag='050']/subfield[@code='"+ subfield +"']") is not None:
		return r.find("./datafield[@tag='050']/subfield[@code='" + subfield + "']").text

"""
	Use SRU to find matching bib record based on OCLC number. 
	Returns MMS ID for the matching bib record, and call number parts from the bib record. 
"""
def find_mms_id(oclc):
	sru =  get_sru_base() + get_campus_code() + '?version=1.2&operation=searchRetrieve&query=alma.all_for_ui=' + oclc
	response = requests.get(sru)
	if response.status_code != 200:
		logging.info("Failed to get response from SRU: " + sru)
		return None
	bib = ET.fromstring(response.content)
	bib_data = {}
	namespace = "{http://www.loc.gov/zing/srw/}"
	for record in bib.findall(namespace + "records/" + namespace + "record/" + namespace + "recordData/record"):
		if check_marc_field(oclc,record):
			bib_data['mms_id'] = record.find("./controlfield[@tag='001']").text
			bib_data['callnum_a'] = get_call_num(record,'a')
			bib_data['callnum_b']  = get_call_num(record,'b')
		else:
			logging.info("OCLC not found in 035 field: " + oclc)
	return bib_data


		
""""
	Creates holding with the following XML structure
	<holding>
		<record>
			<datafield ind1='{call number type}' tag='852'>
				<subfield code='b'>{location}</subfield>
				<subfield code='c'>{library}</subfield>
				<subfield code='h'>{call number subfield a}</subfield>
				<subfield code='i'>{call number subfield b}</subfield>
			</datafield>
		</record>
	</holding>
	
	Returns holding XML 
"""
def get_holding_xml(loc_row,bib_data):
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
	if bib_data['callnum_a']:
		subfield3 = ET.SubElement(datafield,'subfield')
		subfield3.set('code','h')
		subfield3.text = bib_data['callnum_a']
	if bib_data['callnum_b']:
		subfield4 = ET.SubElement(datafield,'subfield')
		subfield4.set('code','i')
		subfield4.text = bib_data['callnum_b']
	return holding

"""
	Check if holding record exists
	Check if mapped location from current ILS to Alma location mapping matches with any current holdings
	Returns mms ID for holding if one exists
"""
def check_for_holdings(bib_mms_id,loc):
	holding_url = get_base_url() + '/bibs/' + str(bib_mms_id) + '/holdings?apikey=' + get_key()
	response = requests.get(holding_url)
	holdings = ET.fromstring(response.content)
	if response.status_code != 200:
		logging.info("Failed to create/get holding for: " + holding_url)
		return None
	for holding in holdings.findall("holding"):
		location = holding.find("location").text
		if location:
			if location.strip() == loc['location'].strip():
				return holding.find("holding_id").text
			else:
				return None	

"""
	Creates post request with holding xml data to create new holding.  
	Returns holding MMS ID to be used for item creation
"""
def make_holding(bib_data,loc_row):
	post_url = get_base_url() + '/bibs/' + str(bib_data['mms_id']) + '/holdings?apikey=' + get_key()		
	print post_url
	headers = {"Content-Type": "application/xml"}
	holding = get_holding_xml(loc_row,bib_data)
	r = requests.post(post_url,data=ET.tostring(holding),headers=headers)
	response = ET.fromstring(r.content)
	if r.status_code == 200:
		return response.find("holding_id").text

"""
	Get bib info and gets (or creates) holdings for the item we are adding to repository 
"""
def get_holding(row,indices,loc_row):
	oclc =  row[indices['oclc']['position']].strip()
	oclc = re.sub("[^0-9]", "", oclc)
	print oclc
	bib_data = find_mms_id(oclc)
	if bib_data:
		mms_id = bib_data['mms_id']
		print mms_id
		if 'LOCATION' in indices:
			location = return_column_data(row,'LOCATION',indices)
			holding_id = check_for_holdings(mms_id,loc_row[location])
		# If holding doesn't already exist, create holding
		if holding_id is None:
			holding_id = make_holding(bib_data,loc_row[location])
		print holding_id
		url = create_url(mms_id,holding_id)
		return url
	else:
		logging.info("Bib record with OCLC number " + oclc + " not found in repository")



"""
	Check if item already exists in Alma, based on barcode
	This is a little superfluous - Alma won't let us create two items with the same barcode. 
"""
def check_item_exists(row,indices):
	barcode = return_column_data(row,'BARCODE',indices)
	sru =  get_sru_base() + get_campus_code() + '?version=1.2&operation=searchRetrieve&query=alma.all_for_ui=' + barcode
	response = requests.get(sru)
	bibs = ET.fromstring(response.content)
	num_recs = bibs.find("{http://www.loc.gov/zing/srw/}numberOfRecords").text	
	if num_recs == '0': 
		return False
	else:
		return True

"""
	Returns the data in the column 'column' for our row of data
"""
def return_column_data(row,column,indices):
	return row[indices[column]['position']].strip()

"""
	Create item_data xml content, based on mapping conditions.  
	Returns <item_data> Element
"""
def make_item(row,indices,itype_map,status_map,loc_map):
	mapping = get_authoritative_mapping()
	item = ET.Element('item_data')
	for key, value in mapping.iteritems():
		status_code = return_column_data(row,'STATUS',indices)
		content = ""
		if key == 'NON_PUBLIC_NOTE_3' and key not in indices:
			 content = 'migration note: tech_freeze_migration'
			 element = ET.SubElement(item, value)
			 element.text = content
		if key == 'NON_PUBLIC_NOTE_1' and key not in indices:
			if status_code:
				content = "Status: " + status_map[status_code]['status_description']
				element = ET.SubElement(item, value)
				element.text = content
		if key in indices:
			# exceptional mapping conditions
			column_data = return_column_data(row,key,indices)
			if key == 'I TYPE':
				content = itype_map[column_data]
			elif key == 'STATUS':
				content = status_map[column_data]['base_status']
			elif key == 'LOCATION':
				content = loc_map[column_data]['location']
				library = ET.SubElement(item,'library')
				library.text = loc_map[column_data]['library']
			elif key == 'oclc':
				value = None
			elif "note" in value:
				if column_data:
					content = indices[key]['itemheader'] + ": " +  column_data
			else:
				content = column_data
			if key == 'NON_PUBLIC_NOTE_1' and status_code != "-" :
				content = "Status: " + status_map[status_code]['status_description'] + " | " + content
			if key == 'NON_PUBLIC_NOTE_3':
				if return_column_data(row,'NON_PUBLIC_NOTE_3',indices):
					content += ' | migration note: tech_freeze_migration'
				else:
					content += 'migration note: tech_freeze_migration'
			element = ET.SubElement(item, value)
			element.text = content
	# also add physical_material_type in order to post item
	element = ET.SubElement(item,'physical_material_type')
	element.text = 'BOOK' # either map from ITYPE, try and get from bib or just set to default. 
	return item		
	
"""
	Posts complete item XML to Alma, including bib_data, holding_data and item_data elements
"""
def post_item(item_url,item_xml,copy_id):
	item = ET.Element('item')
	bib_data = ET.SubElement(item,'bib_data')
	bib_id = ET.SubElement(bib_data,'mms_id')
	bib_id.text = item_url.split("/")[6]
	holding_data = ET.SubElement(item,'holding_data')
	holding_id = ET.SubElement(holding_data,'holding_id')
	holding_id.text = item_url.split("/")[8]
	copy_num = ET.SubElement(holding_data,'copy_id')
	copy_num.text = copy_id
	item.append(item_xml)
	print ET.tostring(item)
	headers = {"Content-Type": "application/xml"}
	r = requests.post(item_url,data=ET.tostring(item),headers=headers)
	print r.content
	if r.status_code != 200:
		logging.info("Failed to create item for: " + item_url)
	
"""
	Reads in item data in csv format (item_data.csv), 
	Checks for the corresponding bib record, creates a holding record if no applicable holding record exists
	Creates item record using all mapped data
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
			item_exists = check_item_exists(row,indices)
			if not item_exists:
				item_url = get_holding(row,indices,loc_row)
				if item_url:
					item_xml = make_item(row,indices,itype_map,status_map,loc_row)
					copy_id = ""
					if row[indices['COPY #']['position']]:
						copy_id = row[indices['COPY #']['position']]
					post_item(item_url,item_xml,copy_id)
				else:
					logging.info("Failed to create holdings, current item: " + row[indices['BARCODE']['position']])
			else:
				logging.info("Item already exists in repository: " + row[indices['BARCODE']['position']])
	finally:
		f.close()


"""
	Read in configuration file and set up logging
	Call read_items() on the file of item records
"""

# Read campus configuration parameters
config = ConfigParser.RawConfigParser()
config.read(sys.argv[1])
logging.basicConfig(filename='status.log',level=logging.DEBUG)
items_file = sys.argv[2]

read_items(items_file)







# migrate-gap-data
Migrates new items created during the technical freeze period to Alma via the Alma APIs based on OCLC number bib record matchpoint

####Data input
* `item_map.csv`: field mapping csv file for item record fields.  Used to determine how to map fields from item_data.csv to Alma. 
* `item_data.csv`: complete cutover item records to be imported as new records to Alma (checking for duplicates is based on item barcode)
* `location_map.csv`: migration form mapping for locations in the item_data.csv file to the locations/libraries in Alma.
* `status_map.csv`: migration form mapping for item status in the item_data.csv file to the status in Alma. 
* `itype_map.csv`: migration form mapping for item type in item_data.csv file to the item policy in Alma. 

####Pre-requisite setup
Set up SRU integration profile in Alma for OCLC number bib lookup

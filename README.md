# migrate-gap-data
Migrates new items created during the technical freeze period to Alma via the Alma APIs based on OCLC number bib record matchpoint

####Data inputs defined in the config file
* `item_map.csv`: field mapping csv file for item record fields.  Used to determine how to map fields from item_data.csv to Alma. 
* `item_data.csv`: complete cutover item records to be imported as new records to Alma (checking for duplicates is based on item barcode)
* `location_map.csv`: migration form mapping for locations in the item_data.csv file to the locations/libraries in Alma.
* `status_map.csv`: migration form mapping for item status in the item_data.csv file to the status in Alma. 
* `itype_map.csv`: migration form mapping for item type in item_data.csv file to the item policy in Alma. 

####Pre-requisite setup
* Set up SRU integration profile in Alma for OCLC number bib lookup
* Add line `oclc,035|a` to the field mapping form file (item_map.csv in this example)

####config.txt file
In addition to the API, SRU and campus code information, the configuration file stores the data inputs listed above
```
[Params]
apikey: apikey 
baseurl: host
campuscode: campuscode
sru: base sru URL
fieldmap: path_to_data_inputs/item_field_map.csv
locationmap: path_to_data_inputs/location.csv
statusmap: path_to_data_inputs/status_map.csv
itypemap: path_to_data_inputs/itype_map.csv
```

####migrate-items.py
Takes as arguments:
- the configuration file as listed above
- a csv file of item records from the source system

Run as `python ./migrate-items.py {config.txt} {item_data.csv}`

Creates:
   - A holding record for every item in the CSV file (if the holding and item don't already exist in Alma)
   - An item record for every item in the CSV file, if the item barcode doesn't already exist in Alma
   - status.log file, recording any errors and any holdings/items that were not successfully created in Alma

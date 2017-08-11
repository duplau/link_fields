import logging, optparse
from gridder import *

OUTPUT_FIELDS = ['doc_id', 'label', 'grid', 'parent_grid', 'grid_label', 'grid_reason', 'city', 'country']
EXCLUDE_FR = False
ADD_VARIANT_WITHOUT_COUNTRY = False
ROTTEN_DOC_IDS = [ 355912 ]

def print_as_CSV(fields, row = None):
	print(';'.join(fields if row is None else [row[f] if f in row else '' for f in fields]))

def item_to_str(src_item):
	s = src_item['label']
	return src_item['parent_label'] + ' - ' + s if 'parent_label' in src_item else s

def gridded_count(src_items_by_label):
	return sum(['grid' in src_item or 'parent_grid' in src_item for src_item in src_items_by_label.values()])

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/grid_hal.log', level = logging.INFO)
	parser = optparse.OptionParser()
	parser.add_option("-x", "--exclude_fr", dest = "exclude_FR",
						help = "exclude French GRID entities")
	(options, args) = parser.parse_args()
	exclude_FR = options.exclude_FR

	country_syns = dict()
	with open('data/country_fr_en.csv') as countryFile:
		country_reader =  csv.DictReader(countryFile, delimiter = '|')
		for country_row in country_reader:
			country_fr = country_row['Pays']
			country_en = country_row['Country']
			country_syns[justCase(country_fr)] = country_en
			country_syns[justCase(country_en)] = country_en

	src_items_by_label = dict()
	token_count = Counter()
	with open('data/hal.csv') as srcFile:
		src_reader =  csv.DictReader(srcFile, delimiter = '\t', quotechar = '"')
		for srcRow in src_reader:
			label = srcRow['name_s']
			parent_label = srcRow['parentName_s']
			doc_id = srcRow['docid']
			if int(doc_id) in ROTTEN_DOC_IDS: continue
			tokens = validateTokens(parent_label) + validateTokens(label)
			countries = list()
			country_variant = list()
			for token in tokens:
				token_count[token] += 1
				if token in country_syns: 
					countries.append(country_syns[token])
				else:
					country_variant.append(token)
			src_item = dict( origin = SOURCE, label = label, doc_id = doc_id, tokens = tokens, variants = set([label]), acros = set() )
			if len(parent_label) > 0 and parent_label != label:
				src_item['parent_label'] = parent_label
				src_item['variants'].add(' '.join([parent_label, label]))
			if len(countries) > 0: 
				src_item['country'] = countries[0]
				if ADD_VARIANT_WITHOUT_COUNTRY:
					src_item['variants'].add(' '.join(country_variant))
			acronym = srcRow['acronym_s']
			if len(acronym) > 0:
				src_item['acronym'] = acronym
			enrich_item_with_variants(src_item)
			src_items_by_label[label] = src_item

	ref_item_by_grid = dict()
	grids_by_token = defaultdict(set)
	with open('data/grid.csv') as refFile:
		ref_reader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for refRow in ref_reader:
			label = refRow['Name']
			tokens = validateTokens(label)
			grid = refRow['ID']
			country = refRow['Country']
			city = refRow['City']
			if exclude_FR and country == 'France': continue
			ref_item = dict( origin = REFERENCE, country = country, city = city, label = label, labels = dict(), grid = grid, variants = set([label]), acros = set(), aliases = set(), children = set() )
			if len(country) > 0:
				ref_item['variants'].add(' '.join([label, country]))
			if len(city) > 0 and len(country) > 0:
				ref_item['variants'].add(' '.join([label, city, country]))
			state = refRow['State']
			if len(city) > 0 and len(country) > 0 and len(state) > 0:
				ref_item['variants'].add(' '.join([label, city, state, country]))
			enrich_item_with_variants(ref_item)
			ref_item_by_grid[grid] = ref_item
			for token in tokens: 
				grids_by_token[token].add(grid)
			if len(ref_item_by_grid) % 1000 == 0: logging.warning('Pre-processed {} reference entries'.format(len(ref_item_by_grid)))
	with open('data/grid_aliases.csv') as alias_file:
		aliases_reader = csv.DictReader(alias_file, delimiter = ',', quotechar = '"')
		for alias_row in aliases_reader:
			grid = alias_row['grid_id']
			if grid not in ref_item_by_grid: continue
			ref_item_by_grid[grid]['aliases'].add(alias_row['alias'])
	with open('data/grid_labels.csv') as labels_file:
		labels_reader = csv.DictReader(labels_file, delimiter = ',', quotechar = '"')
		for label_row in labels_reader:
			grid = label_row['grid_id']
			if grid not in ref_item_by_grid: continue
			ref_item_by_grid[grid]['labels'][label_row['iso639']] = label_row['label']
	with open('data/grid_acronyms.csv') as acronyms_file:
		acronyms_reader = csv.DictReader(acronyms_file, delimiter = ',', quotechar = '"')
		for acronym_row in acronyms_reader:
			grid = acronym_row['grid_id']
			if grid not in ref_item_by_grid: continue
			ref_item_by_grid[grid]['acronym'] = acronym_row['acronym']
	with open('data/grid_links.csv') as links_file:
		links_reader = csv.DictReader(links_file, delimiter = ',', quotechar = '"')
		for link_row in links_reader:
			grid = link_row['grid_id']
			if grid not in ref_item_by_grid: continue
			ref_item_by_grid[grid]['url'] = link_row['link']
	with open('data/grid_relationships.csv') as rels_file:
		rels_reader = csv.DictReader(rels_file, delimiter = ',', quotechar = '"')
		for rel_row in rels_reader:
			grid = rel_row['grid_id']
			rel_grid = rel_row['related_grid_id']
			if grid not in ref_item_by_grid or rel_grid not in ref_item_by_grid: continue
			if rel_row['relationship_type'] == 'Child':
				ref_item_by_grid[grid]['children'].add(rel_grid)
				ref_item_by_grid[rel_grid]['parent'] = grid
			elif rel_row['relationship_type'] == 'Parent':
				ref_item_by_grid[rel_grid]['children'].add(grid)
				ref_item_by_grid[grid]['parent'] = rel_grid
	unmatched_src_labels = set()
	for (src_label, src_item) in src_items_by_label.items():
		candidate_grids = set()
		for token in sorted(src_item['tokens'], key = lambda t: token_count[t], reverse = True)[:8]:
			newGrids = candidate_grids | grids_by_token[token]
			if len(newGrids) > 32: break
			candidate_grids = newGrids
		logging.debug('Source label "{}": found {} candidates'.format(item_to_str(src_item), len(candidate_grids)))
		if len(candidate_grids) < 1: 
			continue
		candidate = sorted([(grid, score_items(src_item, ref_item_by_grid[grid])) for grid in candidate_grids], key = lambda p: p[1][0], reverse = True)[0]
		score = candidate[1][0]
		if score > 0: 
			grid = candidate[0]
			reason = candidate[1][1]
			ref_label = ref_item_by_grid[grid]['label']
			logging.info('Match found for src item "{}": "{}" ({}) <-- {}'.format(item_to_str(src_item), ref_label, score, reason))
			src_item['grid'] = grid
			src_item['grid_reason'] = reason
		else:
			logging.info('No match found for src item "{}"'.format(item_to_str(src_item)))
			unmatched_src_labels.add(src_label)

	logging.warning('==> now {} gridded entities'.format(gridded_count(src_items_by_label)))

	logging.warning('Matching unmatched src labels...')
	attached_parent_grid_count = 0
	src_items_index = dict()
	for (src_label, src_item) in src_items_by_label.items():
		src_items_index[src_label] = src_item
		if 'acronym' in src_item: src_items_index[src_item['acronym']] = src_item
	for src_label in unmatched_src_labels:
		src_item = src_items_by_label[src_label]
		if 'parent_label' not in src_item: continue
		parent_label = src_item['parent_label']
		if parent_label in src_items_index:
			if grid in src_items_index[parent_label]:
				logging.info('Attaching grid of matched parent "{}" to child "{}"'.format(parent_label, item_to_str(src_item)))
				src_item['grid'] = src_items_index[parent_label]['grid']
				attached_parent_grid_count += 1
			else:
				logging.info('Unmatched parent "{}" of child "{}"'.format(parent_label, item_to_str(src_item)))
		else:
			logging.warning('Parent "{}" of child "{}" not found!'.format(parent_label, item_to_str(src_item)))
	logging.warning('Matched {} unmatched src labels  ==> now {} gridded entities'.format(attached_parent_grid_count, gridded_count(src_items_by_label)))

	logging.warning('Checking parent-child relationships...')
	added_parent_grid_count = 0
	for (src_label, src_item) in src_items_by_label.items():
		if 'grid' in src_item:
			ref_item = ref_item_by_grid[src_item['grid']]
			if 'parent' in ref_item:
				parent_item = ref_item_by_grid[ref_item['parent']]
				logging.info('Adding "{}" parent grid of "{}"'.format(parent_item['label'], item_to_str(src_item)))
				src_item['parent_grid'] = parent_item['grid']
				added_parent_grid_count += 1
	logging.warning('Added {} parent grids ==> now {} gridded entities'.format(added_parent_grid_count, gridded_count(src_items_by_label)))

	logging.warning('Trying prefix matching...')
	added_prefix_grid_count = 0
	for (src_label, src_item) in src_items_by_label.items():
		if 'grid' in src_item: continue
		label = stripped(src_label)
		i = label.rfind(' ')
		while i > 0:
			label = stripped(label[:i])
			if label in src_items_by_label and 'grid' in src_items_by_label[label]:
				logging.info('Adding "{}" prefix as parent grid of "{}"'.format(label, src_items_by_label[label]['label']))
				src_item['parent_grid'] = src_items_by_label[label]['grid']
				src_item['grid_reason'] = 'Matching label prefix "{}" / parent label {}'.format(label,  item_to_str(src_item))
				added_prefix_grid_count += 1
				break
			i = label.rfind(' ')
	logging.warning('Added {} prefix/parent grids ==> now {} gridded entities'.format(added_prefix_grid_count, gridded_count(src_items_by_label)))

	logging.warning('Post-processing gridded entries...')
	print_as_CSV(OUTPUT_FIELDS)
	for (src_label, src_item) in src_items_by_label.items():
		ref_item = ref_item_by_grid[src_item['grid']] if 'grid' in src_item else ref_item_by_grid[src_item['parent_grid']] if 'parent_grid' in src_item else None
		if ref_item is not None:
			src_item['city'] = ref_item['city']
			src_item['country'] = ref_item['country']
			src_item['grid_label'] = ref_item['label']
			print_as_CSV(OUTPUT_FIELDS, src_item)

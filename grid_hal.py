import logging, optparse
from gridder import *

EXCLUDE_FR = True

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/grid_hal.log', level = logging.INFO)
	parser = optparse.OptionParser()
	parser.add_option("-x", "--exclude_fr", dest = "exclude_FR",
						help = "exclude French GRID entities")
	(options, args) = parser.parse_args()
	exclude_FR = options.exclude_FR
	src_items_by_label = dict()
	ref_item_by_grid = dict()
	grids_by_token = defaultdict(set)
	token_count = Counter()
	with open('data/hal.csv') as srcFile:
		src_reader =  csv.DictReader(srcFile, delimiter = '\t', quotechar = '"')
		for srcRow in src_reader:
			label = srcRow['label_s']
			doc_id = srcRow['docid']
			tokens = validateTokens(label)
			for token in tokens: token_count[token] += 1
			src_items_by_label[label] = dict( origin = SOURCE, label = label, doc_id = doc_id, tokens = tokens, variants = set([label]), acros = set() )
	with open('data/grid.csv') as refFile:
		ref_reader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for refRow in ref_reader:
			label = refRow['Name']
			tokens = validateTokens(label)
			grid = refRow['ID']
			if exclude_FR and refRow['Country'] == 'France': continue
			ref_item_by_grid[grid] = dict( origin = REFERENCE, label = label, grid = grid, variants = set([label]), acros = set() )
			for token in tokens: 
				grids_by_token[token].add(grid)
			if len(ref_item_by_grid) % 1000 == 0: logging.info('Pre-processed {} reference entries'.format(len(ref_item_by_grid)))
	for item in src_items_by_label.values():
		enrich_item_with_variants(item)
	for item in ref_item_by_grid.values():
		enrich_item_with_variants(item)
	print('\t'.join(['HAL Label', 'GRID Label', 'GRID']))
	for (srcLabel, src_item) in src_items_by_label.items():
		candidate_grids = set()
		for token in sorted(src_item['tokens'], key = lambda t: token_count[t], reverse = True)[:8]:
			newGrids = candidate_grids | grids_by_token[token]
			if len(newGrids) > 32: break
			candidate_grids = newGrids
		logging.info('Source label "{}": found {} candidates'.format(srcLabel, len(candidate_grids)))
		if len(candidate_grids) < 1: 
			continue
		candidate = sorted([(grid, score_items(src_item, ref_item_by_grid[grid])) for grid in candidate_grids], key = lambda p: p[1], reverse = True)[0]
		grid = candidate[0]
		score = candidate[1]
		ref_label = ref_item_by_grid[grid]['label']
		logging.info('Best candidate : "{}" ({})'.format(ref_label, score))
		if candidate[1] > 0: 
			docid = src_item['doc_id']
			print('\t'.join([docid, srcLabel, ref_label, grid]))

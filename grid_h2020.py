import logging
from munkres import Munkres
from gridder import *

MODE_BASIC = False

def best_candidate(srcItem, refItems, top_n): return best_candidates(srcItem, refItems)[0]

def best_candidates(srcItem, refItems, top_n = None):
	best_list = sorted([(refItem['grid'], score_items(srcItem, refItem)) for refItem in refItems], key = lambda p: p[1], reverse = True)
	return best_list if top_n is None else best_list[:top_n]

def pick_best(candidates, grid_counts, excluded_grids):
	if len(candidates) < 1: return None
	for c in candidates:
		if grid_counts[c[0]] < 2: return c
	return candidates[0] if c[0] not in excluded_grids else None

def pick_basic_candidate(src_items, ref_item_by_grid, grids_by_token, grid_counts, candidates_by_src_label):
	excluded_grids = set()
	for src_item in src_items:
		src_label = src_item['label']
		candidate =  pick_best(candidates_by_src_label[src_label], grid_counts, excluded_grids)
		if candidate is None: 
			logging.info('No candidate for {}'.format(src_label))
			continue
		grid = candidate[0]
		if grid_counts[grid] > 1:
			excluded_grids.add(grid)
		score = candidate[1]
		ref_label = ref_item_by_grid[grid]['label']
		logging.info('Best candidate for {}: "{}" ({})'.format(src_label, ref_label, score))
		if candidate[1] > 0: 
			print('\t'.join([key, src_label, ref_label, grid]))

def empty_matrix(m, n, init_value = 0): return [ [init_value] * n for _ in range(m) ]

def hungarian(matrix):
	mrs = Munkres()
	indexes = mrs.compute(matrix)
	return indexes # Array of (row, column)

def pick_hungarian_candidate(src_items, ref_item_by_grid, grid_counts, candidates_by_src_label):
		m = len(src_items)
		ref_grids = list(grid_counts.keys())
		n = len(ref_grids)
		matrix = empty_matrix(m, n, 100)
		for i, src_item in enumerate(src_items):
			src_label = src_item['label']
			for candidate in candidates_by_src_label[src_label]:
				score = candidate[1]
				if score < 1: continue
				j = ref_grids.index(candidate[0])
				matrix[i][j] -= score
		indexes = hungarian(matrix)
		for (i, j) in indexes:
			src_label = src_items[i]['label']
			grid = ref_grids[j]
			ref_label = ref_item_by_grid[grid]['label']
			score = 100 - matrix[i][j]
			if score < 1: continue
			print('\t'.join([key, src_label, ref_label, grid, str(score)]))

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/grid_h2020.log', level = logging.INFO)
	country_codes = countryToCodeMap()
	src_blocks = defaultdict(list)
	token_count = Counter()
	src_labels = set()
	with open('data/h2020_ascii.csv') as srcFile: # h2020_participants_public.csv
		srcReader =  csv.DictReader(srcFile, delimiter = ';', quotechar = '"')
		for srcRow in srcReader:
			src_label = srcRow['LB_LEGAL_NAME']
			if src_label in src_labels: continue
			src_labels.add(src_label)
			key = makeKey(srcRow['CD_ORG_COUNTRY'], srcRow['LB_ORG_CITY'])
			tokens = validateTokens(src_label)
			for token in tokens: token_count[token] += 1
			src_item = dict( origin = SOURCE, label = src_label, tokens = tokens, variants = set([src_label]), acros = set() )
			enrich_item_with_variants(src_item)
			src_blocks[key].append(src_item)
	ref_blocks = defaultdict(list)
	ref_item_by_grid = dict()
	grids_by_token = defaultdict(set)
	ref_labels = set()
	with open('data/grid_ascii.csv') as refFile:
		ref_reader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for ref_row in ref_reader:
			ref_label = ref_row['Name']
			if ref_label in ref_labels: continue
			ref_labels.add(ref_label)
			grid = ref_row['ID']
			tokens = validateTokens(ref_label)
			for token in tokens: 
				grids_by_token[token].add(grid)
			key = makeKey(country_codes[ref_row['Country']] if ref_row['Country'] in country_codes else None, ref_row['City'])
			refItem = dict( origin = REFERENCE, label = ref_label, grid = grid, variants = set([ref_label]), acros = set() )
			ref_item_by_grid[grid] = refItem
			enrich_item_with_variants(refItem)
			ref_blocks[key].append(refItem)
	print('\t'.join(['Location', 'H2020 Label', 'GRID Label', 'GRID']))
	for (key, src_items) in src_blocks.items():
		refs = None
		if key in ref_blocks: 
			refs = ref_blocks[key]
		else:
			logging.warning('No reference block found for source block {}!'.format(key))
			i = key.find('/')
			if i >= 0:
				key0 = key[:i]
				if key0 in ref_blocks:
					refs = ref_blocks[key0]
					logging.info('Fallback on sub-block {}'.format(key0))
				else:
					logging.warning('No reference block found for source sub-block {}!'.format(key0))
		if refs is None: continue
		logging.info('Processing block {}: {} src items, {} ref items'.format(key, len(src_items), len(refs)))
		candidates_by_src_label = defaultdict(list)
		grid_counts = Counter()
		for src_item in src_items:
			src_label = src_item['label']
			candidate_grids = set()
			for token in sorted(src_item['tokens'], key = lambda t: token_count[t], reverse = True)[:8]:
				newGrids = candidate_grids | grids_by_token[token]
				if len(newGrids) > 32: break
				candidate_grids = newGrids
			if len(candidate_grids) < 1: 
				continue
			candidates = sorted([(grid, score_items(src_item, ref_item_by_grid[grid])) for grid in candidate_grids], key = lambda p: p[1], reverse = True)
			candidates_by_src_label[src_label] = candidates
			for candidate in candidates:
				grid_counts[candidate[0]] += 1
		if MODE_BASIC:
			pick_basic_candidate(src_items, ref_item_by_grid, grids_by_token, grid_counts, candidates_by_src_label)
		else:
			pick_hungarian_candidate(src_items, ref_item_by_grid, grid_counts, candidates_by_src_label)

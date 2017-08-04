import logging
from gridder import *

def bestCandidateScore(src, ref, variants):
	return max([scoreStrings(a, b) for a in variants[src] for b in variants[ref]])

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/grid_hal.log', level = logging.DEBUG)
	countryCodes = countryToCodeMap()
	srcLabels = dict()
	docIdByLabel = dict()
	tokenCount = Counter()
	variants = defaultdict(set)
	with open('data/hal.csv') as srcFile:
		srcReader =  csv.DictReader(srcFile, delimiter = '\t', quotechar = '"')
		for srcRow in srcReader:
			label = srcRow['label_s']
			tokens = validateTokens(label)
			for token in tokens: tokenCount[token] += 1
			srcLabels[srcRow['label_s']] = tokens
			docIdByLabel[srcRow['label_s']] = srcRow['docid']
	gridByToken = defaultdict(set)
	labelByGrid = dict()
	with open('data/grid.csv') as refFile:
		refReader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for refRow in refReader:
			label = refRow['Name']
			tokens = validateTokens(label)
			grid = refRow['ID']
			labelByGrid[grid] = label
			for token in tokens: gridByToken[token].add(grid)
			if len(labelByGrid) % 1000 == 0: logging.info('Pre-processed {} entries'.format(len(labelByGrid)))
	for main in set(labelByGrid.values()) | set(srcLabels.keys()):
		variants[main].add(main)
		for variant in extractAcronyms(main):
			variants[main].add(variant)
	print('\t'.join(['HAL Label', 'GRID Label', 'GRID']))
	for (srcName, tokens) in srcLabels.items():
		# srcLabel['sig'] = sorted(srcLabel['tokens'], key = lambda t: tokenCount[t], reverse = True)[:5]
		candidateGrids = set()
		for token in sorted(tokens, key = lambda t: tokenCount[t], reverse = True)[:8]:
			newGrids = candidateGrids | gridByToken[token]
			if len(newGrids) > 32: break
			candidateGrids = newGrids
		logging.debug('Source label "{}": found {} candidates'.format(srcName, len(candidateGrids)))
		if len(candidateGrids) < 1: 
			continue
		candidate = sorted([(grid, scoreStrings(srcName, labelByGrid[grid])) for grid in candidateGrids], key = lambda p: p[1], reverse = True)[0]
		grid = candidate[0]
		score = candidate[1]
		logging.debug('Best candidate : "{}" ({})'.format(labelByGrid[grid], score))
		if candidate[1] > 0: 
			docid = docIdByLabel[srcName]
			print('\t'.join([docid, srcName, labelByGrid[grid], grid]))

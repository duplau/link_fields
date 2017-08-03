import logging
from gridder import *

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/grid_h2020.log', level = logging.DEBUG)
	# Block rows by country
	countryCodes = countryToCodeMap()
	srcBlocks = defaultdict(set)
	with open('data/h2020.csv') as srcFile: # h2020_participants_public.csv
		srcReader =  csv.DictReader(srcFile, delimiter = ';', quotechar = '"')
		for srcRow in srcReader:
			key = makeKey(srcRow['CD_ORG_COUNTRY'], srcRow['LB_ORG_CITY'])
			srcBlocks[key].add(srcRow['LB_LEGAL_NAME'])

	refBlocks = defaultdict(set)
	GIDs = dict()
	with open('data/grid.csv') as refFile: # grid_public.csv
		refReader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for refRow in refReader:
			key = makeKey(countryCodes[refRow['Country']] if refRow['Country'] in countryCodes else None, refRow['City'])
			refBlocks[key].add(refRow['Name'])
			GIDs[refRow['Name']] = refRow['ID']
	selectedPairs = []
	for key in sorted(srcBlocks.keys(), key = lambda k: len(srcBlocks[k]), reverse = True):
		# Find closest neighbor
		srcNames = srcBlocks[key]
		if key not in refBlocks: continue
		refs = refBlocks[key]
		print('## Pays: {}'.format(key))
		unmatched = list()
		matched = dict()
		ambiguous = defaultdict(list)
		refOccurrences = Counter()
		matches = defaultdict()
		for srcName in srcNames:
			closestRefs = difflib.get_close_matches(srcName, refs, n = 10, cutoff = 0.6) if len(refs) > 0 else []
			matches[srcName] = set(closestRefs)
			for ref in closestRefs: refOccurrences[ref] += 1
		for ref, cnt in refOccurrences.items():
			if cnt < 2: continue 
			logging.debug('Discarding ambiguous reference {}'.format(ref))
			for closestRefs in matches.values(): closestRefs.discard(ref)
		for srcName, closestRefs in matches.items():
			if len(closestRefs) < 1: 
				unmatched.append(srcName)
				continue
			# For every source with a best candidate, we validate that candidate:
			# - first by computing an absolute match length (in  characters, 6) and a relative match length (20% of total after excluding stop-words) 
			#   and marking the candidate pair as included if above a threshold
			# - then by testing for an acronym pattern in either direction (ideally when the expanded variant is the reference we would like to exclude ambiguous acronyms)
			# - if neither has passed, the candidate pair is marked as excluded
			else:
				candidate = sorted([(refName, checkCandidate(srcName, refName)) for refName in closestRefs], key = lambda p: p[1], reverse = True)[0]
				if candidate[1] > 0: 
					print ('Candidate for {}: {}'.format(srcName, candidate))
					selectedPairs.append((srcName, candidate[0]))
	print('|'.join(['', 'H2020', 'GRID', '']))
	print('|'.join(['', '-', '-', '']))
	for (src, ref) in selectedPairs: 
		print('|'.join(['', src, ref, '']))
	print()			

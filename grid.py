import csv, unicodedata, difflib, functools, logging, re
from collections import defaultdict, Counter
from fuzzywuzzy import fuzz

# $ egrep -v -i "Ltd|Consultant|Limited|Corp|Inc" data/grid.csv > data/grid_public.csv

def acronymizeTokens(tokens, minAcroSize = 3, maxAcroSize = 7):
	for s in range(max(minAcroSize, len(tokens)), min(maxAcroSize, len(tokens)) + 1):
		tl = tokens[:s]
		yield (''.join([t[0] for t in tl]).upper(), tl)

def acronymizePhrase(phrase, keepAcronyms = True): 
	tokens = validateTokens(phrase, keepAcronyms)
	return acronymizeTokens(tokens)

ACRO_PATTERNS = ['[{}]', '({})']
def findValidAcronyms(phrase):
	for acro in acronymizePhrase(phrase, True):
		if any([phrase.find(ap.format(acro)) >=0 for ap in ACRO_PATTERNS]): 
			yield acro

def extractAcronyms(phrase):
	for acro in acronymizePhrase(phrase, True):
		for ap in ACRO_PATTERNS:
			substring = ap.format(acro)
			i = phrase.find(substring)
			if i >=0:
				yield acro
				yield phrase[:i] + phrase[i + len(substring):]

def isStopWord(word): return word in STOP_WORDS

def isValidPhrase(tokens): return len(tokens) > 0 and not all(len(t) < 2 and t.isdigit() for t in tokens)

def stripped(s): return s.strip(" -_.,'?!").strip('"').strip()

def isValidToken(token, minLength = 2):
	token = stripped(token)
	if token.isspace() or not token: return False
	if token.isdigit(): return False # Be careful this does not get called when doing regex or template matching!
	if len(token) <= minLength and not (token.isalpha() and token.isupper()): return False
	return not isStopWord(token)

def isValidValue(v):
	''' Validates a single value (sufficient non-empty data and such things) '''
	stripped = stripped(v)
	return len(stripped) > 0 and stripped not in ['null', 'NA', 'N/A']

def isAcroToken(token):
	return re.match("[A-Z][0-9]*$", token) or re.match("[A-Z0-9]+$", token)

MIN_ACRO_SIZE = 3
MAX_ACRO_SIZE = 6

def lowerOrNot(token, keepAcronyms, keepInitialized = False):
	''' Set keepAcronyms to true in order to improve precision (e.g. a CAT scan will not be matched by a kitty). '''
	if keepAcronyms and len(token) >= MIN_ACRO_SIZE and len(token) <= MAX_ACRO_SIZE and isAcroToken(token):
		return token
	if keepInitialized:
		m = re.search("([A-Z][0-9]+)[^'a-zA-Z].*", token)
		if m:
			toKeep = m.group(0)
			return toKeep + lowerOrNot(token[len(toKeep):], keepAcronyms, keepInitialized)
	return token.lower()

def toASCII(phrase): return unicodedata.normalize('NFKD', phrase)

def caseToken(t, keepAcronyms = False): return toASCII(lowerOrNot(t.strip(), keepAcronyms))

def replaceBySpace(str, *patterns): return functools.reduce(lambda s, p: re.sub(p, ' ', s), patterns, str)

def dehyphenateToken(token):
	result = token[:]
	i = result.find('-')
	while i >= 0 and i < len(result) - 1:
		left = result[0:i]
		right = result[i+1:]
		if left.isdigit() or right.isdigit(): break
		result = left + right
		i = result.find('-')
	return result.strip()

def preSplit(v):
	s = ' ' + v.strip() + ' '
	s = replaceBySpace(s, '[\{\}\[\](),\.\"\';:!?&\^\/\*-]')
	return re.sub('([^\d\'])-([^\d])', '\1 \2', s)

def justCase(phrase, keepAcronyms = False):
	return caseToken(preSplit(phrase), keepAcronyms)

def splitAndCase(phrase, keepAcronyms = False):
	return map(lambda t: caseToken(t, keepAcronyms), str.split(preSplit(phrase)))

def validateTokens(phrase, keepAcronyms = False, tokenValidator = functools.partial(isValidToken, minLength = 2), phraseValidator = isValidPhrase):
	if phrase:
		tokens = splitAndCase(phrase, keepAcronyms)
		validTokens = []
		for token in tokens:
			if tokenValidator(token): validTokens.append(token)
		if phraseValidator(validTokens): return validTokens
	return []

def normalizeAndValidatePhrase(value,
	keepAcronyms = False, tokenValidator = functools.partial(isValidToken, minLength = 2), phraseValidator = isValidPhrase):
	''' Returns a string that joins normalized, valid tokens for the input phrase
		(None if no valid tokens were found) '''
	tokens = validateTokens(value, keepAcronyms, tokenValidator, phraseValidator)
	return ' '.join(tokens) if len(tokens) > 0 else None


def allStopWords():
	for lg in ['en', 'fr', 'es', 'de', 'it']: 
		STOP_WORDS |= set([caseToken(t) for t in fileToList(fileName)])

def stripped(s): return s.strip(" -_.,'?!").strip('"').strip()

def fileRowIterator(filePath, sep):
	with open(filePath, mode = 'r') as csvfile:
		reader = csv.reader(csvfile, delimiter = sep, quotechar='"')
		for row in reader:
			try:
				yield list(map(stripped, row))
			except UnicodeDecodeError as ude:
				logging.error('Unicode error while parsing "%s"', row)

def fileToVariantMap(fileName, sep = '|', includeSelf = False):
	''' The input format is pipe-separated, column 1 is the main variant, column 2 an alternative variant.

		Returns a reverse index, namely a map from original alternative variant to original main variant

		Parameters:
		includeSelf if True, then the main variant will be included in the list of alternative variants
			(so as to enable partial matching simultaneously).
	'''
	otherToMain = defaultdict(list)
	mainToOther = defaultdict(list)
	for r in fileRowIterator(fileName, sep):
		if len(r) < 2: continue
		main, alts = r[0], r[1:]
		for alt in alts: otherToMain[alt].append(main)
		mainToOther[main].extend(alts)
	l = list([(other, next(iter(main))) for (other, main) in otherToMain.items() if len(main) < 2])
	if includeSelf: l = list([(main, main) for main in mainToOther.keys()]) + l
	return dict(l)


STOP_WORDS = set([
	# Prepositions (excepted "avec" and "sans" which are semantically meaningful)
	"a", "au", "aux", "de", "des", "du", "par", "pour", "sur", "chez", "dans", "sous", "vers",
	# Articles
	"le", "la", "les", "l", "c", "ce", "ca",
	 # Conjonctions of coordination
	"mais", "et", "ou", "donc", "or", "ni", "car",
])

NON_DISCRIMINATING_TOKENS = map(splitAndCase, [
	# EN
	'University', 'Hospital', 'Department', 'Agency', 'Institute', 'College', 'Faculty', 'Authority', 'Academy', 'Department', 'Center', 'Centre', 'School'
	# DE
	'Klinikum', 'Hochschule', 'Fachhochschule',
	# IT
	'Istituto', 'Regione', 'Comune', 'Centro',
	# ES
	'Universidad', 'Agencia', 'Servicio', 'Conselleria', 'Museo',
	# PL
	'Uniwersytet', 'Centrum', 'Akademia'
])

def makeKey(country, city): 
	return caseToken(country) if country else ''

def countryToCodeMap():
	with open('data/country_name_code.csv') as f:
		reader = csv.reader(f, delimiter = ',')
		return dict([(row[0], 'UK' if row[1] == 'GB' else row[1]) for row in reader])

def lowerOrNot(token, keepAcronyms = False, keepInitialized = False):
	''' Set keepAcronyms to true in order to improve precision (e.g. a CAT scan will not be matched by a kitty). '''
	if keepAcronyms and len(token) >= MIN_ACRO_SIZE and len(token) <= MAX_ACRO_SIZE and isAcroToken(token):
		return token
	if keepInitialized:
		m = re.search("([A-Z][0-9]+)[^'a-zA-Z].*", token)
		if m:
			toKeep = m.group(0)
			return toKeep + lowerOrNot(token[len(toKeep):], keepAcronyms, keepInitialized)
	return token.lower()

def toASCII(phrase): return unicodedata.normalize('NFKD', phrase)

# A map from alt variant to main variant 
SYNMAP = fileToVariantMap('data/synonyms')

def normalize(t): 
	s = caseToken(t)
	for variant, main in SYNMAP.items():
		s = s.replace(variant, main)
	return s

def checkCandidate(src, ref):
	a = stripped(src)
	b = stripped(ref)
	a1 = acronymizePhrase(a)
	b1 = acronymizePhrase(b)
	if a1 == b.upper() or a.upper() == b1:
		logging.debug('Accepted for ACRO : {} / {}'.format(a, b))
		return 100
	absCharRatio = fuzz.ratio(a, b)
	if absCharRatio < 20: 
		logging.debug('Rejected for ABS : {} / {}'.format(a, b))
		return 0
	partialCharRatio = fuzz.partial_ratio(a, b)
	if partialCharRatio < 30: 
		logging.debug('Rejected for PARTIAL : {} / {}'.format(a, b))
		return 0
	a2 = ' '.join(filter(lambda t: t not in NON_DISCRIMINATING_TOKENS, validateTokens(src)))
	b2 = ' '.join(filter(lambda t: t not in NON_DISCRIMINATING_TOKENS, validateTokens(ref)))
	tokenSortRatio = fuzz.token_sort_ratio(a2, b2)
	if tokenSortRatio < 40: 
		logging.debug('Rejected for TOKEN_SORT : {} / {}'.format(a, b))
		return 0
	tokenSetRatio = fuzz.token_set_ratio(a2, b2)
	if tokenSetRatio < 50:
		logging.debug('Rejected for TOKEN_SET : {} / {}'.format(a, b))
		return 0
	s = max(absCharRatio, partialCharRatio, tokenSortRatio, tokenSetRatio)
	return s if s > 80 else 0

CONFIGS = {
	
	'h2020': (
		['CD_ORG_COUNTRY', 'LB_ORG_CITY'], # Block key field(s)
		'LB_LEGAL_NAME', # Source label field
		),
	'hal': (
		)
}

DATASET = 'hal'

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/griddr.log', level = logging.DEBUG)
	# Block rows by country
	countryCodes = countryToCodeMap()
	srcBlocks = defaultdict(set)
	if DATASET == 'h2020':
		with open('data/h2020.csv') as srcFile: # h2020_participants_public.csv
			srcReader =  csv.DictReader(srcFile, delimiter = ';', quotechar = '"')
			for srcRow in srcReader:
				key = makeKey(srcRow['CD_ORG_COUNTRY'], srcRow['LB_ORG_CITY'])
				srcBlocks[key].add(srcRow['LB_LEGAL_NAME'])
	elif DATASET == 'hal':
		with open('data/hal.csv') as srcFile:
			srcReader =  csv.DictReader(srcFile, delimiter = '\t', quotechar = '"')
			for srcRow in srcReader:				
				srcBlocks[''].add(srcRow['label_s'])

	refBlocks = defaultdict(set)
	GIDs = dict()
	with open('data/grid.csv') as refFile: # grid_public.csv
		refReader =  csv.DictReader(refFile, delimiter = ',', quotechar = '"')
		for refRow in refReader:
			if DATASET == 'h2020':
				key = makeKey(countryCodes[refRow['Country']] if refRow['Country'] in countryCodes else None, refRow['City'])
			elif DATASET == 'hal':
				key = ''
			refBlocks[key].add(refRow['Name'])
			GIDs[refRow['Name']] = refRow['ID']
	selectedPairs = []
	for key in sorted(srcBlocks.keys(), key = lambda k: len(srcBlocks[k]), reverse = True):
		# Find closest neighbor
		srcNames = srcBlocks[key]
		if key not in refBlocks: continue
		refs = refBlocks[key]
		print('## Key: {}'.format(key))
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
				print ('Candidate for {}: {}'.format(srcName, candidate))
				if candidate[1] > 0: selectedPairs.append((srcName, candidate[0]))
	print('|'.join(['', 'Source', 'GRID', '']))
	print('|'.join(['', '-', '-', '']))
	for (src, ref) in selectedPairs: 
		print('|'.join(['', src, ref, '']))
	print()			

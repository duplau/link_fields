import csv, unicodedata, difflib, functools, logging, re, os, sys
from collections import defaultdict, Counter
from fuzzywuzzy import fuzz
import enchant

SOURCE = 1
REFERENCE = 2

REQUIRES_SHARED_PROPER_NOUN = True
DICTS = [ enchant.Dict("en_US") ]
RESOURCE_PATH = 'resource'

# $ egrep -v -i "Ltd|Consultant|Limited|Corp|Inc" data/grid.csv > data/grid_public.csv

def acronymizeTokens(tokens, minAcroSize = 3, maxAcroSize = 7):
	for s in range(max(minAcroSize, len(tokens)), min(maxAcroSize, len(tokens)) + 1):
		tl = tokens[:s]
		yield (''.join([t[0] for t in tl]).upper(), tl)

def acronymizePhrase(phrase, keepAcronyms = True): 
	tokens = validateTokens(phrase, keepAcronyms)
	return list(acronymizeTokens(tokens))

ACRO_PATTERNS = ['[{}]', '({})']
def findValidAcronyms(phrase):
	for acro in acronymizePhrase(phrase, True):
		if any([phrase.find(ap.format(acro)) >=0 for ap in ACRO_PATTERNS]): 
			yield acro

def enrich_item_with_variants(item):
	for (acro, variant) in extractAcronymsByColocation(item['label']):
		item['variants'].add(variant)
		item['acros'].add(acro)

def extractAcronymsByConstruction(phrase):
	for acro in acronymizePhrase(phrase, True):
		for ap in ACRO_PATTERNS:
			substring = ap.format(acro)
			i = phrase.find(substring)
			if i >=0:
				yield (acro, phrase[:i] + phrase[i + len(substring):])

def extractAcronymsByColocation(phrase):
	ms = re.findall('\b\[([\s0-9A-Z/]+)\]\b', phrase)
	if not ms: return
	for m in ms:
		yield (m.group(1), phrase[:m.start()])

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

def toASCII(string):
	string = re.sub(u"[àáâãäå]", 'a', string)
	string = re.sub(u"[èéêë]", 'e', string)
	string = re.sub(u"[ìíîï]", 'i', string)
	string = re.sub(u"[òóôõö]", 'o', string)
	string = re.sub(u"[ùúûü]", 'u', string)
	string = re.sub(u"[ýÿ]", 'y', string)
	return string

# def toASCII(phrase): return unicodedata.normalize('NFKD', phrase).encode('ascii')

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


def fileToList(fileName, path = RESOURCE_PATH): 
	filePath = fileName if path is None else os.path.join(path, fileName)
	with open(filePath, mode = 'r') as f: 
		return [justCase(line) for line in f]

FRENCH_WORDS = set(fileToList('liste_mots_fr.col'))

STOP_WORDS = set([
	# Prepositions (excepted "avec" and "sans" which are semantically meaningful)
	"a", "au", "aux", "de", "des", "du", "par", "pour", "sur", "chez", "dans", "sous", "vers",
	# Articles
	"le", "la", "les", "l", "c", "ce", "ca",
	 # Conjonctions of coordination
	"mais", "et", "ou", "donc", "or", "ni", "car",
])

NON_DISCRIMINATING_TOKENS = list([justCase(t) for t in [
	# FR
	'Société', 'Université', 'Unité', 'Pôle',
	# EN
	'University', 'Hospital', 'Department', 'Agency', 'Institute', 'College', 'Faculty', 'Authority', 'Academy', 'Department', 'Center', 'Centre', 'School'
	# DE
	'Klinikum', 'Hochschule', 'Fachhochschule',
	# IT
	'Istituto', 'Regione', 'Comune', 'Centro',
	# ES
	'Universidad', 'Agencia', 'Servicio', 'Conselleria', 'Museo', 'Fundacion',
	# PL
	'Uniwersytet', 'Centrum', 'Akademia'
]])

TRANSLATIONS = {
	'University': ['Université', 'Universidad', 'Universität', 'Universitat'],
	'Hospital': ['Hôpital'],
	'Agency': ['Agence', 'Agencia'],
	'City': ['Commune', 'Comune'],
	'Clinic': ['Clinique', 'Klinikum'],
	'Academy': ['Académie', 'Akademia'],
	'Institute': ['Institut', 'Instituto', 'Istituto', 'Instytut'],
	'Center': ['Centre', 'Centrum', 'Zentrum'],
	'Association': ['Asociacion'],
	'Society': ['Société', 'Societa', 'Gesellschaft'],
	'Development': ['Développement'],
	'Consulting': ['Conseil'],
	'Foundation': ['Fundacion', 'Fondation'],
	'European': ['Européen'],
	'Technology': ['Technologie'],
	'Systems': ['Systèmes'],
	'Industrial': ['Industriel', 'Industrie', 'Industrial'],
	'Research': ['Recherche'],
	'Energy': ['Energie', 'Energia', 'Power'],
	'Organization': ['Ograniczona']
}

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

def filterProperNouns(it):
	return filter(lambda t: len(t) > 2 and t not in FRENCH_WORDS  and t not in NON_DISCRIMINATING_TOKENS and not any([d.check(t) for d in DICTS]), it)

def scoreStrings(src, ref):
	a0 = stripped(src)
	b0 = stripped(ref)
	a1 = acronymizePhrase(a0)
	b1 = acronymizePhrase(b0)
	if len(a1) > 0 and len(b1) > 0 and (a1 == b0.upper() or a0.upper() == b1):
		logging.debug('Accepted for ACRO : {} / {}'.format(a, b))
		return 100
	a = justCase(src)
	b = justCase(ref)
	absCharRatio = fuzz.ratio(a, b)
	if absCharRatio < 20: 
		logging.debug('Rejected for ABS : {} / {}'.format(a, b))
		return 0
	partialCharRatio = fuzz.partial_ratio(a, b)
	if partialCharRatio < 30: 
		logging.debug('Rejected for PARTIAL : {} / {}'.format(a, b))
		return 0
	aTokens = validateTokens(src)
	bTokens = validateTokens(ref)
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
	if REQUIRES_SHARED_PROPER_NOUN:
		aProper = ' '.join(filterProperNouns(aTokens))
		bProper = ' '.join(filterProperNouns(bTokens))
		if(len(aProper) > 3 and len(bProper) > 3):
			properNounSortRatio = fuzz.token_sort_ratio(aProper, bProper)
			if properNounSortRatio < 10: 
				logging.debug('Rejected for PROPER_NOUN_SORT : {} / {}'.format(a, b))
				return 0
			properNounSetRatio = fuzz.token_set_ratio(aProper, bProper)
			if properNounSetRatio < 20:
				logging.debug('Rejected for PROPER_NOUN_SET : {} / {}'.format(a, b))
				return 0
	s = (absCharRatio * partialCharRatio * tokenSortRatio**2 * tokenSetRatio**3) / 100**6
	return s if s > 60 else 0

def score_items(src, ref):
	score_str = max([scoreStrings(a, b) for a in src['variants'] for b in ref['variants']]) if 'variants' in src and 'variants' in ref else 0
	score_acro = max([fuzz.ratio(a, b) for a in src['acro'] for b in ref['acro']]) if 'acro' in src and 'acro' in ref else 0
	score_country = 50
	if 'country' in src and 'country' in ref:
		score_country = 100 if fuzz.ratio(src['country'], ref['country']) > 80 else 0
	score_city = 50
	if 'city' in src and 'city' in ref:
		score_city = 100 if fuzz.ratio(src['city'], ref['city']) > 80 else 0
	return (max(score_str, score_acro) * score_country * score_city) / 100**2

if __name__ == '__main__':
	logging.basicConfig(filename = 'log/gridder.log', level = logging.DEBUG)
	phrases = sys.argv[1:3]
	print('Score:', scoreStrings(phrases[0], phrases[1]))

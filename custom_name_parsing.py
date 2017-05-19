#!/usr/bin/env python3
# coding=utf-8

import re, unicodedata
from collections import defaultdict
from functools import reduce

# Natural language toolbox and lexical stuff: FRENCH ONLY!!!

STOP_WORDS = [
	# Prepositions (excepted "avec" and "sans" which are semantically meaningful)
	"a", "au", "aux", "de", "des", "du", "par", "pour", "sur", "chez", "dans", "sous", "vers", 
	# Articles
	"le", "la", "les", "l", "c", "ce", "ca", 
	 # Conjonctions of coordination
	"mais", "et", "ou", "donc", "or", "ni", "car"
]

def isStopWord(word): return word in STOP_WORDS

# Utilities

def replaceBySpace(str, *patterns): return reduce(lambda s, p: re.sub(p, ' ', s), patterns, str)

def toASCII(phrase): return unicodedata.normalize('NFKD', phrase)

def preSplit(v):
	s = ' ' + v.strip() + ' '
	s = replaceBySpace(s, '[\{\}\[\](),\.\"\';:!?&\^\/\*-]')
	return re.sub('([^\d\'])-([^\d])', '\1 \2', s)

def splitAndCase(phrase):
	return list([caseToken(t) for t in str.split(preSplit(phrase))])

def validateTokens(phrase, isFirst):
	if phrase:
		tokens = splitAndCase(phrase)
		validTokens = []
		for token in tokens:
			valid = isValidFirstnameToken(token) if isFirst else isValidSurnameToken(token)
			if valid: validTokens.append(token)
		if len(validTokens) > 0 and len(validTokens) == len(tokens): return validTokens
	return []

def isValidSurnameToken(token):
	token = stripped(token)
	if token.isspace() or not token: return False
	if token.isdigit(): return False
	if len(token) <= 2 and not (token.isalpha() and token.isupper()): return False
	return not isStopWord(token)

def isValidFirstnameToken(token):
	token = stripped(token)
	if token.isspace() or not token: return False
	return not token.isdigit()

def normalizeAndValidatePhrase(phrase, isFirst):
	tokens = validateTokens(phrase, isFirst)
	if len(tokens) > 0:
		isValid = (len(tokens) == 1 or all([len(t) == 1 for t in tokens])) if isFirst else ((len(tokens) == 1 and len(tokens[0]) == 1) or all([len(t) > 1 for t in tokens]))
		if isValid: return ' '.join(tokens)
	return None

def caseToken(t): return toASCII(t.strip().lower())

def validatedLexiconMap(lexicon, isFirst, tokenize = False): 
	''' Returns a dictionary from normalized string to list of original strings. '''
	lm = defaultdict(list)
	for s in lexicon:
		k = normalizeAndValidatePhrase(s, isFirst) if tokenize else caseToken(s)
		if k is None: continue
		lm[k].append(s)
	return lm

#####

def stripped(s): return s.strip(" -_.,'?!").strip('"').strip()
def fileToList(fileName): 
	with open(fileName, mode = 'r') as f: 
		return [stripped(line) for line in f]
def fileToSet(fileName): return set(fileToList(fileName))

# Custom parsing of person names

F_FIRST = u'Prénom'
F_LAST = u'Nom'
F_TITLE = u'Titre'
F_FIRSTORLAST = F_FIRST + '|' + F_LAST

PRENOM_LEXICON = fileToSet('resource/prenom')
PATRONYME_LEXICON = fileToSet('resource/patronyme_fr')

FR_FIRSTNAMES = set([s.lower() for s in PRENOM_LEXICON])
FR_SURNAMES = set([s.lower() for s in PATRONYME_LEXICON])

PN_STRIP_CHARS = ' <>[](){}"\''
PN_DELIMITERS = ',;+/'
FN_INITIAL_SEPS = '-.'
FN_COMP_DELIMITER = '-'

TITLE_MONSIEUR = 'M.'
PN_TITLE_VARIANTS = {
	TITLE_MONSIEUR: ['mr', 'monsieur', 'mister', 'sir'], # Form "M." is handled separately
	'Mme': ['mme', 'mrs', 'madame', 'madam', 'ms', 'miss'],
	'Dr': ['dr', 'docteur', 'doctor'],
	'Pr': ['pr', 'professeur', 'prof', 'professor']
}

def splitAndKeepDelimiter(s, delimiter):
    return reduce(lambda l, e: l[:-1] + [l[-1] + e] if e == delimiter else l + [e], re.split("(%s)" % re.escape(delimiter), s), [])

def nameTokenizer(s, isFirst):
	for token in s.split():
		for t1 in splitAndKeepDelimiter(token, '-') if isFirst else [token]:
			for t2 in splitAndKeepDelimiter(t1, '.'):
				if t2 not in FN_INITIAL_SEPS: yield t2

def joinChoices(s): 
	l = list(s)
	if len(l) < 1: return None
	return l[0] + ('({})'.format(' or '.join(l[1:])) if len(l) > 1 else '')

def joinPersonName(d):
	l = [joinChoices([ln.upper() for ln in d[F_LAST]])]
	if F_FIRST in d and len(d[F_FIRST]) > 0: l = [joinChoices([fn.capitalize() + ('.' if len(fn) == 1 else '') for fn in d[F_FIRST]])] + l
	if F_TITLE in d and len(d[F_TITLE]) > 0: l = [d[F_TITLE]] + l
	return ' '.join(l)

def extractPersonNames(l):
	for d in PN_DELIMITERS[1:]:
		cs = l.split(d)
		if len(cs) > 1 and any([PN_DELIMITERS[0] in c for c in cs]):
			return extractPersonNames(PN_DELIMITERS[0].join([' '.join(reversed(c.split(PN_DELIMITERS[0]))) for c in cs]))
	s = re.sub(r'[\b\s](et|and|&)[\b\s]', PN_DELIMITERS[0], l, flags=re.IGNORECASE)
	s0 = s.translate({ PN_STRIP_CHARS: None })
	print('s0', s0)
	for d in PN_DELIMITERS:
		(s1, s2, s3) = s0.partition(d)
		if len(s2) == 1: 
			if d not in s1 + s3:
				a1, b3 = extractAnyFirstName(s1), extractLastName(s3)
				if a1 and b3: 
					print('a1, b3', a1, b3)
					return [{ F_FIRST: set([a1]), F_LAST: set([b3]) }]
				b1, a3 = extractLastName(s1), extractAnyFirstName(s3)
				if b1 and a3: 
					print('b1, a3', b1, a3)
					return [{ F_FIRST: set([a3]), F_LAST: set([b1]) }]
			l1, l3 = extractPersonNames(s1), extractPersonNames(s3)
			if len(l1) + len(l3) > 0: return l1 + l3
	return personNameSingleton(s0)

def personNameSingleton(s): 
	d = extractPersonName(s)
	return [] if d is None else [d]

def isInitial(name): 
	# return len(s) == 1 or (len(s) == 2 and s[1] in FN_INITIAL_SEPS)
	return not all([(len(s) == 1 or (len(s) == 2 and s[1] in FN_INITIAL_SEPS)) for s in nameTokenizer(name, True)])

def appendFirst(firstComps, alternating, fis, d, i, t):
	if (isInitial(t) and not all([isInitial(firstComp[1]) for firstComp in firstComps])) or (not isInitial(t) and all([isInitial(firstComp[1]) for firstComp in firstComps])):
		recordFirst(firstComps, alternating, fis, d)
	firstComps.append((i, t))

def recordFirst(firstComps, alternating, fis, d):
	if len(firstComps) < 1: return
	elif len(firstComps) == 1: 
		fp = firstComps[0]
		fst = fp[1]
		d[F_FIRST].add(fst)
		fis.add((fp[0], fp[0]))
		d[F_FIRSTORLAST].add(fst)
		alternating.append((1, fst))
	else:
		fst = FN_COMP_DELIMITER.join([firstComp[1] for firstComp in firstComps])
		d[F_FIRST].add(fst)
		fis.add((firstComps[0][0], firstComps[-1][0]))

		# TODO this was added
		# d[F_FIRSTORLAST].add(fst)

		alternating.append((0, fst))
	firstComps.clear()

LABELS_MAP = validatedLexiconMap(PRENOM_LEXICON, True)

def extractFirstName(s):
	v = normalizeAndValidatePhrase(s, True)
	return v if (v is not None and v in LABELS_MAP) else None

def extractAnyFirstName(s):
	tokens = list(nameTokenizer(s, True))
	comps = list()
	for s in tokens:
		if s[-1] in FN_INITIAL_SEPS:
			t = s.strip(FN_INITIAL_SEPS)
			# if t.isalpha() and t != TITLE_MONSIEUR[:-1]: comps.append(t)
			if t.isalpha(): comps.append(t)
		else:
			t0 = s.strip(FN_INITIAL_SEPS)
			if len(t0) > 1:
				t = t0.lower()
				# if t in FR_FIRSTNAMES: comps.append(t)
				comps.append(t)
	if len(comps) > 0:
		skipped = len(comps) < len(tokens)
		isValid = len(comps) == 1 or (all([len(t) == 1 for t in comps]) and not skipped)
		if isValid: return '-'.join(comps)
	return None

def extractLastName(s):
	return normalizeAndValidatePhrase(s, False)

def extractPersonName(s):
	d = defaultdict(set)
	# Set of first-name (start token, end token) pairs representing the spans 
	fis = set() 
	tokens = list(nameTokenizer(s, True))
	print('tokens', tokens)
	firstComps = list()
	# List of pairs (kind, component) where kind is 0 for a first-name component, 1 for first or surname, 2 for surname
	alternating = list() 
	firstDone, lastDone = False, False
	for i, token in enumerate(tokens):
		if token[-1] in FN_INITIAL_SEPS:
			t = token.strip(FN_INITIAL_SEPS)
			if not t.isalpha(): continue
			if i == 0 and t == TITLE_MONSIEUR[:-1]: d[F_TITLE] = TITLE_MONSIEUR
			if not firstDone: appendFirst(firstComps, alternating, fis, d, i, t.lower())
			elif not lastDone: d[F_LAST].add(t.lower())
			continue
		t0 = token.strip(FN_INITIAL_SEPS)
		if len(t0) < 2: continue
		t = t0.lower()
		title = None
		for (main, variants) in PN_TITLE_VARIANTS.items():
			if t0[1:].islower() and t in [v.lower() for v in variants]:
				title = main
				break
		if title: 
			recordFirst(firstComps, alternating, fis, d)
			d[F_TITLE].add(title)
			continue
		if t in FR_FIRSTNAMES:
			appendFirst(firstComps, alternating, fis, d, i, t)
			firstDone = True
		else:
			t1 = t.strip(FN_INITIAL_SEPS)
			recordFirst(firstComps, alternating, fis, d)
			d[F_LAST].add(t)
			lastDone = True
			alternating.append((2, t))
	recordFirst(firstComps, alternating, fis, d)
	if len(d[F_LAST]) < 1:
		if len(d[F_FIRSTORLAST]) > 0:
			d[F_LAST] = d[F_FIRSTORLAST] - d[F_FIRST]
			d[F_FIRST] = d[F_FIRST] - d[F_LAST] # noLastAsFirstComponent(d, F_FIRST)
			d[F_FIRSTORLAST] = d[F_LAST] - d[F_FIRST]
	if len(d[F_FIRST]) > 1 or len(d[F_LAST]) > 1:
		# FIXME unstack sequence if it's first/last-alternating...
		pass
	if len(d[F_LAST]) < 1:
		for candidates in candidatesList(tokens, fis, d):
			if len(candidates) > 0: 
				d[F_LAST].add(sorted(candidates, key = lambda c: len(c), reverse = True)[0])
				break
	if len(d[F_LAST]) < 1:
		pickBestFirstAsLast(d)
	if len(d[F_LAST]) < 1: return None
	if len(d[F_FIRST]) < 1:
		d[F_FIRST] = d[F_FIRSTORLAST] - d[F_LAST] # noLastAsFirstComponent(d, F_FIRSTORLAST)
	if F_FIRSTORLAST in d: del d[F_FIRSTORLAST]
	if TITLE_MONSIEUR[:-1] in d[F_FIRST]: del d[F_TITLE]
	noLastAsFirstComponent(d)
	for ln in d[F_LAST]:
		d[F_LAST] = set([norm(ln) for ln in d[F_LAST]])
	return d

def pickBestFirstAsLast(d):
	if len(d[F_FIRST]) == 1:
		fn = list(d[F_FIRST])[0]
		if not isInitial(fn):
			d[F_LAST].add(fn)
			d[F_FIRST].remove(fn)
	elif len(d[F_FIRST]) > 1:
		bestLNs = sorted([fn for fn in d[F_FIRST] if fn.lower() not in FR_FIRSTNAMES], key = lambda s: len(s), reverse = True)
		if len(bestLNs) > 0:
			d[F_LAST].add(bestLNs[0])
			d[F_FIRST].remove(bestLNs[0])

def noLastAsFirstComponent(d):
	toRemove = set()
	toAdd = set()
	for fn in d[F_FIRST]:
		firstComps = norm(fn).split(FN_COMP_DELIMITER)
		firstComps0 = set(firstComps) & set([norm(ln) for ln in d[F_LAST]])
		if len(firstComps0) > 0:
			toRemove.add(fn)
			toAdd.add(FN_COMP_DELIMITER.join([c for c in firstComps if norm(c) not in firstComps0]))
	d[F_FIRST] -= toRemove
	d[F_FIRST] |= toAdd

def norm(c): return c.strip('-.,').upper()

def noFirstAsLast(token, d): return not any([norm(token).find(norm(fn)) >= 0 for fn in d[F_FIRST]])

def candidatesList(allTokens, fis, d):
	tokens = [t.strip(FN_INITIAL_SEPS) for t in allTokens]
	# Start with neighbors of the first name token matches
	yield set(filter(lambda token: noFirstAsLast(token, d), [tokens[fi[0] - 1] for fi in fis if fi[0] > 0]))
	yield set(filter(lambda token: noFirstAsLast(token, d), [tokens[fi[1] + 1] for fi in fis if fi[1] < len(tokens) - 1]))
	# Then prioritize upper-case tokens not included in any first name
	yield set(filter(lambda token: len(token) > 2 and token.isupper() and noFirstAsLast(token, d), tokens))
	# Then capitalized tokens not included in any first name
	yield set(filter(lambda token: len(token) > 2 and token.capitalize() == token and noFirstAsLast(token, d), tokens))

	# Then relax first-name constraint to full string comparison
	yield set(filter(lambda token: len(token) > 2 and token.isupper() and not any([token == fn.upper() for fn in d[F_FIRST]]), tokens))
	yield set(filter(lambda token: len(token) > 2 and token.capitalize() == token and not any([token == fn.capitalize() for fn in d[F_FIRST]]), tokens))

	# Then neglect casing...
	yield set(filter(lambda token: len(token) > 2 and not any([token.upper() == fn.upper() for fn in d[F_FIRST]]), tokens))

# Top-level parsing methods

def customParsePersonNamesAsStrings(l): return map(joinPersonName, extractPersonNames(l))

MD_OUTPUT_MAX = 3

def printCustomParsePersonNamesAsHeader(): 
	print('## Résultats de normalisation de noms de personnes')
	print('')
	print('|{}|'.format('|'.join(['Source'] + ['Nom #' + str(i + 1) for i in range(MD_OUTPUT_MAX)])))
	print('|{}|'.format('|'.join('-' * (MD_OUTPUT_MAX + 1))))

def printCustomParsePersonNamesAsMd(l): 
	ls = list(customParsePersonNamesAsStrings(l))
	print('|{}|'.format('|'.join([l] + ls[:3])))

if __name__ == '__main__':
	printCustomParsePersonNamesAsHeader()
	for (src, refs) in [
		('Abdellah Bounfour, Kamal Naït-Zerrad et Abdallah Boumalk', [('Abdellah', 'Bounfour'), ('Kamal', 'Naït-Zerrad'), ('Abdallah', 'Boumalk')]),
		# ('Schreck E., Gontier L. and Treilhou M.', [('E.', 'Schreck'), ('L.', 'Gontier'), ('M.', 'Treilhou')]),
		# ('L. Jutier, C. Léonard and F. Gatti.', [('L.', 'Jutier'), ('C.', 'Léonard'), ('F.', 'Gatti.')]),
		# ('Véronique Wester-Ouisse', [('Véronique', 'Wester-Ouisse')]),
		# ('Justine, J.-L.', [('Justine', 'J.-L.')]),
		# ('Adolphe L.', [('L.', 'Adolphe')]),
		# ('Pierre-André MIMOUN', [('Pierre-André', 'MIMOUN')]),
		# ('Pierre-André mimoun', [('Pierre-André', 'MIMOUN')]),
		# ('Alain Schnapp', [('Alain', 'Schnapp')]),
		# ('Schnapp Alain', [('Alain', 'Schnapp')]),
		# ('BADIE Bertrand', [('Bertrand', 'BADIE')]),
		# ('BAKHOUCHE Béatrice', [('Béatrice', 'BAKHOUCHE')]),
		# ('Emmanuel WALLON (sous la direction de)', [('Emmanuel', 'WALLON')]),
		# ('Charles-Edmond BICHOT', [('Charles-Edmond', 'BICHOT')]),
		# ('Sylvie Neyertz et David Brown', [('Sylvie', 'Neyertz'), ('David', 'Brown')]),
		# ('Anne-Dominique Merville & Antoine COPPOLANI', [('Anne-Dominique', 'Merville'), ('Antoine', 'COPPOLANI')]),
		# ('J.P. Poly', [('J.P.', 'Poly')]),
		# ('Dominique Kalifa', [('Dominique', 'Kalifa')]),
		# ('S. CHAKER (Dir.)', [('S.', 'CHAKER')]),
		# ('Thibault, André', [('André', 'Thibault')])
	 ]:
	 	printCustomParsePersonNamesAsMd(src)
	# with open('test_data/person_names.to_normalize', mode = 'r') as f: 
	# 	for line in f:
	# 		printCustomParsePersonNamesAsMd(stripped(line))			

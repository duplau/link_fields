#!/usr/bin/env python3
# coding=utf-8

import csv, sys, re, optparse

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

MIN_ACRO_SIZE = 3
MAX_ACRO_SIZE = 6
def lowerOrNot(token, keepAcronyms, keepInitialized = False):
	''' Set keepAcronyms to true in order to improve precision (e.g. a CAT scan will not be matched by a kitty). '''
	if keepAcronyms and len(token) >= MIN_ACRO_SIZE and len(token) <= MAX_ACRO_SIZE and (re.match("[A-Z][0-9]*$", token) or re.match("[A-Z0-9]+$", token)): 
		return token
	if keepInitialized:
		m = re.search("([A-Z][0-9]+)[^'a-zA-Z].*", token)
		if m:
			toKeep = m.group(0)
			return toKeep + lowerOrNot(token[len(toKeep):], keepAcronyms, keepInitialized)
	return token.lower()

def toASCII(phrase):
	return phrase.encode('ASCII', 'ignore')

def caseToken(t, keepAcronyms): return toASCII(lowerOrNot(t.strip(), keepAcronyms))

def replaceBySpace(str, *patterns): return reduce(lambda s, p: re.sub(p, ' ', s), patterns, str)

def stripped(s): return s.strip(" -_.,'?!").strip('"').strip()

def isValidToken(token):
	token = stripped(token)
	if token.isspace() or not token: return False
	if token.isdigit(): return False # Be careful this does not get called when doing regex or template matching!
	if len(token) <= 2 and not (token.isalpha() and token.isupper()): return False
	return not isStopWord(token)

def isValidPhrase(tokens): return len(tokens) > 0 and not all([len(t) < 2 and t.isdigit() for t in tokens])

def preSplit(v):
	s = ' ' + v.strip() + ' '
	s = replaceBySpace(s, '[\{\}\[\](),\.\"\';:!?&\^\/\*-]')
	return re.sub('([^\d\'])-([^\d])', '\1 \2', s)

def splitAndCase(phrase, keepAcronyms):
	return map(lambda t: caseToken(t, keepAcronyms), str.split(preSplit(phrase)))

def validateTokens(phrase, keepAcronyms, tokenValidator, phraseValidator):
	if phrase:
		tokens = splitAndCase(phrase, keepAcronyms)
		validTokens = []
		for token in tokens:
			if tokenValidator(token): validTokens.append(token)
		if phraseValidator(validTokens): return validTokens 
	return []

def normalizeAndValidateTokens(value, keepAcronyms = False, tokenValidator = isValidToken, phraseValidator = isValidPhrase):
	''' Returns a list of normalized, valid tokens for the input phrase (an empty list if no valid tokens were found) '''
	return validateTokens(value, keepAcronyms, tokenValidator, phraseValidator)

def normalizeAndValidatePhrase(value, keepAcronyms = False, tokenValidator = isValidToken, phraseValidator = isValidPhrase):
	''' Returns a string that joins normalized, valid tokens for the input phrase (None if no valid tokens were found) '''
	tokens = normalizeAndValidateTokens(value, keepAcronyms, tokenValidator, phraseValidator)
	return ' '.join(tokens) if len(tokens) > 0 else None

########################################################################################

def compactifySyns(merger):

	reader = csv.reader(sys.stdin, delimiter = '|', quotechar='"')
	writer = csv.writer(sys.stdout, delimiter = '|')
	lastMain = (None, None)
	for row in reader:
		vs = [normalizeAndValidatePhrase(v.replace('"', '')) for v in row]
		if len(vs) < 1 or vs[0] is None: continue
		mainKey = merger(vs[0])
		if mainKey != lastMain[0]:
			lastMain = (mainKey, row[0])
		for v in row[1:]: writer.writerow([lastMain[1], v])

def mergerByTokenList(v1): return ' '.join(v1)

def mergerByTokenSet(v1): return set(v1)

if __name__ == '__main__':
	reload(sys)  
	sys.setdefaultencoding('utf8')
	parser = optparse.OptionParser()
	parser.add_option("-s", "--sets", dest = "sets", action = "store_true", default = False,
					  help = "merge when token sets as equal (as opposed to - sorted - token lists)")
	(options, args) = parser.parse_args()
	merger = mergerByTokenSet if options.sets else mergerByTokenList
	compactifySyns(merger)

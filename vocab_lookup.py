#!/usr/bin/python
# coding=utf-8
import re, csv, functools, itertools, operator, unicodedata
from collections import defaultdict
from tinyfss import FastSS
from fuzzywuzzy import fuzz, process

DO_NOT_FOLD = ["^([A-Z0-9]*)$", "^([A-Z0-9]*)[^'a-zA-Z]", " ([A-Z0-9]*)[^'a-zA-Z]", " ([A-Z0-9]*)$"]

########## Natural language toolbox and lexical stuff: FRENCH ONLY!!!

STOP_WORDS = [
	# Prepositions (excepted "avec" and "sans" which are semantically meaningful)
	"a", "au", "aux", "de", "des", "du", "par", "pour", "sur", "chez", "dans", "sous", "vers", 
	# Articles
	"le", "la", "les", "l", "c", "ce", "ca", 
	 # Conjonctions of coordination
	"mais", "et", "ou", "donc", "or", "ni", "car"
]

def isStopWord(word): return word in STOP_WORDS

def isValidPhrase(tokens): return len(tokens) > 0 and not all([len(t) < 2 and t.isdigit() for t in tokens])

def isValidToken(token, exclusionFilter = None):
	token = token.strip(" -_.,'?!")
	if token.isspace() or not token: return False
	if exclusionFilter and exclusionFilter(token): return False
	if token.isalpha() and len(token) <= 2 and not token.isupper(): return False
	return not isStopWord(token)

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

def splitThis(string, delimiters): return re.split('|'.join(map(re.escape, list(delimiters))), string)

def caseToken(t, keepAcronyms): return toASCII(lowerOrNot(t.strip(), keepAcronyms))

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

def splitAndCase(phrase, keepAcronyms):
	s = ' ' + phrase.strip() + ' '
	# str = replaceBySpace(str, '[\[\](),\.\";:!?&\^\/\*-]')
	# str = re.sub('([^\d\'])-([^\d])', '\1 \2', str)
	# tokens = splitThis(str, " .:<>#,;?!()[]{}’")
	s = replaceBySpace(s, '[\{\}\[\](),\.\"\';:!?&\^\/\*-]')
	s = re.sub('([^\d\'])-([^\d])', '\1 \2', s)
	tokens = str.split(s)
	return map(lambda t: caseToken(t, keepAcronyms), tokens)

def validateTokens(phrase, keepAcronyms, exclusionFilter = None):
	if phrase:
		tokens = splitAndCase(phrase, keepAcronyms)
		validTokens = []
		for token in tokens:
			if isValidToken(token, exclusionFilter):
				validTokens.append(token)
		if isValidPhrase(validTokens): return validTokens 
	return []

def toASCII(phrase):
	uni = phrase if isinstance(phrase, unicode) else unicode(phrase, 'utf-8')
	normed = unicodedata.normalize('NFKD', uni)
	return normed.encode('ASCII', 'ignore')

def normalizeAndValidateTokens(value, keepAcronyms, exclusionFilter = None):
	''' Returns a list of normalized, valid tokens for the input phrase (an empty list if no valid tokens were found) '''
	return validateTokens(value, keepAcronyms, exclusionFilter)

def normalizeAndValidatePhrase(value, keepAcronyms, exclusionFilter = None):
	''' Returns a string that joins normalized, valid tokens for the input phrase (None if no valid tokens were found) '''
	tokens = normalizeAndValidateTokens(value, keepAcronyms, exclusionFilter)
	return ' '.join(tokens) if tokens else None

def scanRange(slide, minK, maxK, l):
	res = (0, l)
	done = set(res)
	yield res
	for i in range(1 - maxK, l - 1) if slide else [0]:
		for j in range(max(0, i + 1), min(l, i + maxK)):
			res = (i, j)
			if res not in done and res[0] >= 0 and res[1] < l:
				done.add(res)
				yield res

def kgrams(text, slide, minK, maxK, keepAcronyms):
	tokens = normalizeAndValidateTokens(text, keepAcronyms)
	phrase = ' '.join(tokens)
	done = set(phrase)
	yield phrase
	for i in range(len(tokens)) if slide else [0]:
		for k in reversed(range(min(minK, len(tokens) - i), maxK + 1)):
			kgram = ' '.join(tokens[i : i + k])
			if kgram not in done:
				done.add(kgram)
				yield kgram

# Lookup class definitions

class SmallVocabLookup(object):

	def __init__(self, keepAcronyms):
		self.uidsByNormedTerm = defaultdict(set)
		self.termsByNormedTerm = defaultdict(set)
		self.keepAcronyms = keepAcronyms

	def index(self, normed, term, uids):
		self.uidsByNormedTerm[normed] |= uids
		self.termsByNormedTerm[normed].add(term)

	def lookup(self, phrase):
		''' Returns a dictionary with keys 0, 1, 2 and values possibly empty lists of normalized terms matching the input term'''
		return None

	def normedTermsMatchingTerm(self, term, maxDist):
		''' Returns a flat list of normalized terms matching the input term, sorted by increasing distance to the input term'''
		return None

	def termsMatchingText(self, text, keepAcronyms, maxTokens, minCount = 1):
		''' 
		Same as normedTermsMatchingTerm except that a whole fragment of text is scanned using a sliding window, 
		and that the result is not a flat list of normalized terms but a (term->normalizedTerm) dictionary.
		Also, we optionally discard matches with occurrence below minCount.
		'''
		matchesByNormedTerm = defaultdict(int)
		for kgram in kgrams(text, True, 1, maxTokens, self.keepAcronyms):
			matchingNormedTerms = self.normedTermsMatchingTerm(kgram)
			for normedTerm in matchingNormedTerms:
				matchesByNormedTerm[normedTerm] += 1
		return dict([(nt, (c, self.termsByNormedTerm[nt])) for (nt, c) in matchesByNormedTerm.iteritems() if  c >= minCount])

	def countUidMatches(self, text, maxTokens, minCount):
		''' 
		Returns a (possibly empty) dictionary whose keys are keywords found (exactly or approximately) in the input text
		and values are (occurrence count, set of associated labels) pairs.

		Parameters:
		text is the input text
		maxTokens is n in the n-gram size of the input window rolled over the input text
		minCount is the min number of matches to retain a match
		''' 
		matchingTermsByNormedTerm = self.termsMatchingText(text, maxTokens, minCount)
		countsByTerm = defaultdict(int)
		uidsByTerm = defaultdict(set)
		for (nt, countTermsPair) in matchingTermsByNormedTerm.iteritems():
			count = countTermsPair[0]
			terms = countTermsPair[1]
			for t in terms:
				countsByTerm[t] += count
				uidsByTerm[t] |= self.uidsByNormedTerm[nt]
		return dict([(t, (c, uidsByTerm[t])) for (t, c) in countsByTerm.iteritems()])

class FSSLookup(SmallVocabLookup):

	def __init__(self, uidsByTerm, minTokens, maxTokens, keepAcronyms):
		super(FSSLookup, self).__init__(keepAcronyms)
		self.fss = FastSS()
		for (term, uids) in uidsByTerm.iteritems():
			normed = normalizeAndValidatePhrase(term, self.keepAcronyms)
			for kgram in kgrams(normed, True, minTokens, maxTokens, self.keepAcronyms):
				self.index(kgram, term, uids)
		self.fss.makeindex()

	def index(self, normed, term, uids):
		super(FSSLookup, self).index(normed, term, uids)
		self.fss.add(normed)

	def lookup(self, phrase):
		normed = normalizeAndValidatePhrase(phrase, self.keepAcronyms)
		return self.fss.search(normed) if normed else None

	def normedTermsMatchingTerm(self, term, maxDist = lambda l: 2 if l >= 6 else 1 if l >= 4 else 0):
		results = self.lookup(term)
		if results is None: return []
		# m = maxDist(len(term))
		# return functools.reduce(operator.concat, [results[d] for d in range(m+1)])		
		return list([r for (d, l) in results.iteritems() for r in l if d <= maxDist(min(len(term), len(r)))])

class FWLookup(SmallVocabLookup):

	def __init__(self, uidsByTerm, minTokens, maxTokens, keepAcronyms):
		super(FWLookup, self).__init__(keepAcronyms)
		self.idx = []
		for (term, uids) in uidsByTerm.iteritems():
			normed = normalizeAndValidatePhrase(term, self.keepAcronyms)
			for kgram in kgrams(normed, True, minTokens, maxTokens, self.keepAcronyms):
				super(FWLookup, self).index(normed, term, uids)
			self.idx.append(normed)

	def lookup(self, phrase):
		normed = normalizeAndValidatePhrase(phrase, self.keepAcronyms)
		metric = fuzz.ratio # fuzz.partial_ratio
		return dict(process.extract(normed, self.idx, limit = 2, scorer = metric)) if normed else None

	# When distance is a fuzz partial ratio, threshold needs to be higher for longer strings
	# When distance is a fuzz ratio, threshold needs to be lower for longer strings
	def normedTermsMatchingTerm(self, term, maxDist = lambda l: 60 if l > 10 else 50 if l > 5 else 40):
		results = self.lookup(term)
		if results is None: return []
		ts = sorted(results.keys(), key = lambda t : results[t], reverse = True)
		l = len(term)
		return list(itertools.takewhile(lambda t: results[t] >= maxDist(min(len(t), l)), ts))

class NGLookup(SmallVocabLookup):

	def __init__(self, uidsByTerm, minTokens, maxTokens, n = 4, rarest = 5):
		super(NGLookup, self).__init__(keepAcronyms)
		self.n = n
		self.idx0 = defaultdict(set)
		self.idx = defaultdict(set)
		c0 = defaultdict(int)
		c = defaultdict(int)
		for (term, uids) in uidsByTerm.iteritems():
			for g in prefixNgrams(term, n):
				c0[g] += 1
			for g in ngrams(term, n, boundaries = USE_BOUNDS):
				c[g] += 1
		for (term, uids) in uidsByTerm.iteritems():
			for g in prefixNgrams(term, n):
				self.idx0[g] += uids
			for g in sorted(ngrams(term, n, boundaries = USE_BOUNDS), key = lambda g: c[g])[:rarest]:
				self.idx[g] += uids

	def lookup(self, phrase):
		pass
	def normedTermsMatchingTerm(self, term, maxDist = lambda l: 60 if l > 10 else 50 if l > 5 else 40):
		pass
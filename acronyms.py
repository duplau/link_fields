#!/usr/bin/python
# coding=utf-8

import csv, math, re, sys, logging, optparse
import vocab_lookup
from collections import defaultdict

DEBUG_MODE = False

# Text validation

def preclean(v): return v.strip(" -_.,'?!").strip() # Minimal cleanup

def isValidValue(v): return preclean(v).lower() not in ['', 'null', 'na', 'n/a', 'aucun']

def tokenLength(p): return len(vocab_lookup.normalizeAndValidateTokens(p))

# Iteration of CSV and text-line files

def fileValueiterator(fileName): 
	with open(fileName) as f:
		for line in f:
			entry = preclean(line)
			if isValidValue(entry): yield entry

def fileRowIterator(fileName, sep = '|'):
	with open(fileName, 'rb') as csvfile:
		reader = csv.reader(csvfile, delimiter = sep, quotechar='"')
		for row in reader: yield row

def fileColumnToList(fileName, c, sep = '\t', includeInvalid = False):  
	return [r[c] for r in fileRowIterator(fileName, sep) if len(r) > c and (includeInvalid or isValidValue(r[c]))]

def validRefEntries(refFileName):
	return filter(lambda l: len(l) > 0 and isValidValue(l[0]), fileRowIterator(refFileName, sep = '|'))

def acronymToTermsFromFile(fileName): return { l[0].strip().upper(): l[1:] for l in validRefEntries(fileName) }

# Misc utilities

def stringFreq(t, pl, dontFold):
	if dontFold: return sum([re.search(t, p) is not None for p in pl])
	else: return sum([re.search(t, p, re.I) is not None for p in pl])

def mostCommonInList(l):
	c = defaultdict(int)
	for i in l: c[i] += 1
	return sorted(c.keys(), key = lambda i: c[i], reverse = True)[0]

########## Acronym inference parameters

FRENCH_KNOWN_ACRONYMS = acronymToTermsFromFile('resource/common_acronyms_fr')
FRENCH_TOT_FREQ = {vocab_lookup.toASCII(r[0].strip()).upper(): int(r[1]) for r in fileRowIterator('resource/most_common_tokens_fr', '|')}
FRENCH_AVG = sum([f for (t, f) in FRENCH_TOT_FREQ.iteritems()]) / len(FRENCH_TOT_FREQ)
AMBIGUITY_FACTOR = 4
CAP_FACTOR = 8
COMMON_FACTOR = 32
KNOWN_FACTOR = 16

########## Referential class definition

LOOKUP_CLASS = vocab_lookup.FSSLookup
# LOOKUP_CLASS = vocab_lookup.NGLookup
# LOOKUP_CLASS = vocab_lookup.FWLookup

TOKEN_LENGTH_FACTOR = 2
def matchLengthFactor(t1, t2, keepAcronyms, closest = True):
	l1 = len(vocab_lookup.normalizeAndValidateTokens(t1, keepAcronyms))
	l2 = len(vocab_lookup.normalizeAndValidateTokens(t2, keepAcronyms))
	# return pow(TOKEN_LENGTH_FACTOR, - abs(l1 - l2)) if closest else pow(TOKEN_LENGTH_FACTOR, len(l1))
	return 1000000 / (1 + abs(l1 - l2)) if closest else pow(TOKEN_LENGTH_FACTOR, len(l1))

class Referential(object):

	def __init__(self, refFileName, keepAcronyms = False, maxIndexedTokens = 4, maxLookupTokens = 6):
		logging.info('Loading vocabulary from reference file %s' % refFileName)
		uidsByTerm = defaultdict(set)
		l = fileRowIterator(refFileName, sep = '|')
		for sl in filter(lambda l: len(l) > 0 and isValidValue(l[0]), l):
			if sl[0] in uidsByTerm:
				raise IOError('Duplicate main variant found in reference file: %s' % sl[0])
			for term in filter(isValidValue, sl): 
				uidsByTerm[sl[0]].add(term)
		self.vocabLookup = LOOKUP_CLASS(uidsByTerm, 1, maxIndexedTokens, keepAcronyms)
		self.termByUid = dict() # inverted index
		for term, uids in uidsByTerm.iteritems():
			for uid in uids:
				if uid in self.termByUid: raise RuntimeError('Duplicate uid!')
				self.termByUid[uid] = term
		self.maxLookupTokens = maxLookupTokens
		acroSizeDiscount = int(math.floor(math.log(max(1, len(uidsByTerm) / 100))))
		self.minAcroSize = vocab_lookup.MIN_ACRO_SIZE - acroSizeDiscount
		self.maxAcroSize = vocab_lookup.MAX_ACRO_SIZE - acroSizeDiscount

	########## Acronym inference heuristics
	# (a) we fetch the most common acronyms for a given main variant, and decrease the score of ambiguous acronyms
	# (b) we bump up the score from (a) when these acronyms are capitalized and only capitalized
	# (c) we decrease the score when the acronym is also a common word ("cat" in english)
	#     --> this uses a frequency list of most common (e.g. English) words
	# (d) we increase the score when the acronym is also a known acronym
	#     --> this uses a frequency list of acronyms crawled from well-defined sources

	def acronymizePhrase(self, phrase): 
		keepAcronyms = True
		tokens = vocab_lookup.normalizeAndValidateTokens(phrase, keepAcronyms)
		return self.acronymizeTokens(tokens)

	def acronymizeTokens(self, tokens):
		for s in range(max(self.minAcroSize, len(tokens)), min(self.maxAcroSize, len(tokens)) + 1):
			tl = tokens[:s]
			yield (''.join([t[0] for t in tl]).upper(), tl)

	def acronymExpansions(self, tokens, acronyms):
		yield tokens
		for i in  range(len(tokens)):
			t = tokens[i]
			if len(t) < self.minAcroSize or len(t) > self.maxAcroSize or t not in acronyms: continue
			yield tokens[:i] + list(acronyms[t][0]) + tokens[i+1:]

	def acronymizeAll(self, phrases):
		termsByAcro = defaultdict(set)
		for phrase in phrases:
			for (acro, tokens) in self.acronymizePhrase(phrase): 
				termsByAcro[acro].add(tuple(tokens))
		return termsByAcro

	def scoreAcronyms(self, termsByAcro, phrases):
		scores = dict()
		for a, terms in termsByAcro.iteritems():
			fCap = stringFreq(a, phrases, True)
			fAll = stringFreq(a, phrases, False) - fCap
			if fCap < 1: continue
			s = 1. / pow(AMBIGUITY_FACTOR, len(terms))  * fCap / (fCap + CAP_FACTOR * fAll)
			if a in FRENCH_TOT_FREQ: 
				s = s * float(FRENCH_AVG) / (FRENCH_TOT_FREQ[a] * COMMON_FACTOR)
			if a in FRENCH_KNOWN_ACRONYMS.keys(): 
				s = s * KNOWN_FACTOR
			scores[a] = (mostCommonInList(terms), s)
			dumpStats(scores)
		return scores

	def fetchAcronyms(self, inputPhrases, refFileName):
		''' Returns a dictionary mapping an (upper-cased) acronym to a pair (tokens, score) where 
		tokens represent the most common expansion of the acronym and the score is based on input 
		as training data. '''
		termsByAcro = self.acronymizeAll([sl[0] for sl in validRefEntries(refFileName)])
		return self.scoreAcronyms(termsByAcro, inputPhrases)

	def matchScore(self, phrase, acronyms = None):
		''' The main matching method for this referential. '''
		matches = self.vocabLookup.countUidMatches(phrase, maxTokens = self.maxLookupTokens, minCount = 1)
		# Variable matches holds a dict(variant -> list(hitCount, mainVariant))
		if acronyms and len(matches) < 1:
			tokens = vocab_lookup.normalizeAndValidateTokens(phrase)
			for acroExpanded in self.acronymExpansions(tokens, acronyms):
				matches.update(self.vocabLookup.countUidMatches(' '.join(acroExpanded), 
					maxTokens = self.maxLookupTokens + len(acroExpanded) - len(tokens), 
					minCount = 1))
		for (t, p) in matches.iteritems():
			for m in p[1]:
				yield (m, p[0] * matchLengthFactor(t, m, acronyms))

########## Main methods

def collectExpansions(f0, f1 = None):

def showAmbiguousExpansions(f0):

def deleteAmbiguousExpansions(f0):

def showUnexpectedExpansions(f0, f1):

def deleteUnexpectedExpansions(f0, f1):

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(asctime)s %(message)s")
	reload(sys)  
	sys.setdefaultencoding('utf8')
	parser = optparse.OptionParser()
	parser.add_option("-f0", "--ref_acronyms_file", dest="f0",
					  help="the path to a file containing acronyms from reference/clean data")
	parser.add_option("-f1", "--src_acronyms_file", dest="f1",
					  help="the path to a file containing acronyms from source/ugly data")
	parser.add_option("-ce", "--collect_expansions", dest="collectExpansions",
					  help="used to collect all expansions associated to a given acronym in the input file \
					  (requires a reference acronyms file via option -f0, and optionally a source acronyms \
					  file via =f1 that will be checked against the acronyms in the reference file)")
	parser.add_option("-sa", "--show_ambiguous_expansions", dest="showAmbiguousExpansions",
					  help="show ambiguous expansions (requires a reference acronyms file only, cf. option -f0)")
	parser.add_option("-da", "--delete_ambiguous_expansions", dest="deleteAmbiguousExpansions",
					  help="delete ambiguous expansions (requires a reference acronyms file only, cf. option -f0)")
	parser.add_option("-su", "--show_unexpeted_expansions", dest="showUnexpectedExpansions",
					  help="show unexpected expansions (requires reference and source acronyms files, i.e. -f0 and -f1)")
	parser.add_option("-du", "--delete_unexpected_expansions", dest="deleteUnexpectedExpansions",
					  help="delete unexpected expansions (requires reference and source acronyms files, i.e. -f0 and -f1)")

	(options, args) = parser.parse_args()
	if options.collectExpansions:
		collectExpansions(options.f0, options.f1)
	if options.showAmbiguousExpansions:
		showAmbiguousExpansions(options.f0)
	if options.deleteAmbiguousExpansions:
		deleteAmbiguousExpansions(options.f0)
	if options.showUnexpectedExpansions:
		showUnexpectedExpansions(options.f0, options.f1)
	if options.deleteUnexpectedExpansions:
		deleteUnexpectedExpansions(options.f0, options.f1)

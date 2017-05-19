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

########## Main process : field linking

# - Input is read on stdin.
# - A reference (or nomenclature) file is required as argument, where each line indicates one reference entity, written as 
#   a list of pipe-separated values representing known variants for the entity (with the first element in the list, always
#   present, being the main variant, unique across the file and serving as unique id).
# - It produces as output one line for each line given in input, where each line is a list of tab-separated values for found
#   associations, with their score, so for example `inputTerm|mainVariant_1|score_1|mainVariant_2|score_2` if 2 reference
#   entities were linked with some probability.

def dumpStats(d):
	for i, c in d.iteritems(): print str(c).rjust(3), str(i)

def matchAll(inputPhrases, refFileName, outputStats, findAcronyms, beSpecific = False):
	referential = Referential(refFileName, findAcronyms)
	acronyms = referential.fetchAcronyms(inputPhrases, refFileName) if findAcronyms else None
	matchScores = dict()
	termCounter = defaultdict(int)
	matchCounts = defaultdict(list)
	inputCount = 0
	for term in inputPhrases:
		inputCount += 1
		if term in matchScores: 
			refs = matchScores[term]
		elif isValidValue(term):
			it = referential.matchScore(term, acronyms) # iterator over (mainVariant, score) pairs
			matchScores[term] = list(it)
			if DEBUG_MODE: print 'MATCH_SCORES %s' % '|'.join(['%s(%d)' % (s[0], s[1]) for s in matchScores[term]])
			if beSpecific and len(matchScores[term]) > 0: # Purely length-based specificity
				matchScores[term] = sorted(matchScores[term], key = lambda p: len(p[0]), reverse = True)[:1]
		result = [term]
		if term in matchScores:
			termCounter[term] += 1
			if isValidValue(term):
				matchCount = len(matchScores[term])
				matchCounts[term].append(matchCount)
			for (uid, s) in matchScores[term]:
				result.extend([referential.termByUid[uid], str(s)])
		if DEBUG_MODE: 
			if inputCount % 100 == 0: print 'LOOP %d entries processed' % inputCount
			totalCount = sum([mc for mc in matchCounts[term]]) if term in matchCounts else 0
			if beSpecific and totalCount < 1: print 'UNMATCHED %s' % term
		 	elif totalCount != 1: print 'AMBIGUOUS %s (%d)' % (term, totalCount)
		else: 
			print '|'.join(result)
	if outputStats:
		dumpStats({
			'total unique terms': len(termCounter),
			'valid unique terms': len(matchCounts),
			'unmatched terms': sum([all([c < 1 for c in counts]) for counts in matchCounts.values()]),
			'single-match terms': sum([all([c == 1 for c in counts]) for counts in matchCounts.values()]),
			'multiple-match terms': sum([all([c > 1 for c in counts]) for counts in matchCounts.values()]),
			'ambiguous terms': sum([len(set(counts)) > 1 for counts in matchCounts.values()])})

# Built-in referentials, organized per functional domain

BUILTIN_REFS = {
	'INSEE': [
		'data/commune.insee.ref'
	],
	'MESR': [
		'data/mention_licence.sise.ref'
	],
	'ACTA': [ 
		'data/produit_phyto.acta.ref'
	],
	'HAL': [ 
		'data/organization.hal.ref'
	]
}

# Main method to run the field linkage process

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(asctime)s %(message)s")
	parser = optparse.OptionParser()
	parser.add_option("-i", "--input", dest="inputFileName",
					  help="the path to an input file containing the entities to try and match.")
	parser.add_option("-r", "--reference", dest="refFileName",
					  help="the path to a reference file containing the entities to match against. \
					  The reference (or nomenclature) file has one line per reference entity, written as a list of \
					  pipe-separated values representing  known variants for the entity (with the first element in the list, \
					  	always present, being the main variant, unique across the file and serving as unique id)")
	parser.add_option("-a", "--acronyms", action="store_true", dest="findAcronyms", default = False,
					  help="if this option is set, acronyms are added as variants to each entity in the nomenclature \
					  (and any new term variants are taken into account during the linking process)")

	parser.add_option("-s", "--stats", action="store_true", dest="outputStats", default = False,
					  help="if this option is set, only tallies of results will be displayed (number of matches, etc.)")

	(options, args) = parser.parse_args()
	inputPhrases = list(fileValueiterator(options.inputFileName))
	matchAll(inputPhrases, options.refFileName, options.outputStats, options.findAcronyms, True)

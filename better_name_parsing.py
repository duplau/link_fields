#!/usr/bin/env python3
# coding=utf-8

import unicodedata
from pyparsing import *

F_FIRST = u'Prénom'
F_LAST = u'Nom'
F_TITLE = u'Titre'
F_FIRSTORLAST = F_FIRST + '|' + F_LAST

def stripped(s): return s.strip(" -_.,'?!").strip('"').strip()
def fileToList(fileName): 
	with open(fileName, mode = 'r') as f: 
		return [stripped(line) for line in f]
def fileToSet(fileName): return set(fileToList(fileName))


def toASCII(phrase): return unicodedata.normalize('NFKD', phrase) # normalize('NFD', text)
def casefold(text): return toASCII(text).casefold()
def prepString(s): return re.sub(r'[\b\s](et|and|&)[\b\s]', ',', s, flags=re.IGNORECASE)

PRENOM_LEXICON = fileToSet('resource/prenom')
FR_FIRSTNAMES = list([s.lower() for s in PRENOM_LEXICON])[:10]

name = Word(alphas, min = 3, asKeyword = True)
lastName = Group(delimitedList(name, '-')).setResultsName(F_LAST) + WordEnd()
letter = Word(alphas, exact = 1)
initial = letter + Optional(Literal('.'))
initials = Or([Group(delimitedList(initial, '-')), Group(OneOrMore(initial))]) + WordEnd()
compFirstName = Or([Group(OneOrMore(Or(FR_FIRSTNAMES))), Group(delimitedList(Or(FR_FIRSTNAMES), '-'))])
firstName = Or([initials, compFirstName]).setResultsName(F_FIRST)
lastInitial = (letter + Literal('.')).setResultsName(F_LAST) + WordEnd()
personNameWithoutComma = Or([firstName + lastInitial, firstName + lastName, lastName + firstName])
personNameWithComma = lastName + Literal(',') + firstName
personName = Or([personNameWithoutComma, personNameWithComma])
personNames = Or([delimitedList(personName, ';'), delimitedList(personNameWithoutComma, ',')])

def extractPersonNames(l):
	return personNames.parseString(l)

def customParsePersonNamesAsStrings(s): 
	ls = extractPersonNames(s)
	print('ls', ls.asDict())
	return list([' '.join(l) for l in ls])

MD_OUTPUT_MAX = 3

def printCustomParsePersonNamesAsHeader(): 
	print('## Résultats de normalisation de noms de personnes')
	print('')
	print('|{}|'.format('|'.join(['Source'] + ['Nom #' + str(i + 1) for i in range(MD_OUTPUT_MAX)])))
	print('|{}|'.format('|'.join('-' * (MD_OUTPUT_MAX + 1))))

def printCustomParsePersonNamesAsMd(src): 
	ls = list(customParsePersonNamesAsStrings(src))
	print('|{}|'.format('|'.join([src] + ls[:MD_OUTPUT_MAX])))

if __name__ == '__main__':
	printCustomParsePersonNamesAsHeader()
	for (src, refs) in [
		('Justine, J.-L.', [('Justine', 'J.-L.')]),
		('Adolphe L.', [('L.', 'Adolphe')]),
		# ('Pierre-André MIMOUN', [('Pierre-André', 'MIMOUN')]),
		# ('Pierre-André mimoun', [('Pierre-André', 'MIMOUN')]),
		('Alain Schnapp', [('Alain', 'Schnapp')]),
		('Schnapp Alain', [('Alain', 'Schnapp')]),
		('BADIE Bertrand', [('Bertrand', 'BADIE')]),
		('BAKHOUCHE Béatrice', [('Béatrice', 'BAKHOUCHE')]),
		('Emmanuel WALLON (sous la direction de)', [('Emmanuel', 'WALLON')]),
		('Charles-Edmond BICHOT', [('Charles-Edmond', 'BICHOT')]),
		('Abdellah Bounfour, Kamal Naït-Zerrad et Abdallah Boumalk', [('Abdellah', 'Bounfour'), ('Kamal', 'Naït-Zerrad'), ('Abdallah', 'Boumalk')]),
		('Sylvie Neyertz et David Brown', [('Sylvie', 'Neyertz'), ('David', 'Brown')]),
		('Anne-Dominique Merville & Antoine COPPOLANI', [('Anne-Dominique', 'Merville'), ('Antoine', 'COPPOLANI')]),
		('J.P. Poly', [('J.P.', 'Poly')]),
		('Dominique Kalifa', [('Dominique', 'Kalifa')]),
		('S. CHAKER (Dir.)', [('S.', 'CHAKER')]),
		('Schreck E., Gontier L. and Treilhou M.', [('E.', 'Schreck'), ('L.', 'Gontier'), ('M.', 'Treilhou')]),
		('L. Jutier, C. Léonard and F. Gatti.', [('L.', 'Jutier'), ('C.', 'Léonard'), ('F.', 'Gatti.')]),
		('Véronique Wester-Ouisse', [('Véronique', 'Wester-Ouisse')]),
		('Thibault, André', [('André', 'Thibault')])
	 ]:
	 	printCustomParsePersonNamesAsMd(src)
	# with open('test_data/person_names.to_normalize', mode = 'r') as f: 
	# 	for line in f:
	# 		printCustomParsePersonNamesAsMd(stripped(line))			

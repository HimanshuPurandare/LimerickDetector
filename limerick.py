#!/usr/bin/env python
import argparse
import sys
import codecs
if sys.version_info[0] == 2:
  from itertools import izip
else:
  izip = zip
from collections import defaultdict as dd
import re
import os.path
import gzip
import tempfile
import shutil
import atexit
from string import punctuation
import nltk
from nltk.tokenize import word_tokenize

scriptdir = os.path.dirname(os.path.abspath(__file__))

reader = codecs.getreader('utf8')
writer = codecs.getwriter('utf8')

def prepfile(fh, code):
  if type(fh) is str:
    fh = open(fh, code)
  ret = gzip.open(fh.name, code if code.endswith("t") else code+"t") if fh.name.endswith(".gz") else fh
  if sys.version_info[0] == 2:
    if code.startswith('r'):
      ret = reader(fh)
    elif code.startswith('w'):
      ret = writer(fh)
    else:
      sys.stderr.write("I didn't understand code "+code+"\n")
      sys.exit(1)
  return ret

def addonoffarg(parser, arg, dest=None, default=True, help="TODO"):
  ''' add the switches --arg and --no-arg that set parser.arg to true/false, respectively'''
  group = parser.add_mutually_exclusive_group()
  dest = arg if dest is None else dest
  group.add_argument('--%s' % arg, dest=dest, action='store_true', default=default, help=help)
  group.add_argument('--no-%s' % arg, dest=dest, action='store_false', default=default, help="See --%s" % arg)

class LimerickDetector:
    def __init__(self):
        """
        Initializes the object to have a pronunciation dictionary available
        """
        self._pronunciations = nltk.corpus.cmudict.dict()
        
    def guess_syllables(self, word):
        word = word.lower()
        vow = {'a','e','i','o','u'}
        count = 0     
        if word.endswith('es'):
            temp_word = word[:-2]
            if not temp_word.endswith('s') and not temp_word.endswith('ss') and not temp_word.endswith('sh') and not temp_word.endswith('ch') and not temp_word.endswith('x') and not temp_word.endswith('z') and not temp_word.endswith('c'):
                if not temp_word.endswith('l'):
                    count -= 1
        if word[0] in vow:
            count += 1
        for i in range(1,len(word)):
            if word[i] in vow and not word[i-1] in vow:
                count += 1
            if i == len(word) - 1 and word[i] == 'e' and not word[i-1] == 'l' and not word[i-1] in vow:
                count -= 1
            elif word[i] == 'y':
                if i == len(word)-1 and not word[i-1] in vow:
                    count += 1
                elif not i == len(word)-1 and not word[i+1] in vow:
                    count += 1
        if not word == "fully" and word.endswith("fully"):
            count -= 1
        if 'ia' in word or 'ism' in word:
            count+=1
        if word.endswith('ism'):
            count+=1
        if word.endswith("ed"):
            count -= 1
        if word.startswith("natural"):
            count -= 1
        if count == 0:
            count = 1
        return count
    
    def apostrophe_tokenize(self, text):
        text = text.lower()
        tokenizer = nltk.tokenize.RegexpTokenizer(r'[\w\']+')
        return tokenizer.tokenize(text)
        
    def generate_pronunciationStringList(self, word):
        word = word.lower()
        vowels = set('aeiouAEIOU')
        StringList = []
        for pronunciation in self._pronunciations[word]:
                String = ""
                count = 1
                for sound in pronunciation:
                    if vowels.isdisjoint(sound):
                        count += 1
                        continue
                    elif count == 1:
                        break
                    else:
                        pronunciation = pronunciation[(pronunciation.index(sound)):]
                        break
                    
                for remainingSounds in pronunciation:
                    String += str(remainingSounds)
                StringList.append(String)
        return StringList
    
    def num_syllables(self, word):
        """
        Returns the number of syllables in a word.  If there's more than one
        pronunciation, take the shorter one.  If there is no entry in the
        dictionary, return 1.
        """
        word = word.lower()
        count = 0
        minimum = 999999 
        if word in self._pronunciations:
            for pronunciation in self._pronunciations[word]:
                count = 0
                for element in pronunciation:
                    tem = element[-1]
                    if tem.isdigit():
                        count += 1
                if count < minimum:
                    minimum = count
            return minimum
        else: return 1

    def rhymes(self, a, b):
        """
        Returns True if two words (represented as lower-case strings) rhyme,
        False otherwise.
        """
        a = a.lower()
        b = b.lower()
        aStringList = []
        bStringList = []
        if a in self._pronunciations:
            aStringList = self.generate_pronunciationStringList(a)
        else:
            return False
        if b in self._pronunciations:
            bStringList = self.generate_pronunciationStringList(b)
        else:
            return False
            
        if len(a) >= len(b):
            for aStr in aStringList:
                for bStr in bStringList:
                    if aStr.endswith(bStr):
                        return True
        else:
            for aStr in aStringList:
                for bStr in bStringList:
                    if bStr.endswith(aStr):
                        return True
        return False

    def is_limerick(self, text):
        """
        Takes text where lines are separated by newline characters.  Returns
        True if the text is a limerick, False otherwise.

        A limerick is defined as a poem with the form AABBA, where the A lines
        rhyme with each other, the B lines rhyme with each other, and the A lines do not
        rhyme with the B lines.


        Additionally, the following syllable constraints should be observed:
          * No two A lines should differ in their number of syllables by more than two.
          * The B lines should differ in their number of syllables by no more than two.
          * Each of the B lines should have fewer syllables than each of the A lines.
          * No line should have fewer than 4 syllables

        (English professors may disagree with this definition, but that's what
        we're using here.)
        """
        text = text.lower().strip()
        A = []
        B = []
        aLineSyllables = []
        bLineSyllables = []
        lines = text.splitlines()
        if len(lines) > 5:
            for line in lines:
                if line == "":
                    del lines[lines.index(line)]
        lineno = 1
        
        if len(lines) == 5:
            for line in lines:
                line = line.strip()
                syllablesInLine = 0
                line = re.sub(r"[^\w\s']",'',line)
                wordsInLine = word_tokenize(line)
                
                #Check number of syllables constraint
                for words in wordsInLine:
                    syllablesInLine += self.num_syllables(words)
                
                if lineno == 1 or lineno == 2 or lineno == 5:
                    A.append(wordsInLine[-1])
                    if syllablesInLine < 4:
                        return False
                    else:
                        aLineSyllables.append(syllablesInLine)
                else:
                    B.append(wordsInLine[-1])
                    if syllablesInLine < 4:
                        return False
                    else:
                        bLineSyllables.append(syllablesInLine)
                lineno += 1
            
            if not ((abs(aLineSyllables[0] - aLineSyllables[1]) <= 2) and (abs(aLineSyllables[1] - aLineSyllables[2]) <= 2) and (abs(aLineSyllables[0] - aLineSyllables[2]) <= 2) and (abs(bLineSyllables[0] - bLineSyllables[1]) <= 2)):
                return False
            
            for i in aLineSyllables:
                for j in bLineSyllables:
                    if j >= i:
                        return False
            #Call Rhyme()
            if (self.rhymes(B[0],B[1])):
                if ((self.rhymes(A[0], A[1])) and (self.rhymes(A[1], A[2]))):
                    if ((not self.rhymes(B[0],A[0])) and (not self.rhymes(B[0],A[1])) and (not self.rhymes(B[0],A[2])) and (not self.rhymes(B[1],A[0])) and (not self.rhymes(B[1],A[1])) and (not self.rhymes(B[1],A[2]))):
                        return True
        return False

def main():
  parser = argparse.ArgumentParser(description="limerick detector. Given a file containing a poem, indicate whether that poem is a limerick or not",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  addonoffarg(parser, 'debug', help="debug mode", default=False)
  parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="input file")
  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file")

  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  infile = prepfile(args.infile, 'r')
  outfile = prepfile(args.outfile, 'w')

  ld = LimerickDetector()
  lines = ''.join(infile.readlines())
  outfile.write("{}\n-----------\n{}\n".format(lines.strip(), ld.is_limerick(lines)))

if __name__ == '__main__':
  main()

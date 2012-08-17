#!/usr/bin/env python
from __future__ import print_function
import re, os, argparse, string, glob, copy

longhelp = """
makemake [--command [FLAG COMMAND_WORD]* ]* --files [FILENAME]*

This is a utility to generate makefiles based on regular expression
matching. The intention is to make it easier to conduct the kind of
file processing that is required in scientific data processing
pipelines. The intent is also to be simpler to understand, use, and
debug than the equivalent Makefiles would be, but not to cover every
possible situation that a build system might encounter.

--command marks the beginning of a command rule. 

Each subsequent word is an word to construct the command line. These
are all either regexps (if flagged with --match) or regexp
replacements. If you want to literally use a single file with a
specific name, just write a regexp or replacement that matches
literally. But each argument may be prepended by one or more flags.
The most important flag is --match, just described.

If completely unadorned, the argument is just a word to build your
command line out of, such as "gcc" and any flags you pass to GCC like
"-o". However each word may have a number of flags set which change
its meaning.

BUILDING COMMANDS

In Make, any output file can only be the product of one
rule. Therefore if an argument is named twice while matching rules,
the command lines are combined, respecting the 'once' flag. For
example, the rule

--command 
--once --input ./aggregate.R 
--once %-o --once --output 'pools/{0}.collected'
--match --input 'datafiles/([^.]*)\.(.*).txt' 

will make rules that that have dependencies of the form
datafiles/PREFIX.INFIX.txt, and create products of the form
pools/PREFIX.txt. Thus we have a many-to-one reduction.  For example,
with this rule, if the starting file set is:

datafiles/monkey1.monday.txt
datafiles/monkey1.tuesday.txt
datafiles/monkey2.wednesday.txt
datafiles/monkey2.thursday.txt
datafiles/monkey3.friday.txt

Then rules are produced to create 3 files out of the 5 inputs:

pools/monkey1.collected: datafiles/monkey1.monday.txt\
datafiles/monkey1.tuesday.txt datafiles/monkey1.wednesday.txt ./aggregate.R
	 ./aggreate.R -o pools/monkey1.collected datafiles/monkey1.monday.txt\
         datafiles/monkey1.tuesday.txt datafiles/monkey1.wednesday.txt

pools/monkey2.collected: monkey2.wednesday.txt\
monkey2.thursday.txt ./aggregate.R
	 ./aggreate.R -o pools/monkey1.collected monkey2.wednesday.txt\
         monkey2.thursday.txt

pools/monkey3.collected: monkey3.friday.txt ./aggregate.R
	 ./aggregate.R -o pools/monkey3.collected monkey3.friday.txt 

Note that the % prefix is used to pass dash-containig arguments down
to the command. Now the cool/weird thing is that you can use another rule to add more
arguments to the same command. Here, some special case handling is
done for monkey 2:

--command
--match --out --once 'pools/monkey2.collected'
--once --option
--once --in ./compensate.for.monkey2.R

Now the second rule generated becomes:

pools/monkey2.collected: monkey2.wednesday.txt monkey2.thursday.txt\
./aggregate.R ./compensate-for-monkey2.R
	 ./aggreate.R -o pools/monkey1.collected monkey2.wednesday.txt\
         monkey2.thursday.txt --option ./compensate-for-monkey2.R

while the other rules are unchanged.

Use --help to see a list of all applicable arguments and flags.
"""

verbose = False

class _AttributeHolder(object):
    """Abstract base class that provides __repr__.

    The __repr__ method returns a string in the format::
        ClassName(attr=name, attr=name, ...)
    The attributes are determined either by a class-level attribute,
    '_kwarg_names', or by inspecting the instance __dict__.
    """
    def __repr__(self):
        type_name = type(self).__name__
        arg_strings = []
        for arg in self._get_args():
            arg_strings.append(repr(arg))
        for name, value in self._get_kwargs():
            arg_strings.append('%s=%r' % (name, value))
        return '%s(%s)' % (type_name, ', '.join(arg_strings))

    def _get_kwargs(self):
        return sorted(self.__dict__.items())

    def _get_args(self):
        return []

class Word(_AttributeHolder):
    """A component of a rule, has a pattern and a number of flags."""
    def __init__(self, pattern = "", pattern__ = None, match = False,
                 input = False, output=False, listing=False, once=False,
                 phony=False, intermediate=False, invisible=False, mkdir=False):
        self.pattern      = pattern
        self.pattern__    = pattern__
        self.match        = match
        self.input        = input
        self.output       = output
        self.once         = once
        self.listing      = listing
        self.phony        = phony
        self.mkdir        = mkdir
        self.intermediate = intermediate
        self.invisible    = invisible

class UnmatchedWord(Word):
    def tryMatch(self, filename):
        """return a matched word, or None"""
        if self.match:
            if self.pattern__ is None:
                self.pattern__ = re.compile(self.pattern)
            match = re.match(self.pattern__, filename)
            if match:
                return MatchedWord(self, rematch=match)

    def subst(self, matched):
        """Uses a string to format the matched groups"""
        if self.match:
            raise Exception("Can't have a second matching argument "
                            "({0}) in a command".format(self.pattern))
        return SubstitutedWord(self, rematch=matched.rematch)

class MatchedWord(Word):
    def __init__(self, copyfrom, rematch):
        """Initialize from a template word and a regex match"""
        self.rematch = rematch
        self.word = rematch.string
        super(MatchedWord,self).__init__(**(copyfrom.__dict__))
        if type(self.word) is not str:
            print("oops!")
            pass

    def groups(self):
        return self.rematch.groups()

    def __setattr__(self, attr, value):
        if attr == "word" and type(value) is not str:
            print("oops!")
            pass
        super(MatchedWord, self).__setattr__(attr, value)


class SubstitutedWord(Word):
    def __init__(self, copyfrom, rematch):
        """Initialize from a matched word and a substitution"""
        self.word = copyfrom.pattern.format(*(rematch.groups()))
        super(SubstitutedWord,self).__init__(**(copyfrom.__dict__))
                
class Command(_AttributeHolder):
    def __init__(self, words=None):
        if words is not None:
            self.words = list(words);
        else:
            self.words = [];

    def tryMatch(self,filename):
        #check for exactly one matcher
        if len([i for i in self.words if i.match]) != 1:
            raise Exception("Must have exactly one --match argument, in command {0}"
                            .format(self.description()))
        matches = [i.tryMatch(filename) for i in self.words]
        theMatch = [i for i in matches if i is not None]
        if len(theMatch) <= 0:
            return None
        theMatch = theMatch[0]
        matchedWords = [match if match is not None else word.subst(theMatch)
                        for (match, word) in zip(matches, self.words)]
        return MatchedCommand(words=matchedWords)

    def description(self):
        return " ".join([i.pattern for i in self.words])

def getList(listfile):
    if os.access(listfile, os.F_OK):
        with file(listfile, 'r') as f:
            return [i.strip() for i in f.readlines()]
    else:
        return []
        
class MatchedCommand(Command):
    def products(self):
        listed = [i 
                  for word in self.words
                  if word.output and word.listing
                  for i in getList(word.word)]
        return listed + [word.word for word in self.words if word.output]

    def dependencies(self):
        listed = [i
                  for word in self.words
                  if word.input and word.listing
                  for i in getList(word.word)]
        return listed + [word.word for word in self.words if word.input]

    def merge(self, *others):
        ##add the words in order. If "once" is used, the first word determines the flags.
        ##And "once" must be marked on the first word
        wordsSeen = {}
        words = []
        for word in sum([x.words for x in [self] + list(others)], []):
            if not (wordsSeen.has_key(word.word) and wordsSeen[word.word].once):
                words.append(word)
                if not wordsSeen.has_key(word.word):
                    wordsSeen[word.word] = word
        self.words = words

        
    def makeRule(self):
        return (
            "{products}: {dependencies}\n"
            "{mkdir_if_necessary}"
            "{command_indent}{command}\n"
            "\n"
            "{phony_rule}"
            "{intermediate_rule}"
            "{listing_rule}"
            "{update_targets}"
            ).format(**
                { 'products'          : " ".join(set(self.products()))
                , 'dependencies'      : " ".join(set(self.dependencies()))
                , 'command_indent'    : "\t" if False in [bool(i.invisible) for i in self.words] else ""
                , 'command'           : self.commandLine()
                , 'phony_rule'        : self.phonyRule()
                , 'intermediate_rule' : self.intermediateRule()
                , 'mkdir_if_necessary': self.mkdirCommands() if self.commandLine() else ""
                , 'listing_rule'      : self.listingRule()
                , 'update_targets'    : ('ALL_TARGETS += $(filter-out $(ALL_TARGETS), {0})\n\n'
                                         .format(" ".join(self.products()
                                                          + self.dependencies())))
                })

    def listingRule(self):
        if [w for w in self.words if w.listing]:
            #changes in output list files should trigger a reboot.
            #as should changes in input list file.
            return ("$(CURDIR)/$(lastword $(MAKEFILE_LIST)): {0}\n\n"
                    .format(" ".join(x.word for x in self.words if x.listing)))
        else:
            return ""
        

    def mkdirCommands(self):
        targets = [word.word for word in self.words if word.mkdir]
        dirs = [os.path.split(x)[0] for x in targets]
        if dirs:
            return "\t" + "\n\t".join(["mkdir -p {0}".format(i) for i in dirs if i != ""]) + "\n"
        else:
            return ""

    def phonyRule(self):
        phonyWords = [x for x in self.words if x.phony]

        if phonyWords:
            phonyRule = "\n\n".join(["{0}: {1}".format(x.word, " ".join(self.products()))
                                        for x in phonyWords if not (x.output or x.input)])
            phonyDecl = "\n\n.PHONY: {0}\n\n".format(" ".join([x.word for x in phonyWords]))
            return phonyRule + phonyDecl
        else:
            return ""

    def intermediateRule(self):
        intermediateTargets = [x.word for x in self.words if x.intermediate]

        if intermediateTargets:
            return ".INTERMEDIATE: {0}\n\n".format(" ".join(intermediateTargets))
        else:
            return ""

    def commandLine(self):
        return " ".join([i.word for   i  in self.words if not i.invisible])

def unique(seq, idfun=id):
    # order preserving prune of a list by object identity
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result

def generateRules(files, commands, maxdepth, maxfiles, verbose=False):
    files = list(files)

    ##track the commands used to generate each target.
    commandsDict = dict([(x, None) for x in files])
    
    ##track the depth of generation for both targets and dependencies of rules.
    depthDict = dict([(x, 0) for x in files])

    ##For each target in order try matching a command pattern against
    ##it. When a new target is generated, extend the file list (that
    ##you are iterating over.)

    for consideredTarget in files:
        for commandPattern in commands:
            matchedCommand = commandPattern.tryMatch(consideredTarget)
            if matchedCommand is not None:
                if verbose:
                    print('-'*3)
                    print("matched: {0}".format(consideredTarget))
                    print("with command: {0}".format(matchedCommand.description()))
                #See what files are produced by this command.
                #Add them to the products list for perusal.
                products = matchedCommand.products()
                #Are some of these products already being produced?
                #If so the commands will have to be merged.
                previousCommands = unique([commandsDict[o] for o in products
                                     if commandsDict.has_key(o)
                                     and commandsDict[o] is not None])
                targetsWereCovered = unique([i
                                             for c in previousCommands
                                             for i in c.products()])
                [commandsDict.pop(i) for i in unique(targetsWereCovered, lambda a:a)]
                
                if len(previousCommands) > 0:
                    mergedCommand = previousCommands[0]
                    mergedCommand.merge(*(previousCommands[1:] + [matchedCommand]))
                    if verbose:
                        print("merged into command: {0}".format(mergedCommand.commandLine()))
                else:
                    mergedCommand = matchedCommand

                newProducts = mergedCommand.products()
                newDependencies = mergedCommand.dependencies()
                prevDepth = depthDict[consideredTarget]

                if prevDepth >= maxdepth:
                    raise Exception("target generation went too deep at {}"
                                    .format(consideredTarget))

                for i in newProducts:
                    commandsDict[i] = mergedCommand

                newFiles = [p for p in newProducts + newDependencies
                            if not depthDict.has_key(p)]
                if verbose:
                    print("new files (depth {0}): {1}".format(prevDepth+1, " ".join(newFiles)))
                files.extend(newFiles)

                if len(files) >= maxfiles:
                    raise Exception("too many files generated at {}"
                                    .format(consideredTarget))

                for i in newProducts + newDependencies:
                    depthDict[i] = prevDepth+1

                # [print(i.makeRule()) for i in
                #  unique([commandsDict[i] for i in files
                #          if commandsDict.has_key(i)
                #          and commandsDict[i] is not None])]
                # print('-'*80)

    ##return commands uniquely in order of creation.
    return unique([commandsDict[i] for i in files
                   if commandsDict.has_key(i)
                   and commandsDict[i] is not None])

class ShlexArgParser(argparse.ArgumentParser):
    def convert_arg_line_to_args(self, arg_line):
        import shlex
        return shlex.split(arg_line, comments=True)

def makeparser():
    """The command line argument parser."""
    theWord = [UnmatchedWord()]

    class AddWords(argparse.Action):
        def __call__(self, parser, namespace, values, option_string):
            for w in values:
                if w.startswith('%'):
                    w = w[1:]
                self.addWord(namespace, w)

        def addWord(self, namespace, word):
            theWord[0].pattern = word
            namespace.commands[-1].words.extend(theWord)
            theWord[0] = UnmatchedWord()

    class StartCommand(AddWords):
        def __call__(self, parser, namespace, values, option_string):
            x = getattr(namespace, "commands", None)
            if x:
                x.append(Command())
            else:
                namespace.commands = [Command()]
            super(StartCommand, self).__call__(parser, namespace, values, option_string)
            
    class SetFlag(AddWords):
        def __call__(self, parser, namespace, values, option_string):
            flagname = option_string.replace("--", "")
            if getattr(theWord[0], flagname) is not None:
                setattr(theWord[0], flagname, True)
            super(SetFlag, self).__call__(parser, namespace, values, option_string)

    
    parser = ShlexArgParser(description=longhelp, fromfile_prefix_chars="@")

    parser.add_argument("--command",
                        help="Begin a command definition.",
                        action=StartCommand, nargs="*", dest="")
    parser.add_argument("--verbose", action='store_true',
                        help="Make a chatty printout to stderr about every "
                        "file that is matched.")
    parser.add_argument('--match', action=SetFlag, nargs='*', dest="",
                        help="The next word specifies a regexp pattern to match "
                        "against available files. (Without --match, it is a regexp "
                        "replacement pattern. Exactly one word in a command must "
                        "be a match)",)
    parser.add_argument('--input', action=SetFlag, nargs='*', dest="",
                        help="The next word specifies an input file.")
    parser.add_argument('--output', action=SetFlag, nargs='*', dest="",
                        help="The next word specifies an output file.")
    parser.add_argument('--once', action=SetFlag, nargs='*', dest="",
                        help="The word will only be included once. (the "
                        "first such word must be marked 'once' for it to "
                        "have meaning)")
    parser.add_argument('--listing',
                        help="The next word specifies a file that lists the "
                        "input files consumed or outputs produced.",
                        action=SetFlag, nargs='*', dest="")
    parser.add_argument('--phony', action=SetFlag, nargs='*', dest="",
                        help="The next word specifies a phony target which "
                        "will depend on the outputs of this command.")
    parser.add_argument('--mkdir', action=SetFlag, nargs='*', dest="",
                        help="An enclosing directory will be made (using mkdir -p) "
                        "if one does not already exist.")
    parser.add_argument('--intermediate',
                        help="The next word specifies an intermediate target",
                        action=SetFlag, nargs='*', dest="")
    parser.add_argument('--invisible', action=SetFlag, nargs='*', dest="",
                        help="This word will not be copied to the command line.")

    parser.add_argument('--maxdepth', nargs=1, default=100, type=int,
                        help="The maximum depth of file "
                        "generation to tolerate. (default: 100)")
    parser.add_argument('--maxfiles', nargs=1, default=10000, type=int,
                        help="The maximum number of targets "
                        "to consider. (default 10000)")
    
    parser.add_argument('--files', nargs='*',
                        help="The base set of files that are to be processed.")
    return parser

def test():
    """This exercises the various features of the makefile generator. I know I
    should break down the functionality into multiple unit tests,
    but not sure how to test other than by inspection."""
    
    with open("input.list", 'w') as f:
        print("datafiles/foo.txt", "datafiles/bar.txt", "datafiles/baz.txt",
              file=f, sep="\n")

    with open("output.list", 'w') as f:
        print("sqlfiles/wibble.sql", "sqlfiles/wobble.sql", "sqlfiles/wubble.sql",
              file=f, sep="\n")
    
    testargs = ('--command '
                '--once --input ./aggregate.R '
                '--once --output --mkdir pools/{0}.collected '
                '--match --input datafiles/([^.]*)\.(.*).txt '
                '--invisible --phony --once aggregates '
                
                '--command '
                '--match --output --once pools/monkey2.collected '
                '--invisible --input ./compensate.for.monkey2.R '
                '%--option=./compensate.for.monkey2.R '

                '--command --input ./tosql '
                '--match --input datafiles/(.*)\.txt '
                '--output --intermediate sqlfiles/{0}.sql '
                
                '--command --input ./dbshove.R '
                'database.db '
                '--match --input sqlfiles/(.*)\.sql '
                '&& touch --output dbtickets/{0}.put '
                '--phony --invisible dbupdated '

                '--command '
                '--output --invisible database.db '
                '--input --invisible --match dbupdated '

                '--command --once corge '
                '--output --once --listing output.list '
                '--input --match dbtickets/(.*).put '

                '--command check --output {0}.check --input --match --listing (.*).list '
                
                '--command '
                '--phony --output --invisible --once buildAll '
                '--input --invisible --match .* '
                
                '--files datafiles/monkey1.monday.txt datafiles/monkey1.tuesday.txt '
                'datafiles/monkey2.wednesday.txt datafiles/monkey2.thursday.txt '
                'datafiles/monkey3.friday.txt input.list'
                )
    goFromString(testargs)

def testDepth():
    testargs = ('--command cp '
                '--match --input (.*).a '
                '--output {0}.a.a '
                ''
                '--files foo.a')
    goFromString(testargs)

def testBreadth():
    testargs = ('--command cp '
                '--match --input (.*.(a|b)) '
                '--output {0}.a '
                '&& cp {0} '
                '--output {0}.b '
                '--files test.a')
    goFromString(testargs)
    

def goFromString(str):
    parser = makeparser()
    ns = parser.parse_args(re.split(" +", str), namespace=argparse.Namespace(commands=[]))
    go(**ns.__dict__)

def go(**kwargs):
    kwargs.pop("")
    rules = generateRules(**kwargs)
    [print(i.makeRule()) for i in rules]

if __name__ == "__main__":
    parser = makeparser()
    ns = parser.parse_args(namespace=argparse.Namespace(commands=[], files=[]))
    go(**ns.__dict__)


##TODO
    
    ##1. Think about reworking to have multimatching rules as follows:
    ##(zero match args; just make a command.  Two match args, make a
    ##partal match at one argument which is another (self-removing)
    ##rule; and finish at another. Will have to do something clever
    ##with the formatting strings.
    
    ##2. Intelligent escaping of command words that must go back
    ##through Make and shell script (that can be bypassed if you want
    ##to use a Make special variable...)

    ##3. Give a warning when combining words with --once if any of the
    ##flags differ.

    ##4. Maybe more warnings/errors for nonsensical flags or combinations of flags.

                                        #!/usr/bin/env python
from __future__ import print_function
import sys, monk, unittest, time, datetime, os, subprocess, contextlib, StringIO

@contextlib.contextmanager
def capture():
    oldout, olderr = sys.stdout, sys.stderr
    out = (StringIO.StringIO(), StringIO.StringIO())
    sys.stdout, sys.stderr = out
    yield out
    sys.stdout, sys.stderr = oldout, olderr
    out[0].close()
    out[1].close()

@contextlib.contextmanager
def directory(dir):
    old_dir = os.getcwd()
    try:
        os.chdir(dir)
    except OSError:
        os.mkdir(dir)
        os.chdir(dir)
    yield
    os.chdir(old_dir)

@contextlib.contextmanager
def temporaryFile(name, mode='w', *args, **kwargs):
    f = file(name, mode, *args, **kwargs)
    yield f
    close(f)
    os.unlink(name)

@contextlib.contextmanager
def touchFiles(files):
    #create and touch all the files in order with 1 sec
    #difference between mtimes. argument is a lsit of tuples of file and contents
    the_time = datetime.datetime.now()
    to_unlink = list()
    to_rmdir = list()
    try:
        for (name, contents) in files:
            ## IN MEDIAS: need to make the directories needed (easy,
            ## use os.path.makedirs) and clean them up afterwards (harder if
            ## you use makedirs)
            with file(name, 'w') as f:
                to_unlink.append(name)
                if (contents is not None):
                    f.writelines("\n".join(contents))
            newtime = time.mktime(the_time.timetuple())
            os.utime(name, (newtime, newtime))
            the_time = the_time + datetime.timedelta(0,1)
        yield
    finally:
        for name in reversed(to_unlink):
            os.unlink(name)
        for name in reversed(to_rmdir):
            os.rmdir(name)

class MonkTestCase(unittest.TestCase):
    #the prototypical test case is to create a number of files, a
    #string defining commands, a target to make, and a list of
    #commands to expect make to execute.

    def setUp(self, args=[], files={}, commands=[], targets = []):
        self.args = args
        self.files = files
        self.command = commands
        self.targets = targets
        self.commands = commands
        unittest.TestCase.setUp(self)

    def doTheTest(self, args=None, files=None, commands=None, targets = []):
        """Interpret the arguments given in args; create the specified
        files with the specified contents and their timestamps in the
        specified order; check that the commands emitted by running Make
        on the resulting Makefile are the same as the examples given."""
        args = self.args if args is None else args
        files = self.files if files is None else files
        targets = self.targets if len(targets) == 0 else targets
        commands = self.commands if commands is None else commands

        #work in "temp" subdir whatever directory the test is in atmo
        tempdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "temp")
        with directory(tempdir):
            with touchFiles(files):
                #capture stdout/stderr in strings
                with capture() as (out, err):
                    monk.goFromString(args)
                    monk_output = out.getvalue()
                    monk_errors = err.getvalue()

                print(monk_errors, file=sys.stderr)
                # and see what 'make' executes of it
                with temporaryFile('Makefile', 'w') as f:
                    f.write(monk_output)
                    #shell=echo supposedly catches catches all commands
                    #executed by MAKE (without running them)
                    #though we might need a temp fifo for it...
                    p = subprocess.Popen(
                        ["make", "SHELL=echo"] + targets,
                        stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                    (make_out, make_err) = p.communicate()
                    print(make_err, file=sys.stderr)
                    #assert that they match the same commands (in order?)
                    if (commands is not None):
                        try:
                            self.assertEquals(make_out.split("\n"), commands)
                        except:
                            import pdb
                            pdb.set_trace()

class OtherTestCase(unittest.TestCase):
    def testBreadth(self):
        testargs = ('--command cp '
                    '--match --input (.*).a '
                    '--output {0}.a.a '
                    ''
                    '--files foo.a')
        self.assertRaises(Exception, monk.goFromString, testargs)

    def testDepth(self):
        testargs = ('--command cp '
                    '--match --input (.*.(a|b)) '
                    '--output {0}.a '
                    '&& cp {0} '
                    '--output {0}.b '
                    '--files test.a')
        self.assertRaises(Exception, monk.goFromString, testargs)

class BigDumbTestCase(MonkTestCase):
    """tests using the too-large set of arguments defined below."""

    def setUp(self, *args, **kwargs):
        MonkTestCase.setUp(
            self,
            args = bigDumbTestArgs,
            files = [("dbshove.R", None),
                     ("datafiles/monkey1.monday.txt", None),
                     ("datafiles/monkey1.tuesday.txt", None),
                     ("datafiles/monkey2.wednesday.txt", None),
                     ("datafiles/monkey2.thursday.txt", None),
                     ("datafiles/monkey3.friday.txt", None),
                     ("datafiles:monkey1.monday.txt", None),
                     ("input.list",  ["datafiles/foo.txt",
                                      "datafiles/bar.txt",
                                      "datafiles/baz.txt"]),
                     ("output.list",  ["sqlfiles/wibble.sql",
                                       "sqlfiles/wobble.sql",
                                       "sqlfiles/wubble.sql"])])

    def testBasic(self):
        self.doTheTest(targets=["buildAll"], commands=[])

bigDumbTestArgs = """
--command
--once --input ./aggregate.R
--once --output --mkdir pools/{0}.collected
--match --input datafiles/([^.]*)\\\\..*\\\\.txt
--invisible --phony --once aggregates

--command
--match --output --once pools/monkey2.collected
--invisible --input ./compensate.for.monkey2.R
%--option=./compensate.for.monkey2.R

--command --input ./tosql
--match --input datafiles/(.*)\\\\.txt
--output --intermediate sqlfiles/{0}.sql

--command --input ./dbshove.R database.db
--match --input sqlfiles/(.*)\\\\.sql
&& touch --output dbtickets/{0}.out
--phony --invisible dbupdated

--command
--output --invisible --tagged database.db
--input --invisible --match dbtickets/.*.out

--command doTheThing --input --match pools/(.*)\\\\.collected
--output --mkdir graphs/{0}.graph1.out
--output --mkdir graphs/{0}.graph2.out

--pushdir graphs
--command --once --input --match (.*).graph
--output --once grouped.graph
--popdir

--command --once corge
--output --once --listing output.list
--input --match dbtickets/(.*).out

--command check
--output {0}.check
--input --match --listing (.*).list

--command
--phony --output --invisible --once buildAll
--input --invisible --match '.*'

--files datafiles/monkey1.monday.txt datafiles/monkey1.tuesday.txt
datafiles/monkey2.wednesday.txt datafiles/monkey2.thursday.txt
datafiles/monkey3.friday.txt input.list"""

def main():
    unittest.main()

if __name__ == "__main__":
    unittest.main()

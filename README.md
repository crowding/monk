# monk

There are many ad-hoc build systems. This one is mine.

Design goals are:

* Be small enough to just include in whatever project, with minimal
  dependencies (Make and Python2.6+)
* Encode some patterns about how to do things that are tricky in Make,
  like:
    * automatic dependency discovery;
    * commands that produce multiple outputs;
    * commands whose outputs can't be predicted until they're run;
    * data-build steps where any of the data, the script that processes the
      data, or the library that the script imports may change;
* Support things Make doesn't, like regexp patterns in rules
* Be language agnostic. The interface for doing things just issuing
  shell commands. You have heavy lifting to do, make it a script
  that's explicitly a step in your build process. This also makes it
  play nicely with other ad hoc build systems like latexmk.
* Don't frigging turn it into its own turing complete language[*][].

It works by generating targets forward by substituting regexps until
it runs out of rules. Then it spits out a simple Makefile, and you use
Make to actually run the build. If it isn't doing what you want, you
can look at the generated Makefile to see what it thinks it's doing.

The syntax is dumb (an overgrown getopt parser, so every keyword
begins with `--`).

Testing has been based on "does it build my project," there few unit
tests.

[*] sure, iterated regexp substitutions are technically turing
complete, whatevs. The point is you would never be tempted to do the
horrible things that people do with Make macros.

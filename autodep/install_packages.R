#!/usr/bin/env Rscript #Download and install necessary packages.
options(warn=2)
#install.packages farts warnings instead of errors if
#it can't install in the given library, which is totally
#ridiculous

install.calls <- alist(
    ptools=install_github,
    vadr=install_github,
    install.packages)

install.opts <- alist(
    ptools = alist(username="crowding"),
    rstan = alist(repos = c(getOption("repos"),
                    rstan = "http://wiki.stan.googlecode.com/git/R"),
        type = "source"),
    alist())

install.opts.global <- alist(lib=normalizePath(install.dir))

main <- function(install.dir, ...) {
  library(methods) #workaround; http://bit.ly/10Fw09j
  if (!require(devtools)) {
    install.packages(devtools)
    library(devtools)
  }

  if (!"." %in% dir(install.dir, all.files=TRUE))
    stop("install.dir is not a real directory")

  # move that to the front for install.github?
  .libPaths(c(install.dir, .libPaths()))

  packages.i.need <- do.call(Reduce, list(union, lapply(c(...), getLines)))
  packages.i.have <- .packages(all.available=TRUE)

  if (length(setdiff(packages.i.need, packages.i.have)) > 0) {
    for (i in setdiff(packages.i.need, packages.i.have)) {
      installer.call <- call(do.call(`switch`, c(i, install.calls)))
      installer.args <- c(do.call(`switch`, c(i, install.opts)),
                          install.opts.global,
                          list(i))
      do.call(installer.call, installer.args)
    }
  }
}

getLines <- function(file) {
  lines <- readLines(file)
  gsub("^\\s+|\\s+$", "", lines)
}

if ("--slave" %in% commandArgs()) {
  args <- commandArgs(trailingOnly=TRUE)
  do.call("main", as.list(args))
}

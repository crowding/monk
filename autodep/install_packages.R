#!/usr/bin/env Rscript #Download and install necessary packages.
options(warn=2)
#install.packages farts warnings instead of errors if
#it can't install in the given library, which is totally
#ridiculous

main <- function(install.dir, ...) {
  if (!"." %in% dir(install.dir, all.files=TRUE)) 
    stop("install.dir is not a real directory")

  # move that to the front for install.github
  .libPaths(c(install.dir, .libPaths()))

  packages.i.need <- do.call(Reduce, list(
    union, c("devtools", lapply(c(...), getLines))))
  packages.i.github <- c(ptools="ptools")
  github.user <- c(ptools="crowding")
  packages.i.have <- .packages(all.available=TRUE)

  if (length(setdiff(packages.i.need, packages.i.have)) > 0) {
    install.packages(setdiff(packages.i.need, packages.i.have),
                     repos = c(
                       CRAN = "http://cran.r-project.org/",
                       RForge="http://R-Forge.R-project.org/"
                       ),
                     lib=normalizePath(install.dir))
  }

  for (i in setdiff(names(packages.i.github), packages.i.have)) {
    library(methods) #workaround; http://bit.ly/10Fw09j
    library(devtools)
    install_github(packages.i.github[[i]],
                   username=github.user[[i]])
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

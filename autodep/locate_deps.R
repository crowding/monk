##this script attempts to determine, for an R script file, the
##packages and other script files that is includes. It is done simply
##by scanning for "source", "library" and "require" statements.

##Command line arguments: file.to.scan list.of.packages list.of.scripts
library(methods)

theDir = ""

findlibs <- function(expr, ...) {
  ##Each submethod recursively scans for calls to library, require,
  ##and/or source and prints matches to the connections.
  UseMethod("findlibs")
}

findlibs.expression <- function(expr, pkgConn=stdout(), srcConn=stdout()) {
  findlibs(as.list(expr), pkgConn, srcConn)
}

findlibs.call <- function(call, pkgConn=stdout(), srcConn=stdout(), ...) {
  if (any(call[[1]] == c("library", "require"))) {
    args <- match.call(getFunction(as.character(call[[1]])), call)
    if (!is.null(args$package) && (is.character(args$package) || is.name(args$package))) {
      writeLines(as.character(args$package), pkgConn)
    }
  } else if (any(call[[1]] == c("source", "load"))) {
    args <- match.call(getFunction(as.character(call[[1]])), call)
    #it's a sourcing...
    if (!is.null(args$file) && (is.character(args$file))) {
      #it's a source file.
      if (theDir != "") {
        writeLines(as.character(file.path(theDir, args$file)), srcConn)
      } else {
        writeLines(as.character(args$file), srcConn)
      }
    }
  } else {
    findlibs(as.list(call), pkgConn, srcConn)
  }
}

findlibs.list <- function(list, pkgConn=stdout(), srcConn=stdout()) {
  do.call(c, lapply(list, findlibs, pkgConn, srcConn))
}

findlibs.default <- function(x, pkgConn=stdout(), srcConn=stdout()) {
  if (is.call(x)) {
    findlibs.call(x, pkgConn, srcConn)
  } else NULL
}

main <- function(rFile, pkgFile, srcFile) {
  if (rFile != basename(rFile)) {
    theDir <<- dirname(rFile)
  }
  pkgConn <- file(pkgFile, 'w')
  on.exit(close(pkgConn), add=TRUE)

  srcConn <- file(srcFile, 'w')
  on.exit(close(srcConn), add=TRUE)

  expr <- parse(rFile)
  invisible(findlibs(expr, pkgConn, srcConn))
}

if ("--slave" %in% commandArgs()) {
  args <- commandArgs(trailingOnly=TRUE)
  do.call("main", as.list(args))
}

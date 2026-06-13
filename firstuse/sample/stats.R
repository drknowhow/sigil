# R sample for the v2 R-frontend lift test.
library(jsonlite)

analyze <- function(xs) {
  m <- mean(xs)
  s <- sd(xs)
  list(mean = m, sd = s)
}

load_data <- function(path) {
  read.csv(path)
}

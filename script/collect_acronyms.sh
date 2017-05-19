#!/bin/bash

cat $1 | tr -cs "A-Z." "\n"| egrep "[A-Z\.?]{2,6}" | tr -d "." | sort | uniq -c | sort -n -r | awk 'BEGIN{FS=" "; OFS="|"} {if (length($2) > 1) {print $2, $1} }' > $1.acro
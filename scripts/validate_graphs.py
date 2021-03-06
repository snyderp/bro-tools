#!/usr/bin/env python
"""Builds graphs from the lines in a gziped bro log in a temporary location,
echos out the number of records incorporated into graphs in the process.  This
script is really only useful as a sanatiy check to see how we'll we're doing,
and making sure that all expected files are being brough into a graph.

Paths to bro-log records are read in from stdin, and each resulting count
is written to stdout

"""
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from brotools.graphs import graphs
from brotools.reports import record_filter
import gzip

for path in sys.stdin:
    with gzip.open(path.strip(), 'rb') as h:
        print sum([len(g) for g in graphs(h, record_filter=record_filter)])

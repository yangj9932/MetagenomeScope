# Settings that can be used to alter the output received by the script and
# by GraphViz.
# Generally, each variable or group of variables contains a explanatory
# comment above its declaration below. Default values are placed to the
# right of each variable.

from math import sqrt

# How many connected components to display. Displays largest (by number of
# nodes) components first -- so MAX_COMPONENTS = 1 displays only the largest
# component, = 2 displays only the two largest components, etc.
# Setting this to None will just display all components.
# If MAX_COMPONENTS > the actual number of components in the graph, all
# components (with size >= MIN_COMPONENT_SIZE)  will be displayed.
MAX_COMPONENTS = None
# Minimum number of contigs for a connected component to be laid out by
# GraphViz. This is to avoid laying out a ton of small, unconnected groups
# of nodes.
# (If you want to lay out all connected components, even ones containing
# single nodes, then you can set MIN_COMPONENT_SIZE to 0.)
# As an example, if a graph contains 5 connected components:
# -One with 20 nodes
# -One with 10 nodes
# -One with  5 nodes
# -Two with  1 node each
# And MIN_COMPONENT_SIZE is set to 10, then even if MAX_COMPONENTS == None
# or MAX_COMPONENTS > 2, only the first two connected components will be
# displayed.
MIN_COMPONENT_SIZE = 5

# If we opt not to use one or both of the bounds here, we can set these to
# float("inf") or float("-inf"), respectively.
MAX_CONTIG_AREA = 5
MIN_CONTIG_AREA = 0.5
MAX_CONTIG_HEIGHT = sqrt(MAX_CONTIG_AREA)
MIN_CONTIG_HEIGHT = sqrt(MIN_CONTIG_AREA)
WIDTH_HEIGHT_RATIO = 1.0

### Frequently-used GraphViz settings ###
# More info on these available at www.graphviz.org/doc/info/attrs.html
# To make things simple, these constants don't use "exterior" semicolons
# NOTE -- to get nodes to look more like BAMBUS', use headport=e,tailport=w in
# GLOBALEDGE_STYLE and rotate=90 in GRAPH_STYLE.
BASIC_NODE_SHAPE = "invhouse"
RCOMP_NODE_SHAPE = "house"
BUBBLE_SHAPE     = "square" # not used for collate_clusters.py
FRAYEDROPE_SHAPE = "square" # not used for collate_clusters.py
CHAIN_SHAPE      = "square" # not used for collate_clusters.py
CYCLE_SHAPE      = "square" # not used for collate_clusters.py
ROUNDED_UP_STYLE = "style=filled,fillcolor=gray64" # we don't use these now
ROUNDED_DN_STYLE = "style=filled,fillcolor=black"  # we don't use these now
CCOMPONENT_STYLE = "style=filled,fillcolor=red"    # we don't use these now
BUBBLE_STYLE     = "\tstyle=filled;\n\tfillcolor=cornflowerblue;\n"
FRAYEDROPE_STYLE = "\tstyle=filled;\n\tfillcolor=green;\n"
CHAIN_STYLE      = "\tstyle=filled;\n\tfillcolor=salmon;\n"
CYCLE_STYLE      = "\tstyle=filled;\n\tfillcolor=darkgoldenrod1;\n"

### Global graph settings (applied to every node/edge/etc. in the graph) ###
# General graph style. Feel free to insert newlines for readability.
# Leaving this empty is also fine, if you just want default graph-wide settings
GRAPH_STYLE      = "rotate=90"

# Style applied to every node in the graph.
# NOTE -- fixedsize=true ensures accaccurate node scaling
GLOBALNODE_STYLE = ""

# Style applied to every edge in the graph.
# NOTE: "dir=none" gives "undirected" edges
GLOBALEDGE_STYLE = "headport=n,tailport=s"

# The filename suffixes indicating a file is of a certain type.
# Ideally, we should be able to detect what filetype an assembly file is by
# just looking at it, but for now this is an okay workaround.
LASTGRAPH_SUFFIX = "LastGraph"
GRAPHML_SUFFIX   = ".gml"

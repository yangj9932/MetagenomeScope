# Copyright (C) 2017-2018 Marcus Fedarko, Jay Ghurye, Todd Treangen, Mihai Pop
# Authored by Marcus Fedarko
#
# This file is part of MetagenomeScope.
# 
# MetagenomeScope is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MetagenomeScope is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MetagenomeScope.  If not, see <http://www.gnu.org/licenses/>.
####
# This file contains various objects defining nodes, node groups, edges, etc.
# in the graph. We use these objects to simplify the process of storing
# information about the graph.

import config
from math import log, sqrt
from collections import deque
import pygraphviz
import uuid

class Edge(object):
    """A generic edge, used for storing layout data (e.g. control points)
       and, if applicable for this type of assembly file, biological
       metadata (e.g. multiplicity).
    """
    def __init__(self, source_id, target_id, multiplicity=None,
            orientation=None, mean=None, stdev=None):
        """Initializes the edge and all of its attributes."""
        self.source_id = source_id
        self.target_id = target_id
        # Refers to either multiplicity (in LastGraph files) or bundle size (in
        # Bambus 3's GML files)
        self.multiplicity = multiplicity
        # Used to characterize edges in Bambus 3's GML files. Can be one of
        # four possible options: "BB", "BE", "EB", or "EE".
        self.orientation = orientation
        # Per Jay: "estimated distance between two contigs if they are part of
        # the same scaffold. If this number is negative, it means that these
        # contigs overlap by that many bases. If it is positive then there
        # exists a gap of that particular size between two contigs."
        # (For Bambus 3's GML files)
        self.mean = mean
        # For Bambus 3's GML files. I don't really know what this means
        self.stdev = stdev
        # We'll eventually assign this edge a "thickness" percentage somewhere
        # in the range [0, 1] (the actual process for doing that is in
        # collate.py). This attribute will contain that information.
        self.thickness = 0.5
        # If we calculate Tukey fences for the edge weights in the connected
        # component that this edge is in -- and if this edge is classified as
        # an outlier during that process -- then we'll set this attribute to
        # either -1 (if this edge is a "low" outlier) or 1 (if this edge is a
        # "high" outlier)
        # (if we don't calculate Tukey fences at all, or if we do but this edge
        # isn't classified as an outlier, then we keep this attribute as 0)
        self.is_outlier = 0
        # For if the edge is an "interior" edge of a node group
        self.group = None
        # Will be replaced with the size rank of the connected component to
        # which this edge belongs
        self.component_size_rank = -1
        # Misc. layout data that we'll eventually record here if we decide
        # to lay out the component in which this edge is stored
        self.xdot_ctrl_pt_str = None
        self.xdot_ctrl_pt_count  = None
        # used for interior edges in node groups
        self.xdot_rel_ctrl_pt_str = None

    @staticmethod
    def get_control_points(position):
        """Removes "startp" and "endp" data, if present, from a string
           definining the "position" attribute (i.e. the spline control
           points) of an edge object in pygraphviz.

           Also replaces all commas in the filtered string with spaces,
           to make splitting the string easier.

           Returns a 3-tuple of the filtered string, the split list of
           coordinates (in the format [x1, y1, x2, y2, ... , xn, yn] where
           each coordinate is a float), and the number of points specified by
           the coordinate list (equal to the length of the coordinate list
           divided by 2).

           Raises a ValueError if the number of remaining coordinates (i.e.
           the length of the split list to be returned) is not divisible by 2.

           See http://www.graphviz.org/doc/Dot.ref for more information on
           how splines work in GraphViz.
        """
        # Remove startp data
        if position.startswith("s,"):
            position = position[position.index(" ") + 1:]
        # remove endp data
        if position.startswith("e,"):
            position = position[position.index(" ") + 1:]
        points_str = position.replace(",", " ")
        coord_list = [float(c) for c in points_str.split()]
        if len(coord_list) % 2 != 0:
            raise ValueError, config.EDGE_CTRL_PT_ERR
        return points_str, coord_list, len(coord_list) / 2

    def db_values(self):
        """Returns a tuple containing the values of this edge.

           The tuple is created to be inserted into the "edges" database
           table.

           Should be called after parsing .xdot layout information for this
           edge.
        """
        group_id = None
        if self.group != None:
            group_id = self.group.cy_id_string
        return (self.source_id, self.target_id, self.multiplicity,
                self.thickness, self.is_outlier, self.orientation,
                self.mean, self.stdev, self.component_size_rank,
                self.xdot_ctrl_pt_str, self.xdot_ctrl_pt_count, group_id)

    def __repr__(self):
        return "Edge from %s to %s" % (self.source_id, self.target_id)

class Node(object):
    """A generic node. Used for representing individual contigs/scaffolds,
       and as the superclass for groups of nodes.
    """
    def __init__(self, id_string, bp, is_complement, depth=None,
                 gc_content=None, label=None, is_single=False, is_repeat=None):
        """Initializes the object. bp initially stood for "base pairs," but
           it really just means the length of this node. In single graphs
           that's measured in bp and in double graphs that's measured in nt.
           
           (Size scaling based on length is done in self.set_dimensions().)
        """
        self.id_string = id_string
        self.bp = bp
        self.depth = depth
        self.gc_content = gc_content
        self.label = label
        # Either 1 (is a repeat), 0 (is not a repeat), or None (not given)
        self.is_repeat = is_repeat
        # If True, we use the "flipped" node style
        self.is_complement = is_complement
        # If True, we draw nodes without direction -- NOTE -- this feature
        # isn't used at present, might be added in at a later time
        # (see https://github.com/marbl/MetagenomeScope/issues/4 for context)
        self.is_single = is_single
        # List of nodes to which this node has an outgoing edge
        self.outgoing_nodes = []
        # List of nodes from which this node has an incoming edge
        self.incoming_nodes = []
        # Dict of Edge objects that have this node as a source -- used for
        # storing/reading more detailed edge information, not used for graph
        # traversal. Edge objects are stored as values, and their
        # corresponding key is the sink (target) node ID of the edge.
        # ...e.g. for 1->2, 1->3, 1->4, outgoing_edge_objects would look like
        # {2: Edge(1, 2), 3: Edge(1, 3), 4: Edge(1, 4)}
        self.outgoing_edge_objects = {}
        # Flag variables we use to make DFS/finding connected components
        # more efficient (maintaining a list or dict of this info is more
        # expensive than just using attributes, like this)
        self.seen_in_dfs = False
        self.in_nodes_to_check = False
        self.seen_in_ccomponent = False
        self.used_in_collapsing = False
        # If we decide to subsume a node group into another node group,
        # thus removing the initial node group, we use this flag to
        # mark that node group to not be drawn.
        self.is_subsumed = False
        # When we collapse nodes into a node group, we change this variable
        # to reference the NodeGroup object in question
        self.group = None
        # Reference to the "size rank" (1 for largest, 2 for 2nd largest,
        # ...) of the connected component to which this node belongs.
        self.component_size_rank = -1
        # Misc. layout data that we'll eventually record here
        # The width/height attributes are technically slightly altered by
        # Graphviz during its layout process -- they're scaled to the nearest
        # integer point values. However, we preserve the original dimensions
        # for rendering them in the viewer interface.
        self.width  = None
        self.height = None
        self.xdot_x      = None
        self.xdot_y      = None
        self.xdot_shape  = None
        # Optional layout data (used for nodes within subgraphs)
        self.xdot_rel_x  = None
        self.xdot_rel_y  = None
        
    def set_dimensions(self):
        """Calculates the width and height of this node and assigns them to
           this node's self.width and self.height attributes, respectively.

           NOTE that "height" and "width" are relative to the default vertical
           layout of the nodes (from top to bottom) -- so height refers to the
           long side of the node and width refers to the short side.

           Some things to keep in mind:
           -self.bp has a minimum possible value of 1
           -self.bp has no maximum possible value, although in practice it'll
            probably be somewhere in the billions (at the time of writing this,
            the longest known genome seems to be Paris japonica's, at
            ~150 billion bp -- source:
            https://en.wikipedia.org/wiki/Paris_japonica)
           -It's desirable to have actual node area proportional to
            node length -- that is, height * width = (x)area for some x
        """
        def adjust_dim(dim):
            """Given a dimension of a node, returns either:
                -the dimension (if the dimension falls within the limits)
                -the max dimension (if the dimension is greater than the max)
                -the min dimension (if the dimension is less than the min)
            """
            if dim > config.MAX_CONTIG_DIM:
                return config.MAX_CONTIG_DIM
            elif dim < config.MIN_CONTIG_DIM:
                return config.MIN_CONTIG_DIM
            return dim

        #area = adjust_dim(log(self.bp, config.CONTIG_SCALING_LOG_BASE))
        # Old scaling method (what we're trying to change via issue #73).
        # Included here for reference.
        self.height = adjust_dim(log(self.bp, config.CONTIG_SCALING_LOG_BASE))
        self.width = sqrt(self.height)
        # Equilibrium scaling (equal width and height: produces "square"-like
        # node shapes).
        # self.height = sqrt(area)
        # self.width = sqrt(area)
        # Elongated scaling
        # self.height = area ** 0.75
        # self.width = area / self.height

    def get_shape(self):
        """Returns the shape "string" for this node."""
        
        if self.is_complement:
            return config.RCOMP_NODE_SHAPE
        elif self.is_single:
            return config.SINGLE_NODE_SHAPE
        else:
            return config.BASIC_NODE_SHAPE

    def node_info(self):
        """Returns a string representing this node that can be used in a .dot
           file for input to GraphViz.
        """
        self.set_dimensions()
        info = "\t%s [height=%g,width=%g,shape=" % \
                (self.id_string, self.height, self.width)
        info += self.get_shape()
        info += "];\n"
        return info

    def add_outgoing_edge(self, node2, multiplicity=None, orientation=None,
            mean=None, stdev=None):
        """Adds an outgoing edge from this node to another node, and adds an
           incoming edge from the other node referencing this node.

           Also adds an Edge with any specified data to this node's
           dict of outgoing Edge objects.
        """
        self.outgoing_nodes.append(node2)
        node2.incoming_nodes.append(self)
        self.outgoing_edge_objects[node2.id_string] = \
            Edge(self.id_string, node2.id_string, multiplicity=multiplicity,
                    orientation=orientation, mean=mean, stdev=stdev)

    def edge_info(self, constrained_nodes=None):
        """Returns a GraphViz-compatible string containing all information
           about outgoing edges from this node.

           Useful for only printing edges relevant to the nodes we're
           interested in.

           If constrained_nodes is not None, then it is interpreted as a list
           of nodes to "constrain" the edges: that is, edges pointing to the
           nodes within this list are the only edges whose info will be
           included in the returned string.
        """
        o = ""
        # Since we only care about the target ID and not about any other
        # edge data it's most efficient to just traverse self.outgoing_nodes
        for m in self.outgoing_nodes:
            if (constrained_nodes is None) or (m in constrained_nodes):
                o += "\t%s -> %s\n" % (self.id_string, m.id_string)
        return o

    def collapsed_edge_info(self):
        """Returns a GraphViz-compatible string (like in edge_info()) but:
        
           -Edges that have a .group attribute of None that point to/from
            nodes that have a .group attribute that != None will be
            reassigned (in the string) to point to/from those node groups.

           -Edges that have a .group attribute that != None will not be
            included in the string.
           
           -All edges will have a comment attribute of the format "a,b" where
            a is the id_string of the original source node of the edge (so,
            not a node group) and b is the id_string of the original target
            node of the edge.
        """
        o = ""
        if self.group != None:
            source_id = "cluster_" + self.group.gv_id_string
        else:
            source_id = self.id_string
        for m in self.outgoing_nodes:
            # Used to record the actual edge source/target
            comment = "[comment=\"%s,%s\"]" % (self.id_string, m.id_string)
            # Only record edges that are not in a group (however, this
            # includes edges potentially between groups)
            if self.outgoing_edge_objects[m.id_string].group == None:
                if m.group == None:
                    o += "\t%s -> %s %s\n" % (source_id, m.id_string, \
                        comment)
                else:
                    o += "\t%s -> %s %s\n" % (source_id, \
                        "cluster_" + m.group.gv_id_string, comment)
        return o

    def set_component_rank(self, component_size_rank):
        """Sets the component_size_rank property of this node and of all
           its outgoing edges.
        """
        self.component_size_rank = component_size_rank
        for e in self.outgoing_edge_objects.values():
            e.component_size_rank = component_size_rank

    def db_values(self):
        """Returns a tuple of the "values" of this Node.
        
           This value will be used to populate the database's "contigs"
           table with information about this node.
           
           Note that this doesn't really apply to NodeGroups, since they
           don't have most of these attributes defined. I'll define a more
           specific NodeGroup.db_values() function later.
           
           Also, this shouldn't be called until after this Node's layout
           information has been parsed from an .xdot file and recorded.
           (Unless we're "faking" the layout of this Node's component, in
           which case everything here should be accounted for anyway.)
        """
        # See collate.py for the most up-to-date specifications of how this
        # table is laid out.
        # The "parent cluster id" field can be either an ID or NULL
        # (where NULL denotes no parent cluster), so we decide that here.
        group_id = None
        if self.group != None:
            group_id = self.group.cy_id_string
        length = self.bp
        return (self.id_string, self.label, length, self.gc_content,
                self.depth, self.is_repeat, self.component_size_rank,
                self.xdot_x, self.xdot_y, self.width, self.height,
                self.xdot_shape, group_id)

    def __repr__(self):
        """For debugging -- returns a str representation of this node."""
        return "Node %s" % (self.id_string)

class NodeGroup(Node):
    """A group of nodes, accessible via the .nodes attribute.

       Note that node groups here are used to create "clusters" in GraphViz,
       in which a cluster is composed of >= 1 child nodes.

       (This is similar to Cytoscape.js' concept of a "compound node," for
       reference -- with the distinction that in Cytoscape.js a compound
       node is an actual "node," while in GraphViz a cluster is merely a
       "subgraph.")
    """
    
    plural_name = "other_structural_patterns"
    type_name = "Other"

    def __init__(self, group_prefix, nodes, unique_id=None):
        """Initializes the node group, given all the Node objects comprising
           the node group, a prefix character for the group (i.e. 'F' for
           frayed ropes, 'B' for bubbles, 'C' for chains, 'Y' for cycles),
           and a GraphViz style setting for the group (generally
           from config.py).

           Note that we use two IDs for Node Groups: one with '-'s replaced
           with 'c's (since GraphViz only allows '-' in IDs when it's the
           first character and the other ID characters are numbers), and one
           with the original ID names. The 'c' version is passed into GraphViz,
           and the '-' version is passed into the .db file to be used in
           Cytoscape.js.

           Also, if this NodeGroup has some unique ID, then you can
           pass that here via the unique_id argument. This makes the
           NodeGroup ID's just the group_prefix + the unique_id, instead
           of a combination of all of the node names contained within this
           NodeGroup (this approach is useful for NodeGroups of NodeGroups,
           e.g. Bicomponents).
        """
        self.node_count = 0
        self.edge_count = 0
        self.bp = 0
        self.gv_id_string = "%s" % (group_prefix)
        self.cy_id_string = "%s" % (group_prefix)
        self.nodes = []
        self.edges = []
        # dict that maps node id_strings to the corresponding Node objects
        self.childid2obj = {}
        for n in nodes:
            self.node_count += 1
            self.bp += n.bp
            if unique_id == None:
                self.gv_id_string += "%s_" % (n.id_string.replace('-', 'c'))
                self.cy_id_string += "%s_" % (n.id_string)
            self.nodes.append(n)
            n.used_in_collapsing = True
            n.group = self
            self.childid2obj[n.id_string] = n
        if unique_id == None:
            self.gv_id_string = self.gv_id_string[:-1] # remove last underscore
            self.cy_id_string = self.cy_id_string[:-1] # remove last underscore
        self.xdot_c_width = 0
        self.xdot_c_height = 0
        self.xdot_left = None
        self.xdot_bottom = None
        self.xdot_right = None
        self.xdot_top = None
        if unique_id != None:
            self.gv_id_string += unique_id
            self.cy_id_string = self.gv_id_string
        super(NodeGroup, self).__init__(self.gv_id_string, self.bp, False)

    def layout_isolated(self):
        """Lays out this node group by itself. Stores layout information in
           the attributes of both this NodeGroup object and its child
           nodes/edges.
        """
        # pipe .gv into pygraphviz to lay out this node group
        gv_input = ""
        gv_input += "digraph nodegroup {\n"
        if config.GRAPH_STYLE != "":
            gv_input += "\t%s;\n" % (config.GRAPH_STYLE)
        if config.GLOBALNODE_STYLE != "":
            gv_input += "\tnode [%s];\n" % (config.GLOBALNODE_STYLE)
        if config.GLOBALEDGE_STYLE != "":
            gv_input += "\tedge [%s];\n" % (config.GLOBALEDGE_STYLE)
        gv_input += self.node_info(backfill=False)
        for n in self.nodes:
            # Ensure that only the edges that point to nodes that are within
            # the node group are present; ensures layout is restricted to just
            # the node group in question.
            # This works because the edges we consider in the first place all
            # originate from nodes within the node group, so we don't have to
            # worry about edges originating from nodes outside the node group.
            gv_input += n.edge_info(constrained_nodes=self.nodes)
        gv_input += "}"
        cg = pygraphviz.AGraph(gv_input)
        cg.layout(prog='dot')
        # Obtain cluster width and height from the layout
        bounding_box_text = cg.subgraphs()[0].graph_attr[u'bb']
        bounding_box_numeric = [float(y) for y in bounding_box_text.split(',')]
        self.xdot_c_width = bounding_box_numeric[2] - bounding_box_numeric[0]
        self.xdot_c_height = bounding_box_numeric[3] - bounding_box_numeric[1]
        # convert width and height from points to inches
        self.xdot_c_width /= config.POINTS_PER_INCH
        self.xdot_c_height /= config.POINTS_PER_INCH
        # Obtain node layout info
        # NOTE: we could iterate over the subgraph's nodes or over the entire
        # graph (cg)'s nodes -- same result, since the only nodes in the graph
        # are in the subgraph.
        for n in cg.nodes():
            curr_node = self.childid2obj[str(n)]
            # Record the relative position (within the node group's bounding
            # box) of this child node.
            ep = n.attr[u'pos'].split(',')
            curr_node.xdot_rel_x = float(ep[0]) - bounding_box_numeric[0]
            curr_node.xdot_rel_y = float(ep[1]) - bounding_box_numeric[1]
            curr_node.xdot_shape = str(n.attr[u'shape'])
        # Obtain edge layout info
        for e in cg.edges():
            self.edge_count += 1
            source_node = self.childid2obj[str(e[0])]
            curr_edge = source_node.outgoing_edge_objects[str(e[1])]
            self.edges.append(curr_edge)
            # Get control points, then find them relative to cluster dimensions
            ctrl_pt_str, coord_list, curr_edge.xdot_ctrl_pt_count = \
                Edge.get_control_points(e.attr[u'pos'])
            curr_edge.xdot_rel_ctrl_pt_str = ""
            p = 0
            while p <= len(coord_list) - 2:
                if p > 0:
                    curr_edge.xdot_rel_ctrl_pt_str += " "
                x_coord = coord_list[p] - bounding_box_numeric[0]
                y_coord = coord_list[p + 1] - bounding_box_numeric[1]
                curr_edge.xdot_rel_ctrl_pt_str += str(x_coord)
                curr_edge.xdot_rel_ctrl_pt_str += " "
                curr_edge.xdot_rel_ctrl_pt_str += str(y_coord)
                p += 2
            curr_edge.group = self

    def node_info(self, backfill=True, incl_cluster_prefix=True):
        """Returns a string of the node_info() of this NodeGroup.
        
           If backfill is False, this works as normal: this node group is
           treated as a subgraph cluster, and all its child information is
           returned.
           
           If backfill is True, however, this node group is just treated
           as a rectangular normal node. Furthermore, the resulting node
           "definition" line will be prefixed with "cluster_" if
           incl_cluster_prefix is True. (The value of incl_cluster_prefix is
           only utilized if backfill is True.)
        """
        if backfill:
            output = "\t"
            if incl_cluster_prefix:
                output += "cluster_"
            output += "%s [height=%g,width=%g,shape=rectangle];\n" % \
                (self.gv_id_string, self.xdot_c_height, self.xdot_c_width)
            return output
        else:
            info = "subgraph cluster_%s {\n" % (self.gv_id_string)
            if config.GLOBALCLUSTER_STYLE != "":
                info += "\t%s;\n" % (config.GLOBALCLUSTER_STYLE)
            for n in self.nodes:
                info += n.node_info()
            info += "}\n"
            return info

    def db_values(self):
        """Returns a tuple containing the values associated with this group.
           Should be called after parsing and assigning .xdot bounding box
           values accordingly.
        """
        return (self.cy_id_string, self.bp, self.component_size_rank,
                self.xdot_left, self.xdot_bottom, self.xdot_right,
                self.xdot_top, self.type_name)

class Bubble(NodeGroup):
    """A group of nodes collapsed into a Bubble.
    
       Simple bubbles that MetagenomeScope automatically identifies (and
       validates using the is_valid_bubble() method of this class) consist
       of one node which points to >= 2 "middle" nodes, all of which in turn
       have linear paths that point to one "end" node.

       More complex bubbles (for example, those identified by MetaCarvel)
       can be specified by the user.

       (In any case, this Bubble class is agnostic as to the structure of its
       nodes; all that's needed to create a Bubble is a list of its nodes.)
    """

    plural_name = "bubbles"
    type_name = "Bubble"

    def __init__(self, *nodes):
        """Initializes the Bubble, given a list of nodes comprising it."""

        super(Bubble, self).__init__('B', nodes)

    @staticmethod
    def is_valid_bubble(s):
        """Returns a 2-tuple of True and a list of the nodes comprising the
           Bubble if a Bubble defined with the given start node is valid.
           Returns a 2-tuple of (False, None) if such a Bubble would be
           invalid.
           
           NOTE that this assumes that s has > 1 outgoing edges.
        """
        if s.used_in_collapsing: return False, None
        # Get a list of the first node on each divergent path through this
        # (potential) bubble
        m1_nodes = s.outgoing_nodes
        # The bubble's ending node will be recorded here
        e_node = None
        # We keep a list of chains to mark as "subsumed" (there's a max
        # of p chains that will be in this list, where p = the number of
        # divergent paths through this bubble)
        chains_to_subsume = []
        # Traverse through the bubble's divergent paths, checking for
        # validity and recording nodes
        # List of all middle nodes (divergent paths) in the bubble
        m_nodes = []
        # List of all nodes that are the "end" of divergent paths in the bubble
        mn_nodes = []
        for n in m1_nodes:
            if len(n.incoming_nodes) != 1 or len(n.outgoing_nodes) != 1:
                return False, None
            # Now we know that this path is at least somewhat valid, get
            # all the middle nodes on it and the ending node from it.
            chain_validity, path_nodes = Chain.is_valid_chain(n)
            if not chain_validity:
                # We could have already grouped the middle nodes of this rope
                # into a chain, which would be perfectly valid
                # (Chain.is_valid_chain() rejects Chains composed of nodes that
                # have already been used in collapsing)
                if n.used_in_collapsing:
                    if type(n.group) == Chain:
                        path_nodes = n.group.nodes
                        path_end = path_nodes[len(path_nodes)-1].outgoing_nodes
                        # The divergent paths of a bubble must converge
                        if len(path_end) != 1:
                            return False, None
                        if e_node == None:
                            e_node = path_end[0]
                        # If the divergent paths of a bubble don't converge to
                        # the same ending node, then it isn't a bubble
                        elif e_node != path_end[0]:
                            return False, None
                        m_nodes += path_nodes
                        mn_nodes.append(path_nodes[len(path_nodes) - 1])
                        chains_to_subsume.append(n.group)
                    else:
                        # if this path has been grouped into a pattern that 
                        # isn't a chain, don't identify this as a bubble
                        return False, None
                # Or we just have a single middle node (assumed if no middle
                # chain exists/could exist)
                else:
                    # Like above, record or check ending node
                    if e_node == None:
                        e_node = n.outgoing_nodes[0]
                    elif e_node != n.outgoing_nodes[0]:
                        return False, None
                    # And if that worked out, then record this path
                    m_nodes.append(n)
                    mn_nodes.append(n)
            else:
                # The middle nodes form a chain that has not been "created" yet
                # This makes this a little easier for us.
                path_end = path_nodes[len(path_nodes) - 1].outgoing_nodes
                if len(path_end) != 1:
                    return False, None
                if e_node == None:
                    e_node = path_end[0]
                elif e_node != path_end[0]:
                    return False, None
                m_nodes += path_nodes
                mn_nodes.append(path_nodes[len(path_nodes) - 1])
            # Now we have the middle and end nodes of the graph stored.

        # Check ending node
        if e_node.used_in_collapsing:
            return False, None
        # If the ending node has any incoming nodes that are not in
        # mn_nodes, then reject this bubble.
        elif set(e_node.incoming_nodes) != set(mn_nodes):
            return False, None
        # If the bubble is cyclical, reject it
        # (checking the outgoing/incoming nodes of m1_nodes, and only
        # allowing chains or singleton paths in m_nodes, means we should
        # never have an outgoing node from e to anything in m_nodes by this
        # point
        elif s in e_node.outgoing_nodes:
            return False, None
        
        # Check entire bubble structure, to ensure all nodes are distinct
        composite = [s] + m_nodes + [e_node]
        if len(set(composite)) != len(composite):
            return False, None

        # If we've gotten here, then we know that this is a valid bubble.
        for ch in chains_to_subsume:
            ch.is_subsumed = True
        return True, composite

class MiscPattern(NodeGroup):
    """A group of nodes identified by the user as a pattern.

       Basically, this is handled the same as the other structural pattern
       classes (Bubble, Rope, Chain, Cycle) with the slight exceptions that
       1) no validation is imposed on the pattern structure (aside from
       checking that node IDs are valid) and 2) the "type name" of this
       class can be any string, and is defined in the input file alongside
       the pattern structure."""

    plural_name = "misc_patterns"

    def __init__(self, type_name="Misc", *nodes):
        """Initializes the Pattern, given a list of nodes comprising it."""
        self.type_name = type_name
        super(MiscPattern, self).__init__('M', nodes)

class Rope(NodeGroup):
    """A group of nodes collapsed into a Rope."""

    plural_name = "frayed_ropes"
    type_name = "Frayed Rope"

    def __init__(self, *nodes):
        """Initializes the Rope, given a list of nodes comprising it."""
        super(Rope, self).__init__('F', nodes)
     
    @staticmethod
    def is_valid_rope(s):
        """Returns a 2-tuple of (True, a list of all the nodes in the Rope)
           if a Rope defined with the given start node would be a valid
           Rope. Returns a 2-tuple of (False, None) if such a Rope would be
           invalid.
           
           Assumes s has only 1 outgoing node.
        """
        # Detect the first middle node in the rope
        m1 = s.outgoing_nodes[0]
        # Get all start nodes
        s_nodes = m1.incoming_nodes
        # A frayed rope must have multiple paths from which to converge to
        # the "middle node" section
        if len(s_nodes) < 2: return False, None
        # Ensure none of the start nodes have extraneous outgoing nodes
        # (or have been used_in_collapsing)
        for n in s_nodes:
            if len(n.outgoing_nodes) != 1 or n.used_in_collapsing:
                return False, None
        # Now we know that, regardless of the middle nodes' composition,
        # no chain can exist involving m1 that does not start AT m1.
        # Also we know the start nodes are mostly valid (still need to check
        # that each node in the rope is distinct, but that is done later
        # on after we've identified all middle and end nodes).

        # Check the middle nodes

        # Determine if the middle path of the rope is (or could be) a Chain
        chain_to_subsume = None
        chain_validity, m_nodes = Chain.is_valid_chain(m1)
        if not chain_validity:
            # We could have already grouped the middle nodes of this rope
            # into a chain, which would be perfectly valid
            # (Chain.is_valid_chain() rejects Chains composed of nodes that
            # have already been used in collapsing)
            if m1.used_in_collapsing:
                if type(m1.group) == Chain:
                    m_nodes = m1.group.nodes
                    e_nodes = m_nodes[len(m_nodes) - 1].outgoing_nodes
                    chain_to_subsume = m1.group
                else:
                    # if m1 has been grouped into a pattern that isn't a
                    # chain, don't identify this as a frayed rope
                    return False, None
            # Or we just have a single middle node (assumed if no middle
            # chain exists/could exist)
            else:
                m_nodes = [m1]
                e_nodes = m1.outgoing_nodes
        else:
            # The middle nodes form a chain that has not been "created" yet.
            # This makes this a little easier for us.
            e_nodes = m_nodes[len(m_nodes) - 1].outgoing_nodes
        # Now we have the middle and end nodes of the graph stored.

        # Check ending nodes
        # The frayed rope's converged middle path has to diverge to
        # something for it to be a frayed rope
        if len(e_nodes) < 2: return False, None
        for n in e_nodes:
            # Check for extraneous incoming edges, and that the ending nodes
            # haven't been used_in_collapsing.
            if len(n.incoming_nodes) != 1 or n.used_in_collapsing:
                return False, None
            for o in n.outgoing_nodes:
                # We know now that all of the m_nodes (sans m1) and all of the
                # e_nodes only have one incoming node, but we don't know
                # that about the s_nodes. Make sure that this frayed rope
                # isn't cyclical.
                if o in s_nodes:
                    return False, None

        # Check the entire frayed rope's structure
        composite = s_nodes + m_nodes + e_nodes
        # Verify all nodes in the frayed rope are distinct
        if len(set(composite)) != len(composite):
            return False, None

        # If we've made it here, this frayed rope is valid!
        if chain_to_subsume != None:
            chain_to_subsume.is_subsumed = True
        return True, composite

class Chain(NodeGroup):
    """A group of nodes collapsed into a Chain. This is defined as > 1
       nodes that occur one after the other, with no intermediate edges.
    """

    plural_name = "chains"
    type_name = "Chain"

    def __init__(self, *nodes):
        """Initializes the Chain, given all the nodes comprising the chain."""
        super(Chain, self).__init__('C', nodes)

    @staticmethod
    def is_valid_chain(s):
        """Returns a 2-tuple of (True, a list of all the nodes in the Chain
           in order from start to end) if a Chain defined at the given start
           node would be valid. Returns a 2-tuple of (False, None) if such a
           Chain would be considered invalid.
           
           Note that this finds the longest possible Chain that includes s,
           if a Chain exists starting at s. If we decide that no Chain
           exists starting at s then we just return (False, None), but if we
           find that a Chain does exist starting at s then we traverse
           "backwards" to find the longest possible chain including s.
        """
        if len(s.outgoing_nodes) != 1:
            return False, None
        # Determine the composition of the Chain (if one exists starting at s)
        # First, check to make sure we have the minimal parts of a Chain:
        # a starting node with one outgoing edge to another node, and the other
        # node only has one incoming edge (from the starting node). The other
        # node also cannot have an outgoing edge to the starting node.
        if s.outgoing_nodes[0] == s or type(s.outgoing_nodes[0]) != Node:
            return False, None
        chain_list = [s]
        curr = s.outgoing_nodes[0]
        chain_ends_cyclically = False
        # We iterate "down" through the chain.
        while True:
            if (len(curr.incoming_nodes) != 1 or type(curr) != Node
                                            or curr.used_in_collapsing):
                # The chain has ended, and this can't be the last node in it
                # (The node before this node, if applicable, is the chain's
                # actual end.)
                break
            
            if len(curr.outgoing_nodes) != 1:
                # Like above, this means the end of the chain...
                # NOTE that at this point, if curr has an outgoing edge to a
                # node in the chain list, it has to be to the starting node.
                # This is because we've already checked every other node in
                # the chain list to ensure that every non-starting node has
                # only 1 incoming node.
                if len(curr.outgoing_nodes) > 1 and s in curr.outgoing_nodes:
                    chain_ends_cyclically = True
                else:
                    # ...But this is still a valid end-node in the chain.
                    chain_list.append(curr)
                # Either way, we break -- we're done traversing the chain
                # forwards.
                break

            # See above NOTE re: cyclic outgoing edges. This is basically
            # the same thing.
            if curr.outgoing_nodes[0] == s:
                chain_ends_cyclically = True
                break

            # If we're here, the chain is still going on!
            chain_list.append(curr)
            curr = curr.outgoing_nodes[0]

        # Alright, done iterating down the chain.
        if len(chain_list) <= 1 or chain_ends_cyclically:
            # There wasn't a Chain starting at s. (There might be a Chain
            # that includes s that starts "before" s, but we don't really
            # bother with that now -- we only care about optimality when
            # reporting that a Chain exists. We would find such a Chain later,
            # anyway.)
            # Also, re chain_ends_cyclically:
            # We'll detect a cycle here when we're actually looking for
            # cycles -- so don't count this as a chain.
            return False, None

        if len(s.incoming_nodes) != 1:
            # s was already the optimal starting node, so just return what we
            # have currently
            return True, chain_list

        # If we're here, we know a Chain exists starting at s. Can it be
        # extended in the opposite direction to start at a node "before" s?
        # We run basically what we did above, but in reverse.
        backwards_chain_list = []
        curr = s.incoming_nodes[0]
        while True:
            if (len(curr.outgoing_nodes) != 1 or type(curr) != Node
                                            or curr.used_in_collapsing):
                # The node "before" this node is the optimal starting node.
                # This node can't be a part of the chain.
                break
            if len(curr.incoming_nodes) != 1:
                # This indicates the end of the chain, and this is the optimal
                # starting node in the chain.
                if len(set(curr.incoming_nodes) & set(chain_list)) > 0:
                    # Chain "begins" cyclically, so we'll tag it as a cycle
                    # when detecting cycles
                    return False, None
                backwards_chain_list.append(curr)
                break
            # The backwards chain continues. Fortunately, if the chain had
            # invalid references (e.g. last node has an outgoing edge to the
            # prior start node or something), those should have been caught
            # in the forwards chain-checking, so we don't need to check for
            # that corner case here.
            backwards_chain_list.append(curr)
            curr = curr.incoming_nodes[0]
        if backwards_chain_list == []:
            # There wasn't a more optimal starting node -- this is due to the
            # node "before" s either not being a Node, or having > 1 outgoing
            # edges.
            return True, chain_list
        # If we're here, we found a more optimal starting node
        backwards_chain_list.reverse()
        return True, backwards_chain_list + chain_list

class Cycle(NodeGroup):
    """A group of nodes collapsed into a Cycle. This is defined as > 1
       nodes that occur one after another with no intermediate edges, where
       the sequence of nodes repeats.
       
       (Less formally, this is essentially a Chain where the 'last' node has
       one outgoing edge to the 'first' node.)
    """

    plural_name = "cyclic_chains"
    type_name = "Cyclic Chain"

    def __init__(self, *nodes):
        """Initializes the Cycle, given all the nodes comprising it."""
        super(Cycle, self).__init__('Y', nodes)

    @staticmethod
    def is_valid_cycle(s):
        """Identifies the simple cycle that "starts at" a given starting
           node, if such a cycle exists. Returns (True, [nodes]) if
           such a cycle exists (where [nodes] is a list of all the nodes in
           the cycle), and (False, None) otherwise.
           
           NOTE that this only identifies cycles without any intermediate
           incoming/outgoing edges not in the simple cycle -- that is, this
           basically just looks for chains that end cyclically. (This also
           identifies single-node loops as cycles.)
           
           The ideal way to implement cycle detection in a graph is to use
           Depth-First Search (so, in our case, it would be to modify the
           code in collate.py that already runs DFS to identify cycles), but
           for now I think this more limited-in-scope method should work ok.
        """
        s_outgoing_node_ct = len(s.outgoing_nodes)
        if len(s.incoming_nodes) == 0 or s_outgoing_node_ct == 0:
            # If s has no incoming or no outgoing nodes, it can't be in
            # a cycle!
            return False, None
        # Edge case: we identify single nodes with loops to themselves.
        # If the start node has multiple outgoing edges but no reference to
        # itself, then it isn't the start node for a cycle. (It could very
        # well be the end node of another cycle, but we would eventually
        # test that node for being a cycle later on.)
        if s in s.outgoing_nodes:
            # Valid whether s has 1 or >= 1 outgoing edges
            return True, [s]
        elif s_outgoing_node_ct > 1:
            # Although we allow singleton looped nodes to be cycles (and to
            # have > 1 outgoing nodes), we don't allow larger cycles to be
            # constructed from a start node with > 1 outgoing nodes (since
            # these are chain-like cycles, as discussed above).
            return False, None
        # We iterate "down" through the cycle to determine its composition
        cycle_list = [s]
        curr = s.outgoing_nodes[0]
        while True:
            if (len(curr.incoming_nodes) != 1 or type(curr) != Node
                                            or curr.used_in_collapsing):
                # The cycle has ended, and this can't be the last node in it
                # (The node before this node, if applicable, is the cycle's
                # actual end.)
                return False, None
            
            if len(curr.outgoing_nodes) != 1:
                # Like above, this means the end of the cycle, but it can
                # mean the cycle is valid.
                # NOTE that at this point, if curr has an outgoing edge to a
                # node in the cycle list, it has to be to the starting node.
                # This is because we've already checked every other node in
                # the cycle list to ensure that every non-starting node has
                # only 1 incoming node.
                if len(curr.outgoing_nodes) > 1 and s in curr.outgoing_nodes:
                    return True, cycle_list + [curr]
                else:
                    # If we didn't loop back to start at the end of the
                    # cycle, we never will for this particular cycle. So
                    # just return False.
                    return False, None

            # We know curr has one incoming and one outgoing edge. If its
            # outgoing edge is to s, then we've found a cycle.
            if curr.outgoing_nodes[0] == s:
                return True, cycle_list + [curr]

            # If we're here, the cycle is still going on -- the next node to
            # check is not already in the cycle_list.
            cycle_list.append(curr)
            curr = curr.outgoing_nodes[0]

        # If we're here then something went terribly wrong

class Component(object):
    """A connected component in the graph. We use this in order to
       maintain meta-information, such as node groups, for each connected
       component we're interested in.
    """
    def __init__(self, node_list, node_group_list):
        """Given a list of all nodes (i.e. not node groups) and a list of
           all node groups in the connected component, intializes the
           connected component.
        """
        self.node_list = node_list
        self.node_group_list = node_group_list 

    def node_and_edge_info(self):
        """Returns the node and edge info for this connected component
           as a 2-string tuple, where the first string is node info and the
           second string is edge info (and both strings are DOT-compatible).
        """

        node_info = ""
        edge_info = ""
        # Get node info from groups (contains info about the group's child
        # nodes as well)
        for g in self.node_group_list:
            node_info += g.node_info()

        # Get node info from "standalone nodes" (not in node groups)
        # Simultaneously, we get edge info from all nodes, standalone or not
        # (GraphViz will reconcile this edge information with the node group
        # declarations to specify where edges should be in the xdot file)
        for n in self.node_list:
            if not n.used_in_collapsing:
                node_info += n.node_info()
            edge_info += n.collapsed_edge_info()

        return node_info, edge_info

    def __repr__(self):
        """Returns a (somewhat verbose) string representation of this
           component.
        """
        return "Component of " + str(self.node_list) + \
                "; " + str(self.node_group_list)

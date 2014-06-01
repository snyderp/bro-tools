"""Classes and functions useful for parsing and representing collections
of BroRecords as a DAG, with each node's successor being the page that
lead to a given page, and its children being the pages visted next."""

import networkx as nx
from .records import bro_records
from .chains import BroRecordChain


def graphs(handle, time=.5, record_filter=None):
    """A generator function yields BroRecordGraph objects that represent
    pages visited in a browsing session.

    Args:
        handle -- a file handle like object to read lines of bro data off of.

    Keyword Args:
        time          -- the maximum amount of time that can have passed in
                         a browsing session before the graph is closed and
                         yielded
        record_filter -- an optional function that, if provided, should take two
                         arguments of bro records, and should provide True if
                         they should be included in the same chain or not.  Note
                         that this is in addition to the filtering / matching
                         already performed by the BroRecordChain.add_record
                         function

    Return:
        An iterator returns BroRecordGraph objects
    """
    _graphs = []
    for r in bro_records(handle, record_filter=record_filter):
        found_graph_for_record = False
        for g in _graphs:

            # First make sure that our graphs are not too old.  If they
            # are, yield them and then remove them from our considered
            # set
            if (r.ts - g.latest_ts) > time:
                yield g
                _graphs.remove(g)
                continue

            # If the current graph is not too old to represent a valid
            # browsing session then, see if it is valid for the given
            # bro record.  If so, then we don't need to consider any other
            # graphs on this iteration
            if g.add_node(r):
                found_graph_for_record = True
                break

        # Last, if we haven't found a graph to add the current record to,
        # create a new graph and add the record to it
        if not found_graph_for_record:
            _graphs.append(BroRecordGraph(r))

    # Last, if we've considered every record in the collection, we need to
    # yield the remaining graphs to the caller, to make sure they see
    # ever relevant record
    for g in _graphs:
        yield g


class BroRecordGraph(object):

    def __init__(self, br):
        self._g = nx.DiGraph()
        self.ip = br.id_orig_h

        # The root element of the graph can either be the referrer of the given
        # bro record, if it exists, or otherwise the record itself.
        self._g.add_node(br)
        self._root = br

        # Keep track of
        self.latest_ts = br.ts

        # Since we expect that we'll see nodes in a sorted order (ie
        # each examined node will be the lastest-one-seen-yet)
        # we can make date comparisons of nodes faster by
        # keeping a seperate set of references to them, from earliest to
        # latest
        self._nodes_sorted = [br]

    def __len__(self):
        return len(self._nodes_sorted)

    def referrer_record(self, br):
        """Returns the BroRecord that could be the referrer of the given
        record, if one exists, and otherwise returns None.  If there
        are multiple BroRecords in this graph that could be the referrer of
        the given record, the most recent candidate is returned.

        Args:
            br -- a BroRecord object

        Returns:
            The most recent candidate BroRecord that could be the referrer of
            the passed BroRecord, or None if there are no possible matches.
        """
        # We can special case situations where the IP addresses don't match,
        # in order to save ourselves having to walk the entire line of nodes
        # again in a clear miss situation
        if br.id_orig_h != self.ip:
            return None

        for n in self._nodes_sorted[::-1]:
            if n.is_referrer_of(br):
                return n
        return None

    def add_node(self, br):
        """Attempts to add the given BroRecord as a child (successor) of its
        referrer in the graph.

        Args:
            br -- a BroRecord object

        Returns:
            True if a referrer of the the BroRecord could be found and the given
            record was added as its child / successor.  Otherwise, False is
            returned, indicating no changes were made."""
        referrer_node = self.referrer_record(br)
        if not referrer_node:
            return False

        time_difference = br.ts - referrer_node.ts
        self._g.add_weighted_edges_from([(referrer_node, br, time_difference)])
        self.latest_ts = br.ts
        self._nodes_sorted.append(br)

        return True

    def nodes(self):
        """Returns an array of BroRecords, from oldest to newest, that are in
        the graph.

        Return:
            A list of zero or more BroRecords
        """
        return self._nodes_sorted

    def graph(self):
        """Returns the underlying graph representation for the BroRecords

        Returns:
            The underlying graph representation, a networkx.DiGraph object
        """
        return self._g

    def chain_from_node(self, br):
        """Returns a BroRecordChain object, describing the chain of requests
        that lead to the given BroRecord.

        Args:
            br -- a BroRecord

        Return:
            None if the given BroRecord is not in the give BroRecordGraph,
            otherwise a BroRecordChain object describing how the record br
            was arrived at from the root of the graph / DAG.
        """
        g = self._g
        if not g.has_node(br):
            return None

        path = [br]
        node = br
        while True:
            parents = g.predecessors(node)
            if not len(parents):
                break
            node = parents[0]
            path.append(node)

        chain = BroRecordChain(path[-1])
        for r in path[1::-1]:
            chain.add_record(r)
        return chain
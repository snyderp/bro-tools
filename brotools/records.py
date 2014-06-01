def _strip_protocol(url):
    if url[0:7] == "http://":
        url = url[7:]
    elif url[0:8] == "https://":
        url = url[8:]
    return url

def bro_records(handle, record_filter=None):
    """A generator function for iterating over a a collection of bro records.
    The iterator returns BroRecord objects (named tuples) for each record
    in the given file

    Args:
        handle -- a file handle like object to read lines of bro data off of.

    Keyword Args:
        record_filter -- an optional function that, if provided, should take two
                         arguments of bro records, and should provide True if
                         they should be included in the same chain or not.  Note
                         that this is in addition to the filtering / matching
                         already performed by the BroRecordChain.add_record
                         function

    Return:
        An iterator returning BroRecord objects
    """
    seperator = None
    num_lines = 0
    for raw_row in handle:
        num_lines += 1
        row = raw_row[:-1] # Strip off line end
        if not seperator and row[0:10] == "#separator":
            seperator = row[11:].decode('unicode_escape')
        elif row[0] != "#":
            try:
                r = BroRecord(row, seperator)
            except Exception, e:
                print "Bad line entry"
                print "File: {0}".format(handle.name)
                print "Values: {0}".format(row.split(seperator))
                raise e

            # if record_filter and not record_filter(r):
            #     continue
            yield r


class BroRecord(object):

    def __init__(self, line, seperator="\t"):
        values = [a if a != "-" else "" for a in line.split(seperator)]
        self.ts = float(values[0])
        self.id_orig_h = values[1]
        self.id_resp_h = values[2]
        self.method = values[3]
        self.host = values[4]
        self.uri = values[5]
        self.referrer = _strip_protocol(values[6])
        self.user_agent = values[7]
        self.status_code = values[8]
        self.content_type = values[9]
        self.location = values[10]
        try:
            self.cookies = values[11]
        except IndexError:
            self.cookies = None
        self.line = line

    def __str__(self):
        return self.line

    def url(self):
        return u"{host}{uri}".format(host=self.host, uri=self.uri)

    def is_referrer_of(self, r):
        """Returns a boolean response of whether it looks like the current
        BroRecord object is the referrer of the passed BroRecord.  This
        check is True if 1) the IPs match, 2) the requested url of the current
        object is equal to the referrer of the given object, and 3) if the
        passed BroRecord has a timestamp later than the current object.

        Args:
            r -- A BroRecord

        Return:
            True if it looks like the current object could be the referrer
            of the passed object, and otherwise False.
        """
        if r.id_orig_h != self.id_orig_h:
            return False

        if self.url() != r.referrer:
            return False

        if r.ts <= self.ts:
            return False

        return True

class BroRecordWindow(object):
    """Keep track of a sliding window of BroRecord objects, and don't keep more
    than a given amount (defined by a time range) in memory at a time"""

    def __init__(self, time=.5):
        # A collection of BroRecords that all occurred less than the given
        # amount of time before the most recent one (in order oldest to newest)
        self._collection = []

        # Window size of bro records to keep in memory
        self._time = time

    def size(self):
        return len(self._collection)

    def prune(self):
        """Remove all BroRecords that occured more than self.time before the
        most recent BroRecord in the collection.

        Return:
            An int count of the number of objects removed from the collection
        """

        # Simple case that if we have no stored BroRecords, there can't be
        # any to remove
        if len(self._collection) == 0:
            return 0

        removed_count = 0
        most_recent_time = self._collection[-1].ts
        window_low_bound = self._time

        while len(self._collection) > 1 and self._collection[0].ts + window_low_bound < most_recent_time:
            self._collection = self._collection[1:]
            removed_count += 1

        return removed_count

    def append(self, record):
        """Adds a BroRecord to the current collection of bro records, and then
        cleans to watched collection to remove old records (records before the)
        the sliding time window.

        Args:
            record -- A BroRecord, created by the bro_records function

        Return:
            The number of records that were removed from the window during garbage collection.
        """
        self._collection.append(record)

        # Most of the time the given record will be later than the last
        # record added (since we keep the collection sorted).  In this common
        # case, just add the new record to the end of the collection.
        # Otherwise, add the record and sort the whole thing
        self._collection.append(record)
        if record.ts > self._collection[-2].ts:
            self._collection.sort(key=lambda x: x.ts)

        return self.prune()
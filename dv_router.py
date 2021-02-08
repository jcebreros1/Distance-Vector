"""
Your awesome Distance Vector router for CS 168

Based on skeleton code by:
  MurphyMc, zhangwen0411, lab352
"""

import sim.api as api
from cs168.dv import RoutePacket, \
                     Table, TableEntry, \
                     DVRouterBase, Ports, \
                     FOREVER, INFINITY

class DVRouter(DVRouterBase):

    # A route should time out after this interval
    ROUTE_TTL = 15

    # Dead entries should time out after this interval
    GARBAGE_TTL = 10

    # -----------------------------------------------
    # At most one of these should ever be on at once
    SPLIT_HORIZON = False
    POISON_REVERSE = False
    # -----------------------------------------------
    
    # Determines if you send poison for expired routes
    POISON_EXPIRED = False

    # Determines if you send updates when a link comes up
    SEND_ON_LINK_UP = False

    # Determines if you send poison when a link goes down
    POISON_ON_LINK_DOWN = False

    def __init__(self):
        """
        Called when the instance is initialized.
        DO NOT remove any existing code from this method.
        However, feel free to add to it for memory purposes in the final stage!
        """
        assert not (self.SPLIT_HORIZON and self.POISON_REVERSE), \
                    "Split horizon and poison reverse can't both be on"
        
        self.start_timer()  # Starts signaling the timer at correct rate.

        # Contains all current ports and their latencies.
        # See the write-up for documentation.
        self.ports = Ports()
        
        # This is the table that contains all current routes
        self.table = Table()
        self.table.owner = self
        self.history = {}

    def add_static_route(self, host, port):
        """
        Adds a static route to this router's table.

        Called automatically by the framework whenever a host is connected
        to this router.

        :param host: the host.
        :param port: the port that the host is attached to.
        :returns: nothing.
        """
        # `port` should have been added to `peer_tables` by `handle_link_up`
        # when the link came up.
        assert port in self.ports.get_all_ports(), "Link should be up, but is not."

        # TODO: fill this in!
        self.table[host] = TableEntry(host, port, self.ports.get_latency(port), FOREVER)

    def handle_data_packet(self, packet, in_port):
        """
        Called when a data packet arrives at this router.

        You may want to forward the packet, drop the packet, etc. here.

        :param packet: the packet that arrived.
        :param in_port: the port from which the packet arrived.
        :return: nothing.
        """
        # TODO: fill this in!
        for host, entry in self.table.items(): # iterate through my table 
            if packet.dst in entry:
                if entry.latency < INFINITY:
                    self.send(packet, entry.port, False)

    """
    Helper functions that will decide what to advertise. It will either not advertise or advertise a latency of infinity.
    If the algorithm decides to advertise, the sendAd will send the advertisement
    """
    def skipOrSend(self, advertisedPort, currPort, sh, pr):
        if sh is True and pr is False:
            return self.SPLIT_HORIZON is True and currPort == advertisedPort
        else:
            return self.POISON_REVERSE is True and currPort == advertisedPort

    def isSame(self, force, entry, port, latency):
        return force is False and entry.dst in self.history and port in self.history[entry.dst] and self.history[entry.dst][port] == latency

    def sendAd(self, port, dst, latency):
        self.history.setdefault(dst, {})[port] = latency
        self.send_route(port, dst, latency)

    def send_routes(self, force=False, single_port=None):
        """
        Send route advertisements for all routes in the table.

        :param force: if True, advertises ALL routes in the table;
                      otherwise, advertises only those routes that have
                      changed since the last advertisement.
               single_port: if not None, sends updates only to that port; to
                            be used in conjunction with handle_link_up.
        :return: nothing.
        """
        # TODO: fill this in!
        if single_port is not None:
            for entry in self.table.values():
                latency = entry.latency
                self.sendAd(single_port, host, latency)
        else:
            for host, entry in self.table.items():
                for port in self.ports.get_all_ports():
                    latency = entry.latency
                    switcher = {
                        1: self.skipOrSend(port, entry.port, True, False),
                        2: self.skipOrSend(port, entry.port, False, True),
                        3: self.isSame(force, entry, port, latency)
                    }
                    splitHorizon = switcher.get(1, lambda: "Invalid Choice")
                    positionReverse = switcher.get(2, lambda: "Invalid Choice")
                    checkHistory = switcher.get(3, lambda: "Invalid Choice")
                    
                    if splitHorizon:
                            continue
                    if positionReverse:
                            latency = INFINITY
                    if self.isSame(force, entry, port, latency) or checkHistory:
                        continue
                    self.sendAd(port, host, latency)
        
    # Will delete the routes that I appended to toDelete
    def deleteRoutes(self, toDelete):
        for host in toDelete:
            del self.table[host]

    def expire_routes(self):
        """
        Clears out expired routes from table.
        accordingly.
        """
        # TODO: fill this in!
        toDelete = []
        if self.POISON_EXPIRED is True:
            for host, entry in self.table.items():
                if entry.has_expired:
                    self.table[host] = TableEntry(host, entry.port, INFINITY, api.current_time())
        else:
            for host, entry in self.table.items():
                if entry.has_expired:
                    toDelete.append(host)
            self.deleteRoutes(toDelete)
    def handle_route_advertisement(self, route_dst, route_latency, port):
        """
        Called when the router receives a route advertisement from a neighbor.

        :param route_dst: the destination of the advertised route.
        :param route_latency: latency from the neighbor to the destination.
        :param port: the port that the advertisement arrived on.
        :return: nothing.
        """
        # TODO: fill this in!
        # if its not in the table entry then I need to add it since it is a new destination
        if route_dst not in self.table.keys():
            self.table[route_dst] = TableEntry(route_dst, port, self.ports.get_latency(port) + route_latency, api.current_time() + self.ROUTE_TTL)
        else:
            for host, entry in self.table.items():
                if route_dst == host: # if my destination is in my table entry then maybe I have found a better path and must update my existing path
                    if port == entry.port and route_latency >= INFINITY:
                        self.table[host] = TableEntry(route_dst, port, INFINITY, api.current_time())
                        self.send_routes(False)
                    elif port == entry.port or entry.latency > route_latency + self.ports.get_latency(port):
                        self.table[host] = TableEntry(route_dst, port, route_latency + self.ports.get_latency(port), api.current_time() + self.ROUTE_TTL)
                        self.send_routes(False)

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this router goes up.

        :param port: the port that the link is attached to.
        :param latency: the link latency.
        :returns: nothing.
        """
        self.ports.add_port(port, latency)
        # TODO: fill in the rest!
        if self.SEND_ON_LINK_UP:
            self.send_routes(False, port);

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this router does down.

        :param port: the port number used by the link.
        :returns: nothing.
        """
        self.ports.remove_port(port)
        # TODO: fill this in!
        toDelete = []
        for host, entry in self.table.items():
            if entry.port == port:
                if self.POISON_ON_LINK_DOWN:
                    self.table[host] = TableEntry(host, port, INFINITY, api.current_time() + self.ROUTE_TTL)
                    self.send_routes(False);
                else:
                    toDelete.append(host)
        self.deleteRoutes(toDelete)

    # Feel free to add any helper methods!
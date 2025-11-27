from sys import exit
from logging import getLogger
from influxdb import InfluxDBClient
from requests.exceptions import ConnectionError
from influxdb.exceptions import InfluxDBServerError


class DBManager(object):
    """
    Patched DBManager for Varken *Telegraf passthrough mode*.

    When Varken is configured to write to Telegraf’s HTTP listener
    instead of a full InfluxDB server, the usual API calls for pinging
    the server, creating databases, or setting retention policies will
    fail.  This class skips those checks while preserving write_points().
    """

    def __init__(self, server):
        self.server = server
        self.logger = getLogger()

        # Basic sanity check for an unedited config file
        if self.server.url == "influxdb.domain.tld":
            self.logger.critical(
                "You have not configured your varken.ini. "
                "Please read the Wiki page for configuration."
            )
            exit(1)

        # Initialise the client so we can still use write_points().
        # Telegraf understands the /write endpoint and line protocol, even
        # though it doesn't expose the rest of the InfluxDB HTTP API.
        self.influx = InfluxDBClient(
            host=self.server.url,
            port=self.server.port,
            username=self.server.username,
            password=self.server.password,
            ssl=self.server.ssl,
            database="varken",     # Ignored by Telegraf, required by client
            verify_ssl=self.server.verify_ssl,
            timeout=10,
        )

        # -----  IMPORTANT  -------------------------------------------------
        # All connection / database management checks are intentionally
        # removed, because Telegraf will return 404 for them.
        # ------------------------------------------------------------------
        self.logger.info(
            "Telegraf passthrough mode enabled — skipping InfluxDB ping "
            "and database/retention‑policy setup."
        )

    def write_points(self, data):
        """
        Forward a list of JSON points to Telegraf.
        Transient errors are logged but not fatal to the main loop.
        """
        try:
            self.logger.debug("Writing data to Telegraf/InfluxDB: %s", data)
            self.influx.write_points(data)
        except (InfluxDBServerError, ConnectionError) as e:
            self.logger.error(
                "Error writing data to InfluxDB. Dropping this set of data. "
                "Check your database! Error: %s",
                e,
            )

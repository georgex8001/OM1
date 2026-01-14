import logging
import multiprocessing as mp
import threading
import time
from queue import Empty, Full
from typing import Dict, List, Optional, Union

import zenoh

from runtime.logging import LoggingConfig, get_logging_config, setup_logging
from zenoh_msgs import open_zenoh_session, sensor_msgs

from .singleton import singleton


def simple_paths_processor(
    data_queue: mp.Queue,
    control_queue: mp.Queue,
    logging_config: Optional[LoggingConfig] = None,
):
    """
    Process paths data from the Zenoh session.

    Parameters
    ----------
    data_queue : mp.Queue
        Queue for receiving paths data.
    control_queue : mp.Queue
        Queue for sending control commands.
    """
    setup_logging("simple_paths_processor", logging_config=logging_config)

    def paths_callback(msg: zenoh.Sample):
        """
        Callback for receiving paths messages.

        Parameters
        ----------
        msg: zenoh.Sample
            The message containing paths data.
        """
        paths = sensor_msgs.Paths.deserialize(msg.payload.to_bytes())
        msg_time = paths.header.stamp.sec + paths.header.stamp.nanosec * 1e-9
        current_time = time.time()
        latency = current_time - msg_time
        logging.debug(f"Received paths with latency: {latency:.6f} seconds")
        logging.info(f"Received paths: {paths.paths}")

        try:
            data_queue.put_nowait(paths)
        except Full:
            try:
                data_queue.get_nowait()
                data_queue.put_nowait(paths)
            except Empty:
                pass

    running = True

    try:
        session = open_zenoh_session()
        session.declare_subscriber("om/paths", paths_callback)
        logging.info("Zenoh is open for SimplePathsProvider")
    except Exception as e:
        logging.error(f"Failed to open Zenoh session: {e}")

    while running:
        try:
            cmd = control_queue.get_nowait()
            if cmd == "STOP":
                running = False
                break
        except Empty:
            pass

        time.sleep(0.1)


@singleton
class SimplePathsProvider:
    """
    Singleton class to provide simple path processing using Zenoh.

    This provider manages robot navigation path data by subscribing to Zenoh
    topics and processing path information to generate movement options.
    It uses a multiprocessing architecture with separate processes for data
    collection and path derivation.

    The provider categorizes paths into movement options:
    - Turn left: paths with indices 0-2
    - Advance: paths with indices 3-5
    - Turn right: paths with indices 6-8
    - Retreat: path with index 9

    Attributes
    ----------
    session : Optional[zenoh.Session]
        Zenoh session instance (currently unused, reserved for future use).
    paths : Optional[sensor_msgs.Paths]
        Current paths data from Zenoh subscription.
    turn_left : List[int]
        List of path indices representing left turn options.
    turn_right : List[int]
        List of path indices representing right turn options.
    advance : List[int]
        List of path indices representing forward movement options.
    retreat : bool
        Boolean flag indicating if backward movement is available.
    path_angles : List[int]
        Predefined angles in degrees for each path option.
    data_queue : mp.Queue
        Multiprocessing queue for receiving paths data from Zenoh subscriber.
    control_queue : mp.Queue
        Multiprocessing queue for sending control commands to processor.
    _valid_paths : Optional[sensor_msgs.Paths]
        Internal storage for the most recent valid paths data.
    _lidar_string : str
        Natural language description of available movement options.
    _simple_paths_processor_thread : Optional[mp.Process]
        Background process for Zenoh subscription and data collection.
    _simple_paths_derived_thread : Optional[threading.Thread]
        Background thread for processing paths data and generating movement options.
    _stop_event : threading.Event
        Event flag for signaling thread termination.

    Notes
    -----
    The provider uses a singleton pattern to ensure only one instance exists
    across the application. Initialization does not start background processes;
    call `start()` method to begin data collection and processing.
    """

    def __init__(self):
        """
        Initialize the SimplePathsProvider instance.

        Sets up all internal data structures, queues, and control mechanisms
        required for path processing. Does not start background processes;
        call `start()` method to begin operation.

        Notes
        -----
        - Initializes empty lists for movement options (turn_left, turn_right, advance)
        - Sets retreat flag to False
        - Creates multiprocessing queues with maxsize=5 for data_queue
        - Initializes thread control variables (threads set to None, stop_event created)
        - Path angles are predefined as [-60, -45, -30, -15, 0, 15, 30, 45, 60, 180]
        - Session and paths attributes are initialized to None
        """
        self.session = None
        self.paths = None

        # Paths attributes
        self.turn_left = []
        self.turn_right = []
        self.advance = []
        self.retreat = False

        # Valid paths list
        self._valid_paths = []

        # LLM string
        self._lidar_string = ""

        # Path angles for movement options
        self.path_angles = [-60, -45, -30, -15, 0, 15, 30, 45, 60, 180]

        # Data Queues for multiprocessing
        self.data_queue = mp.Queue(maxsize=5)
        self.control_queue = mp.Queue()

        # Thread control
        self._simple_paths_processor_thread = None
        self._simple_paths_derived_thread = None
        self._stop_event = threading.Event()

    def start(self):
        """
        Start the SimplePathsProvider by opening a Zenoh session.
        """
        if (
            not self._simple_paths_processor_thread
            or not self._simple_paths_processor_thread.is_alive()
        ):
            self._simple_paths_processor_thread = mp.Process(
                target=simple_paths_processor,
                args=(self.data_queue, self.control_queue, get_logging_config()),
            )
            self._simple_paths_processor_thread.start()
            logging.info("SimplePathsProvider started.")

        if (
            not self._simple_paths_derived_thread
            or not self._simple_paths_derived_thread.is_alive()
        ):
            self._simple_paths_derived_thread = threading.Thread(
                target=self._simple_paths_derived_processor,
                daemon=True,
            )
            self._simple_paths_derived_thread.start()
            logging.info("SimplePathsProvider derived processor started.")

    def stop(self):
        """
        Stop the SimplePathsProvider by closing the Zenoh session.
        """
        self._stop_event.set()

        if self._simple_paths_processor_thread:
            self.control_queue.put("STOP")
            self._simple_paths_processor_thread.join()
            logging.info("SimplePathsProvider stopped.")

        if self._simple_paths_derived_thread:
            self._simple_paths_derived_thread.join()
            logging.info("SimplePathsProvider derived processor stopped.")

    def _simple_paths_derived_processor(self):
        """
        Process paths data from the data queue and generate movement options.
        """
        while not self._stop_event.is_set():
            try:
                paths = self.data_queue.get_nowait()

                # Validate paths data structure
                if paths is None:
                    logging.warning("Received None paths data, skipping processing")
                    continue

                if not hasattr(paths, 'paths'):
                    logging.warning("Paths object missing 'paths' attribute, skipping processing")
                    continue

                if not isinstance(paths.paths, list):
                    logging.warning(f"Paths.paths is not a list (got {type(paths.paths)}), skipping processing")
                    continue

                if len(paths.paths) == 0:
                    logging.debug("Received empty paths list, resetting movement options")
                    self.turn_left = []
                    self.turn_right = []
                    self.advance = []
                    self.retreat = False
                    self._valid_paths = paths
                    self._lidar_string = self._generate_movement_string([])
                    continue

                self.turn_left = []
                self.turn_right = []
                self.advance = []
                self.retreat = False

                for path in paths.paths:
                    # Validate path index range (0-9)
                    if not isinstance(path, int):
                        logging.warning(f"Invalid path type: {type(path)}, expected int, skipping")
                        continue

                    if path < 0 or path > 9:
                        logging.warning(f"Path index {path} out of valid range [0-9], skipping")
                        continue

                    if path < 3:
                        self.turn_left.append(path)
                    elif path >= 3 and path <= 5:
                        self.advance.append(path)
                    elif path < 9:
                        self.turn_right.append(path)
                    elif path == 9:
                        self.retreat = True

                self._valid_paths = paths
                self._lidar_string = self._generate_movement_string(paths.paths)

            except Empty:
                time.sleep(0.1)
                continue
            except Exception as e:
                logging.error(f"Unexpected error in path processing: {e}", exc_info=True)
                time.sleep(0.1)
                continue

    def _generate_movement_string(self, valid_paths: List[int]) -> str:
        """
        Generate movement direction string based on valid paths.

        Parameters
        ----------
        valid_paths : List[int]
            A list of valid path indices represented as integers (0-9).
            Each integer corresponds to a specific movement direction:
            - 0-2: Turn left options
            - 3-5: Advance (forward) options
            - 6-8: Turn right options
            - 9: Retreat (backward) option

        Returns
        -------
        str
            A string describing the safe movement directions based on the valid paths.
            Returns a warning message if no valid paths are available.
        """
        if not valid_paths:
            return "You are surrounded by objects and cannot safely move in any direction. DO NOT MOVE."

        parts = ["The safe movement directions are: {"]

        if self.turn_left:
            parts.append("'turn left', ")
        if self.advance:
            parts.append("'move forwards', ")
        if self.turn_right:
            parts.append("'turn right', ")
        if self.retreat:
            parts.append("'move back', ")

        parts.append("'stand still'}. ")
        return "".join(parts)

    @property
    def valid_paths(self) -> Optional[List]:
        """
        Get the currently valid paths.

        Returns
        -------
        Optional[list]
            The currently valid paths as a list, or None if not
            available. The list contains 0 to 10 entries,
            corresponding to possible paths - for example: [0,3,4,5]
        """
        return self._valid_paths

    @property
    def lidar_string(self) -> str:
        """
        Get the latest natural language assessment of possible paths.

        Returns
        -------
        str
            A natural language summary of possible motion paths
        """
        return self._lidar_string

    @property
    def movement_options(self) -> Dict[str, Union[List[int], bool]]:
        """
        Get the movement options based on the current valid paths.

        Returns
        -------
        Dict[str, List[int]]
            A dictionary containing lists of valid movement options:
            - 'turn_left': Indices for turning left
            - 'advance': Indices for moving forward
            - 'turn_right': Indices for turning right
            - 'retreat': Indices for moving backward
        """
        return {
            "turn_left": self.turn_left,
            "advance": self.advance,
            "turn_right": self.turn_right,
            "retreat": self.retreat,
        }

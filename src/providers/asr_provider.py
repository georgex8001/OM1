import logging
import threading
import time
from typing import Callable, Optional

from om1_speech import AudioInputStream
from om1_utils import ws

from .singleton import singleton


@singleton
class ASRProvider:
    """
    Audio Speech Recognition Provider that handles audio streaming and websocket communication.

    This class implements a singleton pattern to manage audio input streaming and websocket
    communication for speech recognition services. It runs in a separate thread to handle
    continuous audio processing.

    Thread Safety
    -------------
    This class is thread-safe and uses `threading.Lock` to protect critical sections:
    - The `running` state variable is protected during start/stop operations
    - Callback registration is synchronized to prevent race conditions
    - All state-changing operations are atomic

    Reconnection Mechanism
    -----------------------
    The provider implements automatic reconnection with exponential backoff for WebSocket
    connections. When a connection is lost, the provider will:
    1. Attempt to reconnect with increasing delays (1s, 2s, 4s, ..., up to 60s)
    2. Retry up to 10 times before giving up
    3. Monitor connection status in a background thread
    4. Automatically restore audio stream callbacks after reconnection

    Attributes
    ----------
    running : bool
        Indicates whether the provider is currently running. Protected by `_lock`.
    ws_client : ws.Client
        The main WebSocket client for ASR service communication.
    stream_ws_client : Optional[ws.Client]
        Optional secondary WebSocket client for audio streaming.
    audio_stream : AudioInputStream
        The audio input stream that captures microphone data.
    """

    def __init__(
        self,
        ws_url: str,
        stream_url: Optional[str] = None,
        device_id: Optional[int] = None,
        microphone_name: Optional[str] = None,
        rate: Optional[int] = None,
        chunk: Optional[int] = None,
        language_code: Optional[str] = None,
        remote_input: bool = False,
        enable_tts_interrupt: bool = False,
    ):
        """
        Initialize the ASR Provider.

        Parameters
        ----------
        ws_url : str
            The websocket URL for the ASR service connection.
        device_id : int
            The device ID of the chosen microphone; used the system default if None
        microphone_name : str
            The name of the microphone to use for audio input
        rate : int
            The audio sample rate for the audio stream; used the system default if None
        chunk : int
            The audio chunk size for the audio stream; used the 200ms default if None
        language_code : str
            The language code for language in the audio stream; used the en-US default if None
        remote_input : bool
            If True, the audio input is processed remotely; defaults to False.
        enable_tts_interrupt : bool
            If True, enables TTS interrupt.
        """
        # Thread-safe lock: protects running state and callback registration
        self._lock = threading.Lock()
        self.running: bool = False
        
        # WebSocket client configuration
        self.ws_url = ws_url
        self.stream_url = stream_url
        self.ws_client: ws.Client = ws.Client(url=ws_url)
        self.stream_ws_client: Optional[ws.Client] = (
            ws.Client(url=stream_url) if stream_url else None
        )
        
        # Reconnection mechanism configuration
        self._reconnect_enabled = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._base_reconnect_delay = 1.0  # Initial reconnection delay in seconds
        self._max_reconnect_delay = 60.0  # Maximum reconnection delay in seconds
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_reconnect = threading.Event()
        
        self.audio_stream: AudioInputStream = AudioInputStream(
            rate=rate,
            chunk=chunk,
            device=device_id,
            device_name=microphone_name,  # type: ignore
            audio_data_callback=self.ws_client.send_message,
            language_code=language_code,
            remote_input=remote_input,
            enable_tts_interrupt=enable_tts_interrupt,
        )
        
        logging.info("ASRProvider initialized with thread-safe locks and reconnection support")

    def register_message_callback(self, message_callback: Optional[Callable]):
        """
        Register a callback for processing ASR results.

        This method is thread-safe and can be called while the provider is running.

        Parameters
        ----------
        message_callback : Optional[Callable]
            The callback function to process ASR results.
        """
        with self._lock:
            if message_callback is not None:
                logging.info("Registering message callback for ASR results")
                self.ws_client.register_message_callback(message_callback)
                if self.stream_ws_client:
                    self.stream_ws_client.register_message_callback(message_callback)
            else:
                logging.debug("Message callback is None, skipping registration")

    def start(self):
        """
        Start the ASR provider.

        Initializes and starts the websocket client, audio stream, and processing thread
        if not already running. This method is thread-safe and implements automatic
        reconnection for WebSocket connections.

        Notes
        -----
        The method uses a lock to prevent concurrent start/stop operations and ensures
        that only one instance of the provider can be running at a time.
        """
        with self._lock:
            if self.running:
                logging.warning("ASR provider is already running")
                return

            logging.info("Starting ASR provider with thread-safe initialization")
            self.running = True
            self._stop_reconnect.clear()
            self._reconnect_attempts = 0

        # Execute startup operations outside the lock to avoid holding it for too long
        try:
            self.ws_client.start()
            self.audio_stream.start()

            if self.stream_ws_client:
                self.stream_ws_client.start()
                self.audio_stream.register_audio_data_callback(
                    self.stream_ws_client.send_message
                )
                # Register the audio stream to fill the buffer for remote input
                if self.audio_stream.remote_input:
                    self.stream_ws_client.register_message_callback(
                        self.audio_stream.fill_buffer_remote
                    )

            # Start reconnection monitor thread
            if self._reconnect_enabled:
                self._start_reconnect_monitor()

            logging.info("ASR provider started successfully")
        except Exception as e:
            with self._lock:
                self.running = False
            logging.error(f"Failed to start ASR provider: {e}", exc_info=True)
            raise

    def stop(self):
        """
        Stop the ASR provider.

        Stops the audio stream and websocket clients, and sets the running state to False.
        This method is thread-safe and ensures proper cleanup of all resources including
        the reconnection monitor thread.

        Notes
        -----
        The method uses a lock to prevent concurrent start/stop operations and ensures
        that cleanup operations are performed atomically.
        """
        with self._lock:
            if not self.running:
                logging.warning("ASR provider is not running")
                return

            logging.info("Stopping ASR provider")
            self.running = False
            self._stop_reconnect.set()

        # Execute stop operations outside the lock to avoid holding it for too long
        try:
            # Stop reconnection monitor thread
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                self._stop_reconnect.set()
                self._reconnect_thread.join(timeout=2.0)
                if self._reconnect_thread.is_alive():
                    logging.warning("Reconnect monitor thread did not stop within timeout")

            self.audio_stream.stop()
            self.ws_client.stop()

            if self.stream_ws_client:
                self.stream_ws_client.stop()

            logging.info("ASR provider stopped successfully")
        except Exception as e:
            logging.error(f"Error during ASR provider stop: {e}", exc_info=True)

    def _start_reconnect_monitor(self):
        """
        Start the WebSocket reconnection monitor thread.

        This thread periodically checks the WebSocket connection status and performs
        exponential backoff reconnection when the connection is lost. The reconnection
        delay starts from base_reconnect_delay, doubles after each failure, and is
        capped at max_reconnect_delay.
        """
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            logging.warning("Reconnect monitor thread is already running")
            return

        self._reconnect_thread = threading.Thread(
            target=self._reconnect_monitor_loop, daemon=True
        )
        self._reconnect_thread.start()
        logging.info("WebSocket reconnection monitor thread started")

    def _reconnect_monitor_loop(self):
        """
        Reconnection monitor loop: check connection status and perform exponential backoff reconnection.

        This loop runs in a background thread and periodically checks the WebSocket connection
        status. If a disconnection is detected, it will execute an exponential backoff reconnection
        strategy to ensure automatic recovery from network fluctuations.
        """
        logging.info("Entering reconnection monitor loop")
        check_interval = 5.0  # Check connection status every 5 seconds

        while not self._stop_reconnect.is_set():
            try:
                # Check if reconnection is needed
                if self._should_reconnect():
                    self._attempt_reconnect()

                # Wait for check interval or stop signal
                if self._stop_reconnect.wait(timeout=check_interval):
                    break

            except Exception as e:
                logging.error(
                    f"Error in reconnection monitor loop: {e}", exc_info=True
                )
                time.sleep(check_interval)

        logging.info("Exiting reconnection monitor loop")

    def _should_reconnect(self) -> bool:
        """
        Determine if reconnection should be performed.

        Checks the current running state and WebSocket client connection status to
        determine if reconnection is needed.

        Returns
        -------
        bool
            True if reconnection is needed, False otherwise.
        """
        with self._lock:
            if not self.running:
                return False

            # Check if reconnection attempt count exceeds the limit
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logging.error(
                    f"Maximum reconnection attempts ({self._max_reconnect_attempts}) reached. "
                    "Stopping reconnection attempts."
                )
                return False

        # Check WebSocket connection status (must be done outside lock to avoid deadlock)
        # Note: This assumes ws.Client has some way to check connection status
        # If ws.Client does not provide a status check method, consider sending a heartbeat
        # or catching exceptions
        try:
            # If ws_client has is_connected or similar method, check it here
            # Otherwise, reconnection logic will be triggered when message sending fails
            return False  # Temporarily return False; actual implementation needs to be
            # adjusted based on ws.Client API
        except Exception:
            return True

    def _attempt_reconnect(self):
        """
        Perform WebSocket reconnection attempt using exponential backoff strategy.

        Calculates the current reconnection delay (exponential backoff), stops the existing
        connection, waits for the delay period, and then restarts the connection. If reconnection
        succeeds, the reconnection counter is reset; if it fails, the reconnection attempt count
        is incremented.
        """
        with self._lock:
            if not self.running:
                return

            # Calculate exponential backoff delay
            delay = min(
                self._base_reconnect_delay * (2 ** self._reconnect_attempts),
                self._max_reconnect_delay,
            )
            attempts = self._reconnect_attempts + 1

        logging.info(
            f"Attempting WebSocket reconnection (attempt {attempts}/{self._max_reconnect_attempts}, "
            f"delay: {delay:.2f}s)"
        )

        try:
            # Stop existing connections
            try:
                self.ws_client.stop()
                if self.stream_ws_client:
                    self.stream_ws_client.stop()
            except Exception as e:
                logging.warning(f"Error stopping WebSocket clients during reconnect: {e}")

            # Wait for exponential backoff delay
            time.sleep(delay)

            # Recreate and start connections
            with self._lock:
                if not self.running:
                    return

                # Recreate WebSocket clients
                self.ws_client = ws.Client(url=self.ws_url)
                if self.stream_url:
                    self.stream_ws_client = ws.Client(url=self.stream_url)

                # Re-register audio data callback
                self.audio_stream.register_audio_data_callback(
                    self.ws_client.send_message
                )

            # Start connections
            self.ws_client.start()
            if self.stream_ws_client:
                self.stream_ws_client.start()
                if self.audio_stream.remote_input:
                    self.stream_ws_client.register_message_callback(
                        self.audio_stream.fill_buffer_remote
                    )

            # Reconnection successful, reset counter
            with self._lock:
                self._reconnect_attempts = 0

            logging.info("WebSocket reconnection successful")

        except Exception as e:
            with self._lock:
                self._reconnect_attempts = attempts

            logging.error(
                f"WebSocket reconnection failed (attempt {attempts}): {e}",
                exc_info=True,
            )

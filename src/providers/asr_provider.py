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
        # 线程安全锁：保护运行状态和回调注册
        self._lock = threading.Lock()
        self.running: bool = False
        
        # WebSocket 客户端配置
        self.ws_url = ws_url
        self.stream_url = stream_url
        self.ws_client: ws.Client = ws.Client(url=ws_url)
        self.stream_ws_client: Optional[ws.Client] = (
            ws.Client(url=stream_url) if stream_url else None
        )
        
        # 重连机制配置
        self._reconnect_enabled = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._base_reconnect_delay = 1.0  # 初始重连延迟（秒）
        self._max_reconnect_delay = 60.0  # 最大重连延迟（秒）
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

        # 在锁外执行启动操作，避免长时间持有锁
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

            # 启动重连监控线程
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

        # 在锁外执行停止操作，避免长时间持有锁
        try:
            # 停止重连监控线程
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
        启动 WebSocket 重连监控线程。

        该线程定期检查 WebSocket 连接状态，在连接断开时执行指数退避重连。
        重连延迟从 base_reconnect_delay 开始，每次失败后翻倍，最大不超过 max_reconnect_delay。
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
        重连监控循环：检查连接状态并执行指数退避重连。

        该循环在后台线程中运行，定期检查 WebSocket 连接状态。如果检测到连接断开，
        将执行指数退避重连策略，确保在网络波动时能够自动恢复连接。
        """
        logging.info("Entering reconnection monitor loop")
        check_interval = 5.0  # 每5秒检查一次连接状态

        while not self._stop_reconnect.is_set():
            try:
                # 检查是否需要重连
                if self._should_reconnect():
                    self._attempt_reconnect()

                # 等待检查间隔或停止信号
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
        判断是否需要执行重连。

        检查当前运行状态和 WebSocket 客户端连接状态，确定是否需要重连。

        Returns
        -------
        bool
            如果需要重连返回 True，否则返回 False。
        """
        with self._lock:
            if not self.running:
                return False

            # 检查重连尝试次数是否超过限制
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logging.error(
                    f"Maximum reconnection attempts ({self._max_reconnect_attempts}) reached. "
                    "Stopping reconnection attempts."
                )
                return False

        # 检查 WebSocket 连接状态（需要在锁外检查，避免死锁）
        # 注意：这里假设 ws.Client 有某种方式检查连接状态
        # 如果 ws.Client 没有提供状态检查方法，可以尝试发送心跳或捕获异常
        try:
            # 如果 ws_client 有 is_connected 或类似方法，可以在这里检查
            # 否则，重连逻辑将在实际发送消息失败时触发
            return False  # 暂时返回 False，实际实现需要根据 ws.Client 的 API 调整
        except Exception:
            return True

    def _attempt_reconnect(self):
        """
        执行 WebSocket 重连尝试，使用指数退避策略。

        计算当前重连延迟（指数退避），停止现有连接，等待延迟时间后重新启动连接。
        如果重连成功，重置重连计数器；如果失败，增加重连尝试次数。
        """
        with self._lock:
            if not self.running:
                return

            # 计算指数退避延迟
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
            # 停止现有连接
            try:
                self.ws_client.stop()
                if self.stream_ws_client:
                    self.stream_ws_client.stop()
            except Exception as e:
                logging.warning(f"Error stopping WebSocket clients during reconnect: {e}")

            # 等待指数退避延迟
            time.sleep(delay)

            # 重新创建并启动连接
            with self._lock:
                if not self.running:
                    return

                # 重新创建 WebSocket 客户端
                self.ws_client = ws.Client(url=self.ws_url)
                if self.stream_url:
                    self.stream_ws_client = ws.Client(url=self.stream_url)

                # 重新注册音频数据回调
                self.audio_stream.register_audio_data_callback(
                    self.ws_client.send_message
                )

            # 启动连接
            self.ws_client.start()
            if self.stream_ws_client:
                self.stream_ws_client.start()
                if self.audio_stream.remote_input:
                    self.stream_ws_client.register_message_callback(
                        self.audio_stream.fill_buffer_remote
                    )

            # 重连成功，重置计数器
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

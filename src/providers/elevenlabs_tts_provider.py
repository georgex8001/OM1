import logging
import threading
from typing import Callable, Optional, Union

from om1_speech import AudioOutputStream

from .singleton import singleton

logger = logging.getLogger(__name__)


@singleton
class ElevenLabsTTSProvider:
    """
    Text-to-Speech Provider that manages an audio output stream.

    A singleton class that handles text-to-speech conversion and audio output
    through a dedicated thread.

    Parameters
    ----------
    url : str, optional
        The URL endpoint for the TTS service.
        Defaults to "https://api.openmind.org/api/core/elevenlabs/tts".
    api_key : str, optional
        The API key for the TTS service. If provided, it is sent via request headers.
        Defaults to None.
    elevenlabs_api_key : str, optional
        An alternative ElevenLabs-specific API key. If provided, it is included in
        the request payload. Defaults to None.
    voice_id : str, optional
        The voice identifier to use for synthesis.
        Defaults to "JBFqnCBsd6RMkjVDRZzb".
    model_id : str, optional
        The model identifier to use for synthesis.
        Defaults to "eleven_flash_v2_5".
    output_format : str, optional
        The output format for the audio stream.
        Defaults to "mp3_44100_128".
    enable_tts_interrupt : bool, optional
        If True, enables the ability to interrupt ongoing TTS playback when ASR detects
        new speech input. Defaults to False.
    """

    def __init__(
        self,
        url: str = "https://api.openmind.org/api/core/elevenlabs/tts",
        api_key: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None,
        voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb",
        model_id: Optional[str] = "eleven_flash_v2_5",
        output_format: Optional[str] = "mp3_44100_128",
        enable_tts_interrupt: bool = False,
    ):
        """
        Initialize the ElevenLabsTTSProvider instance.

        Sets up the configuration for the Eleven Labs TTS service, including API keys,
        voice/model selection, output format, and interrupt settings. It initializes
        the underlying audio output stream.

        Parameters
        ----------
        url : str, optional
            The URL endpoint for the TTS service.
            Defaults to "https://api.openmind.org/api/core/elevenlabs/tts".
        api_key : str, optional
            The primary API key for the TTS service. If provided, it's used in the
            request headers. Defaults to None.
        elevenlabs_api_key : str, optional
            An alternative Eleven Labs specific API key. If provided, it's included
            in the request payload for TTS generation. Defaults to None.
        voice_id : str, optional
            The ID/name of the voice to use for TTS synthesis.
            Defaults to "JBFqnCBsd6RMkjVDRZzb".
        model_id : str, optional
            The ID/name of the model to use for TTS synthesis.
            Defaults to "eleven_flash_v2_5".
        output_format : str, optional
            The desired audio output format (e.g., mp3, wav).
            Defaults to "mp3_44100_128".
        enable_tts_interrupt : bool, optional
            If True, enables the ability to interrupt ongoing TTS playback when ASR
            detects new speech input. Defaults to False.
        """
        self._lock = threading.RLock()
        self.api_key = api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        self._enable_tts_interrupt = enable_tts_interrupt

        # Initialize TTS provider
        self.running: bool = False
        self._audio_stream: AudioOutputStream = AudioOutputStream(
            url=url,
            headers={"x-api-key": api_key} if api_key else None,
            enable_tts_interrupt=enable_tts_interrupt,
        )

        # Set Eleven Labs TTS parameters
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format

    def configure(
        self,
        url: str = "https://api.openmind.org/api/core/elevenlabs/tts",
        api_key: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None,
        voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb",
        model_id: Optional[str] = "eleven_flash_v2_5",
        output_format: Optional[str] = "mp3_44100_128",
        enable_tts_interrupt: bool = False,
    ):
        """
        Configure the TTS provider with given parameters.

        Parameters
        ----------
        url : str, optional
            The URL endpoint for the TTS service.
            Defaults to "https://api.openmind.org/api/core/elevenlabs/tts".
        api_key : str, optional
            The API key for the TTS service. If provided, it is sent via request headers.
            Defaults to None.
        elevenlabs_api_key : str, optional
            An alternative ElevenLabs-specific API key. If provided, it is included in
            the request payload. Defaults to None.
        voice_id : str, optional
            The voice identifier to use for synthesis.
        model_id : str, optional
            The model identifier to use for synthesis.
        output_format : str, optional
            The output format for the audio stream.
        enable_tts_interrupt : bool, optional
            If True, enables TTS interrupt when ASR detects speech.
            Defaults to False.
        """
        with self._lock:
            restart_needed = (
                url != self._audio_stream._url
                or api_key != self.api_key
                or elevenlabs_api_key != self.elevenlabs_api_key
                or voice_id != self._voice_id
                or model_id != self._model_id
                or output_format != self._output_format
                or enable_tts_interrupt != self._enable_tts_interrupt
            )

            if not restart_needed:
                return

            was_running = self.running

            self.api_key = api_key
            self.elevenlabs_api_key = elevenlabs_api_key
            self._voice_id = voice_id
            self._model_id = model_id
            self._output_format = output_format
            self._enable_tts_interrupt = enable_tts_interrupt

            new_stream: AudioOutputStream = AudioOutputStream(
                url=url,
                headers={"x-api-key": api_key} if api_key else None,
                enable_tts_interrupt=enable_tts_interrupt,
            )

        if was_running:
            self.stop()

        with self._lock:
            self._audio_stream = new_stream

        if was_running:
            self.start()

    def register_tts_state_callback(self, tts_state_callback: Optional[Callable]):
        """
        Register a callback for TTS state changes.

        Parameters
        ----------
        tts_state_callback : Optional[Callable]
            The callback function to receive TTS state changes.
        """
        if tts_state_callback is None:
            return

        with self._lock:
            stream = self._audio_stream

        stream.set_tts_state_callback(tts_state_callback)

    def create_pending_message(self, text: str) -> dict:
        """
        Create a pending message for TTS processing.

        Parameters
        ----------
        text : str
            Text to be converted to speech

        Returns
        -------
        dict
            A dictionary containing the TTS request parameters.
        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("tts enqueue: text_len=%d", len(text))

        with self._lock:
            elevenlabs_api_key = (
                {"elevenlabs_api_key": self.elevenlabs_api_key}
                if self.elevenlabs_api_key
                else {}
            )
            voice_id = self._voice_id
            model_id = self._model_id
            output_format = self._output_format

        return {
            "text": text,
            "voice_id": voice_id,
            "model_id": model_id,
            "output_format": output_format,
            **elevenlabs_api_key,
        }

    def add_pending_message(self, message: Union[str, dict]):
        """
        Add a pending message to the TTS provider.

        Parameters
        ----------
        message : Union[str, dict]
            The message to be added, typically containing text and TTS parameters.
        """
        with self._lock:
            running = self.running
            stream = self._audio_stream

        if not running:
            logger.warning("TTS provider is not running. Call start() before adding messages.")
            return

        try:
            if isinstance(message, str):
                message = self.create_pending_message(message)
            stream.add_request(message)
        except Exception:
            logger.error("Failed to enqueue TTS request.", exc_info=True)
            raise

    def get_pending_message_count(self) -> int:
        """
        Get the count of pending messages in the TTS provider.

        Returns
        -------
        int
            The number of pending messages.
        """
        with self._lock:
            stream = self._audio_stream

        return stream._pending_requests.qsize()

    def start(self):
        """
        Start the TTS provider and its audio stream.
        """
        with self._lock:
            if self.running:
                logger.warning("Eleven Labs TTS provider is already running")
                return

            self.running = True
            stream = self._audio_stream

        stream.start()

    def stop(self):
        """
        Stop the TTS provider and cleanup resources.
        """
        with self._lock:
            if not self.running:
                logger.warning("Eleven Labs TTS provider is not running")
                return

            self.running = False
            stream = self._audio_stream

        stream.stop()

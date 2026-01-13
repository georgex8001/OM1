import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

from .singleton import singleton


class MessageType(Enum):
    """
    Enumeration for message types in the conversation.

    This enum defines the two types of messages that can be stored in a
    conversation: user messages and robot messages.

    Attributes
    ----------
    USER : str
        Represents a message sent by the user.
    ROBOT : str
        Represents a message sent by the robot.
    """

    USER = "user"
    ROBOT = "robot"


@dataclass
class ConversationMessage:
    """
    Represents a conversation message with type, content, and timestamp.

    This dataclass encapsulates a single message in a conversation, including
    its type (user or robot), content, and timestamp for chronological ordering.

    Attributes
    ----------
    message_type : MessageType
        The type of the message, either USER or ROBOT.
    content : str
        The text content of the message.
    timestamp : float
        The Unix timestamp when the message was created, typically obtained
        using time.time().

    Examples
    --------
    >>> msg = ConversationMessage(
    ...     message_type=MessageType.USER,
    ...     content="Hello, robot!",
    ...     timestamp=time.time()
    ... )
    >>> msg_dict = msg.to_dict()
    """

    message_type: MessageType
    content: str
    timestamp: float

    def to_dict(self) -> dict:
        """
        Convert the ConversationMessage to a dictionary.

        Returns
        -------
        dict
            Dictionary representation of the ConversationMessage.
        """
        return {
            "type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationMessage":
        """
        Create a ConversationMessage from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary containing message data.

        Returns
        -------
        ConversationMessage
            The created ConversationMessage instance.
        """
        return cls(
            message_type=MessageType(data.get("type", MessageType.USER.value)),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", 0.0),
        )


@singleton
class TeleopsConversationProvider:
    """
    Singleton provider for managing conversation messages with a Teleops backend.

    This provider enables robots to store and manage conversation history by sending
    user and robot messages to a remote Teleops API. It uses a thread pool executor
    to handle message storage asynchronously, ensuring non-blocking operation.

    The provider implements a singleton pattern, ensuring only one instance exists
    throughout the application lifecycle. This is useful for maintaining conversation
    state across different components of the robot system.

    Attributes
    ----------
    api_key : Optional[str]
        The API key for authenticating with the Teleops backend. If None or empty,
        message storage operations will be skipped.
    base_url : str
        The base URL for the Teleops conversation API endpoint.
    executor : ThreadPoolExecutor
        Thread pool executor used for asynchronous message storage operations.

    Examples
    --------
    >>> provider = TeleopsConversationProvider(api_key="your-api-key")
    >>> provider.store_user_message("Hello, robot!")
    >>> provider.store_robot_message("Hi there! How can I help?")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openmind.org/api/core/teleops/conversation",
    ):
        """
        Initialize the TeleopsConversationProvider.

        Parameters
        ----------
        api_key : Optional[str], optional
            The API key for authenticating with the Teleops backend. If None or empty,
            the provider will be disabled and message storage operations will be skipped.
            Defaults to None.
        base_url : str, optional
            The base URL for the Teleops conversation API endpoint. Defaults to
            "https://api.openmind.org/api/core/teleops/conversation".

        Notes
        -----
        The provider uses a ThreadPoolExecutor with a single worker thread to handle
        message storage operations asynchronously. This ensures that HTTP requests to
        the Teleops backend do not block the main execution thread.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.executor = ThreadPoolExecutor(max_workers=1)

    def store_user_message(self, content: str) -> None:
        """
        Store a user message in the conversation.

        This method creates a ConversationMessage with type USER and submits it
        to the Teleops backend asynchronously via the thread pool executor.

        Parameters
        ----------
        content : str
            The content of the user message. The content will be stripped of
            leading and trailing whitespace before storage.

        Notes
        -----
        The message storage is performed asynchronously, so this method returns
        immediately without waiting for the HTTP request to complete. If the
        API key is not set, the message will not be stored.
        """
        message = ConversationMessage(
            message_type=MessageType.USER,
            content=content.strip(),
            timestamp=time.time(),
        )
        self._store_message(message)

    def store_robot_message(self, content: str) -> None:
        """
        Store a robot message in the conversation.

        This method creates a ConversationMessage with type ROBOT and submits it
        to the Teleops backend asynchronously via the thread pool executor.

        Parameters
        ----------
        content : str
            The content of the robot message. The content will be stripped of
            leading and trailing whitespace before storage.

        Notes
        -----
        The message storage is performed asynchronously, so this method returns
        immediately without waiting for the HTTP request to complete. If the
        API key is not set, the message will not be stored.
        """
        message = ConversationMessage(
            message_type=MessageType.ROBOT,
            content=content.strip(),
            timestamp=time.time(),
        )
        self._store_message(message)

    def _store_message_worker(self, message: ConversationMessage) -> None:
        """
        Worker method to store a conversation message via HTTP POST.

        This method performs the actual HTTP POST request to the Teleops backend.
        It handles API key validation, empty content checks, and error handling.

        Parameters
        ----------
        message : ConversationMessage
            The conversation message to store. Must have non-empty content.

        Notes
        -----
        This method is called by the thread pool executor. It will skip storage
        if the API key is missing or if the message content is empty. All errors
        are logged at the debug level and do not raise exceptions.
        """
        if self.api_key is None or self.api_key == "":
            logging.debug("API key is missing. Cannot store conversation message.")
            return

        if not message.content or not message.content.strip():
            logging.debug("Empty content, skipping conversation storage")
            return

        try:
            request = requests.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=message.to_dict(),
                timeout=2,
            )

            if request.status_code == 200:
                logging.debug(
                    f"Successfully stored {message.message_type.value} message to conversation"
                )
            else:
                logging.debug(
                    f"Failed to store {message.message_type.value} message: {request.status_code} - {request.text}"
                )
        except Exception as e:
            logging.debug(
                f"Error storing {message.message_type.value} conversation message: {str(e)}"
            )

    def _store_message(self, message: ConversationMessage) -> None:
        """
        Submit the message storage task to the executor.

        This method schedules the message storage operation to run asynchronously
        in the thread pool executor.

        Parameters
        ----------
        message : ConversationMessage
            The conversation message to store. The actual storage is performed
            by the _store_message_worker method in a separate thread.

        Notes
        -----
        The message storage is non-blocking. The executor will handle the HTTP
        request in a background thread, allowing the main thread to continue
        execution immediately.
        """
        self.executor.submit(self._store_message_worker, message)

    def is_enabled(self) -> bool:
        """
        Check if the Teleops conversation provider is enabled.

        Returns
        -------
        bool
            True if the API key is set, False otherwise.
        """
        return self.api_key is not None and self.api_key != ""

import logging
from typing import Callable, Optional

import zenoh

from zenoh_msgs import open_zenoh_session


class ZenohListenerProvider:
    """
    Listener provider for subscribing messages using a Zenoh session.

    This class manages a Zenoh session and subscribes to messages on a specified
    topic. It provides a callback mechanism for processing incoming messages
    asynchronously.

    Attributes
    ----------
    session : Optional[zenoh.Session]
        The Zenoh session instance used for subscribing to messages. Set to None
        if session initialization fails.
    sub_topic : str
        The topic name on which to subscribe messages.
    running : bool
        Flag indicating whether the listener provider is currently active.
    """

    def __init__(self, topic: str = "speech"):
        """
        Initialize the Zenoh Listener provider and create a Zenoh session.

        Parameters
        ----------
        topic : str, optional
            The topic name on which to subscribe messages. Defaults to "speech".
            The topic should match the publisher's topic for successful message
            delivery.

        Notes
        -----
        The initialization process consists of the following steps:
        1. Attempts to open a Zenoh session using `open_zenoh_session()`.
        2. If session creation fails, logs an error and sets `session` to None.
        3. Stores the subscription topic name for later use.
        4. Initializes the `running` flag to False.

        The provider will not be able to receive messages until `start()` is called
        with a valid message callback function.
        """
        self.session: Optional[zenoh.Session] = None

        try:
            self.session = open_zenoh_session()
            logging.info("Zenoh client opened")
        except Exception as e:
            logging.error(f"Error opening Zenoh client: {e}")

        self.sub_topic = topic

        self.running: bool = False

    def register_message_callback(self, message_callback: Optional[Callable]):
        """
        Register a callback function for processing incoming messages.

        Parameters
        ----------
        message_callback : Optional[Callable]
            The function that will be called with each incoming Zenoh sample.
            The callback should accept a single argument of type `zenoh.Sample`.
            If None, no callback is registered.

        Notes
        -----
        This method declares a subscriber on the configured topic. If the Zenoh
        session is not available (None), an error is logged and no subscriber
        is created. The callback will be invoked automatically whenever a message
        is published to the subscribed topic.
        """
        if self.session is not None:
            self.session.declare_subscriber(self.sub_topic, message_callback)
        else:
            logging.error("Cannot register callback; Zenoh session is not available.")

    def start(self, message_callback: Optional[Callable] = None):
        """
        Start the listener provider and register the message callback.

        Parameters
        ----------
        message_callback : Optional[Callable], optional
            The callback function to process incoming messages. If provided,
            it will be registered using `register_message_callback()`. If None,
            the callback must be registered separately before messages can be
            processed.

        Notes
        -----
        This method sets the `running` flag to True and registers the message
        callback if provided. If the provider is already running, a warning is
        logged and the method returns without making changes.
        """
        if self.running:
            logging.warning("Zenoh Listener Provider is already running")
            return

        if message_callback is not None:
            self.register_message_callback(message_callback)

        self.running = True
        logging.info("Zenoh Listener Provider started")

    def stop(self):
        """
        Stop the listener provider and clean up resources.

        Notes
        -----
        This method performs the following cleanup operations:
        1. Sets the `running` flag to False to signal shutdown.
        2. Closes the Zenoh session if it is available, which automatically
           unsubscribes from the topic and releases network resources.

        After calling this method, the provider will no longer receive messages
        until `start()` is called again.
        """
        self.running = False

        if self.session is not None:
            self.session.close()

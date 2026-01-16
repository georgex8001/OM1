import logging

import aiohttp
from pydantic import Field

from actions.base import ActionConfig, ActionConnector
from actions.discord.interface import DiscordInput


class DiscordAPIConfig(ActionConfig):
    """
    Configuration class for DiscordAPIConnector.
    """

    webhook_url: str = Field(description="Discord Webhook URL for sending messages")


class DiscordAPIConnector(ActionConnector[DiscordAPIConfig, DiscordInput]):
    """
    Connector for Discord Webhook API.

    This connector integrates with Discord Webhook API to send messages from the robot.
    """

    def __init__(self, config: DiscordAPIConfig):
        """
        Initialize the Discord API connector.

        Parameters
        ----------
        config : DiscordAPIConfig
            Configuration object for the connector.
        """
        super().__init__(config)

        if not self.config.webhook_url:
            logging.warning("Discord Webhook URL not provided in configuration")

    async def connect(self, output_interface: DiscordInput) -> None:
        """
        Send message via Discord Webhook API.

        Parameters
        ----------
        output_interface : DiscordInput
            The DiscordInput interface containing the message text.
        """
        if not self.config.webhook_url:
            logging.error("Discord webhook URL not configured")
            return

        try:
            message_text = output_interface.action
            logging.info(f"SendThisToDiscord: {message_text}")

            payload = {"content": message_text}

            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=payload) as response:
                    if response.status == 204:
                        logging.info("Discord message sent successfully!")
                    else:
                        error_text = await response.text()
                        logging.error(
                            f"Discord API error: {response.status} - {error_text}"
                        )

        except Exception as e:
            logging.error(f"Failed to send Discord message: {str(e)}")
            raise

from dataclasses import dataclass

from actions.base import Interface


@dataclass
class DiscordInput:
    """
    Input interface for the Discord Message action.

    Parameters
    ----------
    action : str
        The text content to be sent as a message to Discord.
        Can include emojis and basic formatting.
    """

    action: str = ""


@dataclass
class Discord(Interface[DiscordInput, DiscordInput]):
    """
    This action allows the robot to send messages to Discord.

    Effect: Sends the specified text content as a message to the configured
    Discord channel using a Webhook URL. The message is sent immediately
    and logged upon successful delivery.
    """

    input: DiscordInput
    output: DiscordInput

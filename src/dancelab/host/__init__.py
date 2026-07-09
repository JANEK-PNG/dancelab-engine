"""External host-shell helpers for graph-based control surfaces."""

from dancelab.host.desktop_app import (
    desktop_available,
    desktop_requirement_message,
    launch_desktop_host,
)
from dancelab.host.node_shell import load_node_host_shell_html

__all__ = [
    "desktop_available",
    "desktop_requirement_message",
    "launch_desktop_host",
    "load_node_host_shell_html",
]

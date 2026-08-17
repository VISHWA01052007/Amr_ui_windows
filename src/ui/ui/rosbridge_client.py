"""
rosbridge_client.py
-------------------
Windows-side ROS 2 communication through rosbridge_websocket.

Uses roslibpy's normal non-blocking `run()` API.
roslibpy manages the WebSocket connection and reconnection.
"""

from typing import Optional, Callable, Dict

import roslibpy


class RosbridgeClient:

    def __init__(
        self,
        host: str,
        port: int = 9090,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
    ) -> None:

        self.host = host
        self.port = port

        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

        # One ROS connection object.
        self._ros: Optional[roslibpy.Ros] = None

        # Publisher/subscriber cache.
        self._topics: Dict[str, roslibpy.Topic] = {}

        self._running = False
        self._connected = False

    # =========================================================
    # CONNECTION
    # =========================================================

    def connect(self) -> None:
        """
        Start the rosbridge connection.

        IMPORTANT:
        roslibpy.run() is non-blocking, so it is safe to call
        from the PyQt main thread.
        """

        if self._running:
            print(
                "[ROSBRIDGE] Connection already running."
            )
            return

        self._running = True

        print(
            f"[ROSBRIDGE] Connecting to "
            f"ws://{self.host}:{self.port}..."
        )

        try:

            # Create ONE Ros connection.
            self._ros = roslibpy.Ros(
                host=self.host,
                port=self.port,
            )

            # Connection established callback.
            self._ros.on_ready(
                self._handle_connected
            )

            # Connection closed callback.
            self._ros.on(
                "close",
                self._handle_disconnected
            )

            # IMPORTANT:
            # run() is non-blocking.
            self._ros.run()

        except Exception as e:

            self._running = False

            print(
                f"[ROSBRIDGE] Connection error: {e}"
            )

    def _handle_connected(self) -> None:
        """Called when rosbridge connection is ready."""

        if not self._running:
            return

        if self._connected:
            return

        self._connected = True

        print(
            f"[ROSBRIDGE] Successfully connected to "
            f"ws://{self.host}:{self.port}"
        )

        if self._on_connected:
            self._on_connected()

    def _handle_disconnected(self, *args) -> None:
        """
        Called when the WebSocket connection closes.

        We do NOT manually create another Ros object.
        roslibpy handles reconnection.
        """

        if not self._connected:
            return

        self._connected = False

        print(
            "[ROSBRIDGE] Rosbridge connection lost."
        )

        if self._on_disconnected:
            self._on_disconnected()

    # =========================================================
    # DISCONNECT
    # =========================================================

    def disconnect(self) -> None:
        """Cleanly close the rosbridge connection."""

        if not self._running:
            return

        print(
            "[ROSBRIDGE] Disconnecting..."
        )

        self._running = False
        self._connected = False

        try:

            if self._ros is not None:
                self._ros.terminate()

        except Exception as e:

            print(
                f"[ROSBRIDGE] Disconnect error: {e}"
            )

        self._ros = None
        self._topics.clear()

        print(
            "[ROSBRIDGE] Disconnected cleanly."
        )

    # =========================================================
    # STATUS
    # =========================================================

    @property
    def is_connected(self) -> bool:
        """Return True if rosbridge is currently connected."""

        return (
            self._connected
            and self._ros is not None
            and self._ros.is_connected
        )

    # =========================================================
    # PUBLISHER
    # =========================================================

    def create_publisher(
        self,
        topic_name: str,
        message_type: str,
    ) -> roslibpy.Topic:

        if not self.is_connected:

            raise RuntimeError(
                "Cannot create publisher: "
                "rosbridge is not connected."
            )

        # Return existing publisher.
        if topic_name in self._topics:
            return self._topics[topic_name]

        topic = roslibpy.Topic(
            self._ros,
            topic_name,
            message_type,
            reconnect_on_close=True,
        )

        topic.advertise()

        self._topics[topic_name] = topic

        print(
            f"[ROSBRIDGE] Publisher advertised: "
            f"{topic_name} [{message_type}]"
        )

        return topic

    # =========================================================
    # PUBLISH
    # =========================================================

    def publish(
        self,
        topic_name: str,
        message_type: str,
        message: dict,
    ) -> bool:
        """Publish a ROS message through rosbridge."""

        if not self.is_connected:

            print(
                f"[ROSBRIDGE] Cannot publish "
                f"{topic_name}: not connected."
            )

            return False

        try:

            topic = self.create_publisher(
                topic_name,
                message_type,
            )

            topic.publish(
                roslibpy.Message(message)
            )

            return True

        except Exception as e:

            print(
                f"[ROSBRIDGE] Publish error on "
                f"{topic_name}: {e}"
            )

            return False

    # =========================================================
    # SUBSCRIBER
    # =========================================================

    def subscribe(
        self,
        topic_name: str,
        message_type: str,
        callback: Callable[[dict], None],
    ) -> Optional[roslibpy.Topic]:
        """
        Subscribe to a ROS topic through rosbridge.

        The received ROS message is passed to callback as
        a normal Python dictionary.
        """

        if not self.is_connected:
            print(
                f"[ROSBRIDGE] Cannot subscribe to "
                f"{topic_name}: not connected."
            )
            return None

        # Return existing subscriber if already tracking
        if topic_name in self._topics:
            return self._topics[topic_name]

        try:
            topic = roslibpy.Topic(
                self._ros,
                topic_name,
                message_type,
                reconnect_on_close=True,
            )

            topic.subscribe(callback)

            self._topics[topic_name] = topic

            print(
                f"[ROSBRIDGE] Subscriber created: "
                f"{topic_name} [{message_type}]"
            )

            return topic

        except Exception as e:
            print(
                f"[ROSBRIDGE] Subscribe error on "
                f"{topic_name}: {e}"
            )
            return None
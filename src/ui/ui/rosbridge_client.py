"""
rosbridge_client.py
-------------------
Windows-side ROS 2 communication through rosbridge_websocket.

Uses roslibpy with the Twisted reactor running in a background
thread without installing OS signal handlers.
"""

import threading
from typing import Optional, Callable, Dict

import roslibpy
from twisted.internet import reactor


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

        self._ros: Optional[roslibpy.Ros] = None

        self._thread: Optional[threading.Thread] = None

        self._topics: Dict[str, roslibpy.Topic] = {}

        self._running = False
        self._connected = False

        self._lock = threading.Lock()

    # =========================================================
    # CONNECTION
    # =========================================================

    def connect(self) -> None:

        if self._running:
            print(
                "[ROSBRIDGE] Connection manager "
                "already running."
            )
            return

        self._running = True

        print(
            f"[ROSBRIDGE] Connecting to "
            f"ws://{self.host}:{self.port}..."
        )

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="RosbridgeThread",
        )

        self._thread.start()

    def _run(self) -> None:
        """
        Create the Ros object and run Twisted without signal
        handlers because this is NOT the Python main thread.
        """

        try:

            ros = roslibpy.Ros(
                host=self.host,
                port=self.port,
            )

            with self._lock:
                self._ros = ros

            ros.on_ready(
                self._handle_connected
            )

            # -------------------------------------------------
            # IMPORTANT
            #
            # Do NOT use:
            #
            #     ros.run()
            #
            # because that attempts to install signal handlers.
            #
            # Instead, run Twisted's reactor directly and disable
            # signal handlers.
            # -------------------------------------------------

            reactor.callWhenRunning(
                self._start_ros_connection
            )

            reactor.run(
                installSignalHandlers=False
            )

        except Exception as e:

            if self._running:

                print(
                    f"[ROSBRIDGE] Connection error: {e}"
                )

        finally:

            if self._connected:

                self._connected = False

                if self._on_disconnected:
                    self._on_disconnected()

    def _start_ros_connection(self) -> None:
        """
        Start the roslibpy connection after the Twisted reactor
        has started.
        """

        try:

            if self._ros is not None:

                # roslibpy's internal connection setup
                self._ros._run()

        except Exception as e:

            print(
                f"[ROSBRIDGE] ROS startup error: {e}"
            )

    def _handle_connected(self) -> None:

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

    # =========================================================
    # DISCONNECT
    # =========================================================

    def disconnect(self) -> None:

        if not self._running:
            return

        print(
            "[ROSBRIDGE] Disconnecting..."
        )

        self._running = False

        try:

            if self._ros is not None:

                self._ros.terminate()

        except Exception as e:

            print(
                f"[ROSBRIDGE] Disconnect error: {e}"
            )

        try:

            if reactor.running:
                reactor.callFromThread(
                    reactor.stop
                )

        except Exception as e:

            print(
                f"[ROSBRIDGE] Reactor stop error: {e}"
            )

        if (
            self._thread is not None
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):

            self._thread.join(
                timeout=2.0
            )

        self._thread = None

        self._connected = False

        print(
            "[ROSBRIDGE] Disconnected cleanly."
        )

    # =========================================================
    # STATUS
    # =========================================================

    @property
    def is_connected(self) -> bool:

        with self._lock:
            ros = self._ros

        return (
            self._connected
            and ros is not None
            and ros.is_connected
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

        if topic_name in self._topics:

            return self._topics[
                topic_name
            ]

        with self._lock:
            ros = self._ros

        if ros is None:

            raise RuntimeError(
                "ROS connection is unavailable."
            )

        topic = roslibpy.Topic(
            ros,
            topic_name,
            message_type,
            reconnect_on_close=True,
        )

        topic.advertise()

        self._topics[
            topic_name
        ] = topic

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
                f"[ROSBRIDGE] Publish error "
                f"on {topic_name}: {e}"
            )

            return False
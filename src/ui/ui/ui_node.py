"""
ui_node.py
-----------
Application entry point for the AMR dashboard UI on Windows.
Manages WebSocket ROS communication via rosbridge and Raspberry Pi SSH remote lifecycles.
"""

import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QInputDialog

from .rosbridge_client import RosbridgeClient
from .main_window import MainWindow
from .controllers.manual_controller import ManualController
from .controllers.robot_status_controller import RobotStatusController
from .controllers.map_controller import MapController
from .controllers.slam_controller import SlamController
from .controllers.navigation_controller import NavigationController
from .controllers.mission_log_controller import MissionLogController
from .config import settings

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
STYLESHEET_PATH = RESOURCES_DIR / "style.qss"


class UINode:
    def __init__(self) -> None:
        print("\n=== [DEBUG UINODE] INITIALIZING WINDOWS AMR DASHBOARD ===")

        self._current_operation_mode: str = "IDLE"

        # 1. State Machine Controllers
        self._mission_log_controller = MissionLogController()
        self._manual_controller = ManualController(publish_callback=self.publish_cmd_vel)
        self._robot_status_controller = RobotStatusController(mission_log_controller=self._mission_log_controller)
        self._map_controller = MapController()
        self._slam_controller = SlamController(mission_log_controller=self._mission_log_controller)
        self._navigation_controller = NavigationController(mission_log_controller=self._mission_log_controller)

        # 2. WebSocket Interface to Raspberry Pi
        self._rosbridge = RosbridgeClient(
            host=settings.PI_IP,
            port=settings.ROSBRIDGE_PORT,
            on_connected=self._on_rosbridge_connected,
            on_disconnected=self._on_rosbridge_disconnected,
        )
        self._rosbridge.connect()

        # 3. Bind Signal Routing Actions
        self._slam_controller.start_requested.connect(self.handle_slam_start)
        self._slam_controller.stop_requested.connect(self.handle_slam_stop)
        self._slam_controller.save_requested.connect(self.handle_slam_save)

        self._navigation_controller.toggle_requested.connect(self._on_navigation_toggle_triggered)
        self._navigation_controller.initial_pose_published.connect(self.publish_initial_pose_msg)
        self._navigation_controller.goal_pose_published.connect(self.send_navigation_action_goal)
        self._navigation_controller.abort_requested.connect(self.handle_navigation_abort)

        self.window = None
        self._mission_log_controller.log_info("Dashboard standing by.")
        print("=== [DEBUG UINODE] CORE WORKSPACE INITIALIZED ===\n")

    def _on_rosbridge_connected(self) -> None:
        self._mission_log_controller.log_success("Connected to Robot Bridge.")
        print("[DEBUG UINODE] Rosbridge connection confirmed.")

    def _on_rosbridge_disconnected(self) -> None:
        self._mission_log_controller.log_error("Lost connection to Robot Bridge.")
        print("[DEBUG UINODE] Rosbridge disconnected.")

    def init_ui(self) -> None:
        self.window = MainWindow(
            manual_controller=self._manual_controller,
            robot_status_controller=self._robot_status_controller,
            map_controller=self._map_controller,
            slam_controller=self._slam_controller,
            navigation_controller=self._navigation_controller,
            mission_log_controller=self._mission_log_controller,
        )
        self.window.show()

    # --- Mode Transitions ---
    def request_mode_transition(self, target_mode: str) -> bool:
        if target_mode == self._current_operation_mode:
            return True
        print(f"[DEBUG UINODE] Transition: {self._current_operation_mode} -> {target_mode}")

        if target_mode == "SLAM":
            self._slam_controller.update_execution_state(running=False, busy=False, locked=False)
            self._navigation_controller.update_execution_state(running=False, busy=False, locked=True)
        elif target_mode == "NAVIGATION":
            self._slam_controller.update_execution_state(running=False, busy=False, locked=True)
            self._navigation_controller.update_execution_state(running=False, busy=False, locked=False)
        elif target_mode == "IDLE":
            self._slam_controller.update_execution_state(running=False, busy=False, locked=False)
            self._navigation_controller.update_execution_state(running=False, busy=False, locked=False)

        self._current_operation_mode = target_mode
        return True

    # --- Velocity Command Publisher (Task 1 Focus) ---
    def publish_cmd_vel(self, linear: float, angular: float) -> None:
        message = {
            "linear": {"x": float(linear), "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": float(angular)},
        }
        
        success = self._rosbridge.publish(
            topic_name=settings.CMD_VEL_TOPIC,
            message_type="geometry_msgs/Twist",
            message=message,
        )

        if success:
            print(f"[DEBUG CMD_VEL] linear={linear:.2f} | angular={angular:.2f}")

    # --- Placeholders for Subsequent Tasks ---
    def publish_initial_pose_msg(self, x: float, y: float, yaw: float) -> None:
        print(f"[DEBUG UINODE] /initialpose requested: ({x}, {y}, yaw={yaw}) - (Will wire in Task 2/3)")

    def send_navigation_action_goal(self, x: float, y: float, yaw: float) -> None:
        print(f"[DEBUG UINODE] Nav goal dispatched: ({x}, {y}, yaw={yaw}) - (Will wire in Task 4)")

    def handle_navigation_abort(self) -> None:
        print("[DEBUG UINODE] Navigation abort triggered.")

    # --- SLAM SSH Lifecycles ---
    def handle_slam_start(self) -> None:
        self.request_mode_transition("SLAM")
        print("[DEBUG UINODE] Executing Remote SLAM Start via SSH on Raspberry Pi...")
        try:
            subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", "~/scripts/start_slam.sh"],
                check=True,
            )
            self._slam_controller.update_execution_state(running=True, busy=False)
        except Exception:
            self._mission_log_controller.log_error("Unable to start mapping.")
            self.request_mode_transition("IDLE")

    def handle_slam_stop(self) -> None:
        print("[DEBUG UINODE] Stopping Remote SLAM via SSH on Raspberry Pi...")
        try:
            subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", "~/scripts/stop_slam.sh"],
                check=True,
            )
        except Exception:
            self._mission_log_controller.log_error("Unable to stop mapping.")

        self._map_controller.clear_map()
        self.request_mode_transition("IDLE")

    def handle_slam_save(self, filename: str) -> None:
        print(f"[DEBUG UINODE] Executing Remote Map Save via SSH for '{filename}'...")
        try:
            subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", f"~/scripts/save_map.sh {filename}"],
                check=True,
            )
            self._mission_log_controller.log_success(f"Map '{filename}' saved successfully.")
        except Exception:
            self._mission_log_controller.log_error("Unable to save map.")

        self._slam_controller.update_execution_state(running=True, busy=False)

    # --- Navigation SSH Lifecycles ---
    def _on_navigation_toggle_triggered(self, checked: bool, map_path: str) -> None:
        if checked:
            self.handle_navigation_start(map_path)
        else:
            self.handle_navigation_stop()

    def handle_navigation_start(self, map_path: str) -> None:
        self.request_mode_transition("NAVIGATION")
        print("[DEBUG UINODE] Querying Raspberry Pi via SSH for available maps...")
        try:
            result = subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", "~/scripts/start_nav.sh"],
                capture_output=True,
                text=True,
                check=True,
            )
            maps = sorted([m.strip() for m in result.stdout.splitlines() if m.strip()])

            if not maps:
                self._mission_log_controller.log_error("Failed to load map: Catalog empty.")
                self._navigation_controller.update_execution_state(running=False, busy=False)
                self.request_mode_transition("IDLE")
                return

            selected_map, ok = QInputDialog.getItem(
                self.window,
                "Select Map",
                "Available Workspace Maps:",
                maps,
                0,
                False,
            )

            if not ok or not selected_map:
                self._navigation_controller.update_execution_state(running=False, busy=False)
                self.request_mode_transition("IDLE")
                return

            subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", f"~/scripts/start_nav.sh {selected_map}"],
                check=True,
            )
            self._navigation_controller.update_execution_state(running=True, busy=False)
            self._mission_log_controller.log_success(f"Map '{selected_map}' loaded.")
        except Exception as e:
            print(f"[ERROR UINODE] handle_navigation_start: {e}")
            self._navigation_controller.update_execution_state(running=False, busy=False)
            self._mission_log_controller.log_error("Failed to load map.")
            self.request_mode_transition("IDLE")

    def handle_navigation_stop(self) -> None:
        print("[DEBUG UINODE] Stopping Remote Navigation via SSH on Raspberry Pi...")
        try:
            subprocess.run(
                ["ssh", f"{settings.PI_USER}@{settings.PI_IP}", "~/scripts/stop_nav.sh"],
                check=True,
            )
        except Exception:
            self._mission_log_controller.log_error("Unable to stop navigation.")

        self._map_controller.clear_map()
        self._navigation_controller.set_global_plan([])
        self._navigation_controller.request_mission_abort()
        self.request_mode_transition("IDLE")

    def shutdown(self) -> None:
        """Ensures safe robot stop and socket cleanup before exiting."""
        print("[DEBUG UINODE] Shutting down Windows dashboard...")
        try:
            self.publish_cmd_vel(0.0, 0.0)
        except Exception:
            pass

        try:
            self._rosbridge.disconnect()
        except Exception:
            pass


def load_stylesheet(app: QApplication) -> None:
    if STYLESHEET_PATH.exists():
        style_data = STYLESHEET_PATH.read_text(encoding="utf-8")
        resolved_icons_dir = str(RESOURCES_DIR).replace("\\", "/")
        style_data = style_data.replace("{{ICONS_DIR}}", resolved_icons_dir)
        app.setStyleSheet(style_data)


def main() -> None:
    app = QApplication(sys.argv)
    load_stylesheet(app)

    ui_node = UINode()
    ui_node.init_ui()

    exit_code = app.exec()
    ui_node.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
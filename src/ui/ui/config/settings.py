"""
settings.py
------------
Centralized configuration settings for the Windows AMR Dashboard.
"""

# =========================
# Robot Motion Parameters
# =========================
DEFAULT_LINEAR_SPEED = 0.45
DEFAULT_ANGULAR_SPEED = 1.0

MAX_LINEAR_SPEED = 2.0
MIN_LINEAR_SPEED = 0.0

MAX_ANGULAR_SPEED = 3.14
MIN_ANGULAR_SPEED = 0.0

LINEAR_SPEED_STEP = 0.05
ANGULAR_SPEED_STEP = 0.1

# =========================
# ROS Topics (Explicit paths for rosbridge)
# =========================
CMD_VEL_TOPIC = "/cmd_vel"
ODOM_TOPIC = "/odom"
MAP_TOPIC = "/map"
INITIAL_POSE_TOPIC = "/initialpose"
GOAL_POSE_TOPIC = "/goal_pose"
GLOBAL_PLAN_TOPIC = "/plan"

NAV2_ACTION_SERVER = "navigate_to_pose"

# =========================
# Raspberry Pi Connection
# =========================
PI_USER = "nova"
PI_IP = "10.13.18.79"
ROSBRIDGE_PORT = 9090

# Remote launch scripts on Pi
SSH_START_SLAM = f"{PI_USER}@{PI_IP} ~/scripts/start_slam.sh"
SSH_STOP_SLAM = f"{PI_USER}@{PI_IP} ~/scripts/stop_slam.sh"
SSH_SAVE_MAP = f"{PI_USER}@{PI_IP} ~/scripts/save_map.sh"
SSH_START_NAV = f"{PI_USER}@{PI_IP} ~/scripts/start_nav.sh"
SSH_STOP_NAV = f"{PI_USER}@{PI_IP} ~/scripts/stop_nav.sh"
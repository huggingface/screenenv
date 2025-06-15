#!/usr/bin/python3
import os
import pwd
import socket
import sys


def init_dbus_socket():
    socket_path = "/run/dbus/system_bus_socket"
    socket_dir = os.path.dirname(socket_path)

    print(f"Initializing dbus socket at {socket_path}")

    # Create directory if it doesn't exist
    if not os.path.exists(socket_dir):
        print(f"Creating directory {socket_dir}")
        os.makedirs(socket_dir, exist_ok=True)

    # Set directory permissions
    print(f"Setting directory permissions for {socket_dir}")
    os.chmod(socket_dir, 0o777)  # Full access for all users

    # Get user and group IDs
    try:
        user_info = pwd.getpwnam("user")
        uid = user_info.pw_uid
        gid = user_info.pw_gid
        print(f"Found user 'user' with uid={uid}, gid={gid}")
    except KeyError:
        print("Warning: Could not find user 'user'")
        uid = os.getuid()
        gid = os.getgid()
        print(f"Using current user uid={uid}, gid={gid}")

    # Set directory ownership
    print(f"Setting directory ownership to uid={uid}, gid={gid}")
    os.chown(socket_dir, uid, gid)

    # Remove existing socket if it exists
    if os.path.exists(socket_path):
        print(f"Removing existing socket at {socket_path}")
        try:
            os.unlink(socket_path)
        except OSError as e:
            print(f"Error removing existing socket: {e}", file=sys.stderr)
            return False

    try:
        # Create and bind socket
        print("Creating new socket")
        s = socket.socket(socket.AF_UNIX)
        s.bind(socket_path)

        # Set socket permissions
        print("Setting socket permissions")
        os.chmod(socket_path, 0o666)  # Read/write for all users
        os.chown(socket_path, uid, gid)

        s.close()
        print(f"Successfully created dbus socket at {socket_path}")

        # Verify socket exists and has correct permissions
        if os.path.exists(socket_path):
            stat = os.stat(socket_path)
            print(f"Socket permissions: {oct(stat.st_mode)}")
            print(f"Socket ownership: uid={stat.st_uid}, gid={stat.st_gid}")

        return True
    except Exception as e:
        print(f"Error creating socket: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = init_dbus_socket()
    sys.exit(0 if success else 1)

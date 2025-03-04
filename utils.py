import os
import platform

def get_default_chrome_user_data_dir():
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
    elif system == "Linux":
        return os.path.expanduser("~/.config/google-chrome")
    elif system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    return None
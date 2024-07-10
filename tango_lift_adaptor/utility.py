from config_parser import config_data


__all__ = ['get_door_status']


def get_door_status(door_state):
    if door_state in [0, 1, 3]:
        result = "close"
    elif door_state in [2]:
        result = "open"
    else:
        result = "None"
    return result

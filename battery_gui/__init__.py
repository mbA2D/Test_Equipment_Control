"""Reusable Qt widgets for the battery-test application."""

from importlib import import_module

__all__ = [
    "ChannelWidget",
    "EquipmentAssignmentWidget",
    "EquipmentConnectionWidget",
    "ConnectedEquipmentWidget",
    "ProfileEditorWidget",
]

_EXPORTS = {
    name: (module, name)
    for name, module in {
        "ChannelWidget": ".channel_widget",
        "EquipmentAssignmentWidget": ".equipment_assignment",
        "EquipmentConnectionWidget": ".equipment_connection",
        "ConnectedEquipmentWidget": ".equipment_connection",
        "ProfileEditorWidget": ".profile_editor",
    }.items()
}


def __getattr__(name):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value

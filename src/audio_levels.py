"""Volume controls with more usable travel at quiet listening levels."""


def volume_gain(percent):
    """Map the displayed percentage to a smooth square-law amplitude taper."""
    position = max(0, min(100, float(percent))) / 100
    return position * position


def music_volume_gain(app):
    """Interface sounds scale with the music volume, on top of their own settings."""
    value = app.property('musicVolume') if app is not None else None
    return 1.0 if value is None else volume_gain(value)

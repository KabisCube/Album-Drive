"""Volume controls with more usable travel at quiet listening levels."""


def volume_gain(percent):
    """Map the displayed percentage to a smooth square-law amplitude taper."""
    position = max(0, min(100, float(percent))) / 100
    return position * position

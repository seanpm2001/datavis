from PyQt5.QtCore import Qt

PIXEL_UNITS = 1
PERCENT_UNITS = 2

# view types
COLUMNS = 1
GALLERY = 2
ITEMS = 4
SLICES = 8

# axis positions
AXIS_TOP_LEFT = 0  # axis in top-left
AXIS_TOP_RIGHT = 1  # axis in top-right
AXIS_BOTTOM_RIGHT = 2  # axis in bottom-right
AXIS_BOTTOM_LEFT = 3  # axis in bottom-left

# view data
NAME = 1
CLASS = 2
ICON = 3
ACTION = 4
VIEW = 5
TOOLTIP = 6
TABLE_CONFIG = 7

# tool tip keys
VISIBLE_CHECKED = 7
VISIBLE_UNCHECKED = 8
RENDER_CHECKED = 9
RENDER_UNCHECKED = 10

# Data roles for QtModels
DATA_ROLE = Qt.UserRole + 2
LABEL_ROLE = Qt.UserRole + 3

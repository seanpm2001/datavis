

from PyQt5.QtWidgets import (QWidget, QGridLayout)
from PyQt5.QtCore import QSize, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QPalette, QPainter, QPainterPath, QPen, QColor

from emqt5.models import AXIS_X, AXIS_Y, AXIS_Z

from ._slices_view import SlicesView


class MultiSliceView(QWidget):
    """
    This view is currently used for displaying 3D volumes and it is composed
    by 3 SlicerViews and a custom 2D plot showing the axis and the slider
    position. This view is the default for Volumes.
    """
    valueChanged = pyqtSignal(int, int)

    def __init__(self, parent, slicesKwargs):
        """
        parent: Parent QWidget
        slicesKwargs: a dict with keys of axis () and values f the model
            for each axis.
        """
        QWidget.__init__(self, parent=parent)
        self._slicesKwargs = slicesKwargs
        self._slicesDict = {}
        self._axis = -1
        self._slice = -1
        self.__setupUi()

    def __setupUi(self):
        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        slicesInfo = {
            AXIS_X: ('X Axis (side)', [1, 1], self._onSliceXChanged),
            AXIS_Y: ('Y Axis (top)', [0, 0], self._onSliceYChanged),
            AXIS_Z: ('Z Axis (front)', [1, 0], self._onAxisZChanged)
        }

        # Build one SlicesView for each axis, taking into account the
        # input parameters and some reasonable default values
        for axis, args in self._slicesKwargs.iteritems():
            text, pos, slot = slicesInfo[axis]
            model = args['model']
            _, _, n = model.getDim()
            sv = SlicesView(self, model, text=args.get('text', text),
                            currentValue=args.get('currentValue', n/2),
                            imageViewKwargs={'histogram': False,
                                             'toolBar': False
                                             })
            sv.valueChanged.connect(slot)
            layout.addWidget(sv, *pos)
            self._slicesDict[axis] = sv

        self._renderArea = RenderArea(self)
        layout.addWidget(self._renderArea, 0, 1)

    def _onSliceChanged(self, axis, value):
        """ Called when the slice index is changed in one of the axis. """
        self._axis = axis
        self._slice = value
        nMax = float(self._slicesDict[axis].getRange()[1])
        # Convert to 40 scale index that is required by the RenderArea
        renderAreaShift = int(40 * (1 - value / nMax))
        self._renderArea.setShift(axis, renderAreaShift)
        self.valueChanged.emit(axis, value)

    @pyqtSlot(int)
    def _onSliceYChanged(self, value):
        self._onSliceChanged(AXIS_Y, value)

    @pyqtSlot(int)
    def _onAxisZChanged(self, value):
        self._onSliceChanged(AXIS_Z, value)

    @pyqtSlot(int)
    def _onSliceXChanged(self, value):
        self._onSliceChanged(AXIS_X, value)

    def getValue(self, axis=None):
        """ Return the current slice index for a given axis.
         (If none, the last changed axis is be used) """
        return self._slicesDict[axis or self._axis].getValue()

    def setValue(self, value, axis=None):
        """ Sets the slice value for the given axis.
        (If axis is None the last modified axis is used) """
        self._slicesDict[axis or self._axis].setValue(axis)


class RenderArea(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._shiftx = 0
        self._widthx = 40
        self._shifty = 0
        self._widthy = 40
        self._shiftz = 0
        self._widthz = 20
        self._boxaxis = AXIS_Z
        self._oldPosX = 60

        self.setBackgroundRole(QPalette.Base)

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(w / 3 + 20, h / 2)
        scale = w if w < h else h
        painter.scale(scale / 100.0, scale / 100.0)
        ox = 0
        oy = 0
        wx = self._widthx
        wy = self._widthy
        wz = self._widthz

        # Draw Y axis
        ty = oy - wy
        painter.setPen(QColor(200, 0, 0))
        painter.drawLine(ox, oy, ox, ty)
        painter.drawLine(ox, ty, ox - 1, ty + 1)
        painter.drawLine(ox, ty, ox + 1, ty + 1)
        painter.drawLine(ox + 1, ty + 1, ox - 1, ty + 1)

        # Draw X axis
        tx = ox + wx
        painter.setPen(QColor(0, 0, 200))
        painter.drawLine(ox, oy, tx, oy)
        painter.drawLine(tx - 1, oy + 1, tx, oy)
        painter.drawLine(tx - 1, oy - 1, tx, oy)
        painter.drawLine(tx - 1, oy + 1, tx - 1, oy - 1)

        # Draw Z axis
        painter.setPen(QColor(0, 200, 0))
        tzx = ox - wz
        tzy = oy + wz
        painter.drawLine(ox, oy, tzx, tzy)
        painter.drawLine(tzx, tzy - 1, tzx, tzy)
        painter.drawLine(tzx + 1, tzy, tzx, tzy)
        painter.drawLine(tzx + 1, tzy, tzx, tzy - 1)
        # painter.drawPath(self.path)

        # Draw labels
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(tx - 5, oy + 15, "x")
        painter.drawText(ox - 15, ty + 15, "y")
        painter.drawText(tzx + 5, tzy + 10, "z")

        painter.setPen(QPen(QColor(50, 50, 50), 0.3))
        painter.setBrush(QColor(220, 220, 220, 100))
        rectPath = QPainterPath()

        self.size = float(self._widthx)
        bw = 30
        bwz = float(wz) / wx * bw

        if self._boxaxis == AXIS_Z:
            shiftz = float(self._widthz) / self.size * self._shiftz
            box = ox - shiftz
            boy = oy + shiftz
            rectPath.moveTo(box, boy)
            rectPath.lineTo(box, boy - bw)
            rectPath.lineTo(box + bw, boy - bw)
            rectPath.lineTo(box + bw, boy)

        elif self._boxaxis == AXIS_Y:
            shifty = float(self._widthy) / self.size * self._shifty
            box = ox
            boy = oy - shifty
            rectPath.moveTo(box, boy)
            rectPath.lineTo(box + bw, boy)
            rectPath.lineTo(box + bw - bwz, boy + bwz)
            rectPath.lineTo(box - bwz, boy + bwz)

        elif self._boxaxis == AXIS_X:
            shiftx = float(self._widthx) / self.size * self._shiftx
            box = ox + shiftx
            boy = oy
            rectPath.moveTo(box, boy)
            rectPath.lineTo(box, boy - bw)
            rectPath.lineTo(box - bwz, boy - bw + bwz)
            rectPath.lineTo(box - bwz, boy + bwz)

        rectPath.closeSubpath()
        painter.drawPath(rectPath)

    def setShift(self, axis, value):
        if axis == AXIS_X:
            self._shiftx = value
        elif axis == AXIS_Y:
            self._shifty = value
        elif axis == AXIS_Z:
            self._shiftz = value

        self._boxaxis = axis
        self.update()

    def minimumSizeHint(self):
        return QSize(30, 30)

    def sizeHint(self):
        return QSize(80, 80)


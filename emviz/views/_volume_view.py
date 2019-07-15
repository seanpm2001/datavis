#!/usr/bin/python
# -*- coding: utf-8 -*-


from PyQt5.QtCore import Qt, pyqtSlot, QSize
import PyQt5.QtWidgets as qtw
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from emviz.widgets import PageBar, TriggerAction, ZoomSpinBox, PagingInfo
from emviz.models import (AXIS_X, AXIS_Y, AXIS_Z, EmptySlicesModel,
                          EmptyTableModel, EmptyVolumeModel, SlicesTableModel)
from ._multislice_view import MultiSliceView
from ._gallery import GalleryView
from ._constants import PIXEL_UNITS, GALLERY, SLICES


class VolumeView(qtw.QWidget):
    """
    Allow to display a volume and switch between MultiSlicesView​and GalleryView
    In case of multiple volumes, this view could be extended with a way
    to select which volume to display.
    """
    def __init__(self, parent, **kwargs):
        """
        :param parent:  (QWidget) Parent widget
        :param kwargs:
           model:          (VolumeModel) The model
           cellSize:       (int) The default cell size
           maxCellSize:    (int) The maximum value for cell size
           minCellSize:    (int) The minimum value for cell size
           zoomUnits:      (int) The zoom type for GalleryView cells:
                           PIXEL_UNITS or PERCENT_UNITS
           galleryKwargs:  (dict) The GalleryView configuration params.
                           See the GalleryView documentation.
           slicesKwargs:   (dict) The MultiSliceView configuration params.
                           See the MultiSliceView documentation.
        """
        qtw.QWidget.__init__(self, parent=parent)
        self._defaultCellSize = kwargs.get("cellSize", 120)
        self._maxCellSize = kwargs.get("maxCellSize", 300)
        self._minCellSize = kwargs.get("minCellSize", 20)
        self._zoomUnits = kwargs.get("zoomUnits", PIXEL_UNITS)
        self._view = None
        self.__setupGUI(kwargs.get('slicesKwargs', dict()),
                        kwargs.get('galleryKwargs', dict()))
        self.setModel(kwargs['model'])
        self.setView(kwargs.get('view', 2))
        self._onChangeCellSize(self._defaultCellSize)

    def __setupGUI(self, slicesKwargs, galleryKwargs):
        self._mainLayout = qtw.QVBoxLayout(self)
        self._mainLayout.setSpacing(0)
        self._mainLayout.setContentsMargins(1, 1, 1, 1)
        self._toolBar = qtw.QToolBar(self)
        self._mainLayout.addWidget(self._toolBar)
        self._stackedLayoud = qtw.QStackedLayout(self._mainLayout)
        self._stackedLayoud.setSpacing(0)
        # actions
        self._actionGroupViews = qtw.QActionGroup(self._toolBar)
        self._actionGroupViews.setExclusive(True)

        self._aSlices = TriggerAction(parent=self._toolBar,
                                      actionName='Multi Slices View',
                                      text='Multi Slices View',
                                      faIconName='fa.sliders',
                                      checkable=True,
                                      slot=self._onMultiSlicesViewTriggered)
        self._actionGroupViews.addAction(self._aSlices)
        self._toolBar.addAction(self._aSlices)
        self._aSlices.setChecked(True)
        self._aGallery = TriggerAction(parent=self._toolBar,
                                       actionName='Gallery View',
                                       text='Gallery View', faIconName='fa.th',
                                       checkable=True,
                                       slot=self._onGalleryViewTriggered)
        self._actionGroupViews.addAction(self._aGallery)
        self._toolBar.addAction(self._aGallery)
        self._toolBar.addSeparator()
        # cell size
        zoomSpin = ZoomSpinBox(self._toolBar, valueType=int,
                               minValue=self._minCellSize,
                               maxValue=self._maxCellSize,
                               currentValue=self._defaultCellSize)
        zoomSpin.sigValueChanged[int].connect(self._onChangeCellSize)

        self._actZoomSpin = self._toolBar.addWidget(zoomSpin)
        # self._toolBar.addSeparator()
        # for axis selection in GalleryView
        self._labelCurrentVolume = qtw.QLabel(parent=self._toolBar,
                                              text=" Axis ")
        self._actLabelCurentVolume = self._toolBar.addWidget(
            self._labelCurrentVolume)
        self._comboBoxCurrentAxis = qtw.QComboBox(self._toolBar)
        self._comboBoxCurrentAxis.currentIndexChanged.connect(
            self._onAxisChanged)
        self._actComboboxCurrentAxis = self._toolBar.addWidget(
            self._comboBoxCurrentAxis)
        # self._toolBar.addSeparator()
        # for multiple volumes
        self._pagingInfo = PagingInfo(1, 1)
        self._pageBar = PageBar(parent=self._toolBar,
                                pagingInfo=self._pagingInfo)
        self._pageBar.setMaximumWidth(150)
        self._actPageBar = self._toolBar.addWidget(self._pageBar)
        self._pageBar.sigPageChanged.connect(self._onVolumeChanged)
        # FIXME [phv] Hide until review the volume stacks
        self._actPageBar.setVisible(False)

        # views
        model = EmptySlicesModel()
        slicesKwargs[AXIS_X] = {'model': model}
        slicesKwargs[AXIS_Y] = {'model': model}
        slicesKwargs[AXIS_Z] = {'model': model}
        self._multiSlicesView = MultiSliceView(self, slicesKwargs)
        self._multiSlicesView.sigAxisChanged.connect(self.__updateAxis)
        self._stackedLayoud.addWidget(self._multiSlicesView)
        model = EmptyTableModel()
        self._galleryView = GalleryView(parent=self, model=model,
                                        **galleryKwargs)

        self._galleryView.sigCurrentRowChanged.connect(
            self._onGalleryRowChanged)
        self._stackedLayoud.addWidget(self._galleryView)

    def __setupComboBoxAxis(self):
        """
        Configure the elements in combobox currentVolume for user selection.
        """
        self._comboBoxCurrentAxis.blockSignals(True)
        model = self._comboBoxCurrentAxis.model()
        if not model:
            model = QStandardItemModel(self._comboBoxCurrentVolume)

        model.clear()

        for axis in [AXIS_X, AXIS_Y, AXIS_Z]:
            item = QStandardItem(self._multiSlicesView.getText(axis))
            item.setData(axis, Qt.UserRole)  # use UserRole for store
            model.appendRow([item])

        self._comboBoxCurrentAxis.blockSignals(False)

    def __setupToolBar(self):
        """ Configure the toolbar according to the current view """
        v = self._view == GALLERY
        self._actComboboxCurrentAxis.setVisible(v)
        self._actZoomSpin.setVisible(v)
        self._actLabelCurentVolume.setVisible(v)

    @pyqtSlot(int)
    def __updateAxis(self, axis):
        """
        Update the widget used to show the axis
        :param axis: (int) The axis (AXIS_X, AXIS_Y or AXIS_Z)
        """
        self._comboBoxCurrentAxis.blockSignals(True)
        self._comboBoxCurrentAxis.setCurrentIndex(
            [AXIS_X, AXIS_Y, AXIS_Z].index(axis))
        self._comboBoxCurrentAxis.blockSignals(False)

    @pyqtSlot(int)
    def _onChangeCellSize(self, size):
        """
        This slot is invoked when the cell size need to be rearranged
        """
        self._galleryView.setIconSize(QSize(size, size))

    @pyqtSlot(bool)
    def _onMultiSlicesViewTriggered(self, checked):
        """ Triggered function for multislices view action """
        if checked:
            self._stackedLayoud.setCurrentWidget(self._multiSlicesView)
            self._view = SLICES
        self._aGallery.setChecked(not checked)
        self.__setupToolBar()

    @pyqtSlot(int)
    def _onGalleryRowChanged(self, row):
        """ Invoked when change the current gallery row """
        axis = self._comboBoxCurrentAxis.currentData(Qt.UserRole)
        self._multiSlicesView.setValue(row + 1, axis)

    @pyqtSlot(bool)
    def _onGalleryViewTriggered(self, checked):
        """ Triggered function for gallery view action """
        if checked:
            self._view = GALLERY
            axis = self._multiSlicesView.getAxis()
            model = self._slicesTableModels[axis]
            row = self._multiSlicesView.getValue() - 1
            self._stackedLayoud.setCurrentWidget(self._galleryView)
            if not model == self._galleryView.getModel():
                self._galleryView.setModel(model)
            self._galleryView.selectRow(row)
        self._aSlices.setChecked(not checked)
        self.__setupToolBar()
        self.__updateAxis(axis)

    @pyqtSlot(int)
    def _onAxisChanged(self, index):
        """
        Invoked when the current value for ComboBox axis has been changed
        :param index: (int) The current index
        """
        axis = self._comboBoxCurrentAxis.currentData(Qt.UserRole)
        self._multiSlicesView.setAxis(axis)
        if self._galleryView.isVisible():
            self._galleryView.setModel(self._slicesTableModels[axis])
            self._galleryView.selectRow(self._multiSlicesView.getValue() - 1)

    @pyqtSlot(int)
    def _onVolumeChanged(self, index):
        # FIXME [phv] Review the volume stacks
        pass

    def setModel(self, model):
        """
        Sets the model.
        :param model:  (VolumeModel)
        """
        if model is None:
            raise Exception("Invalid value for model: None")

        self._model = model
        xModel, yModel, zModel = (model.getSlicesModel(AXIS_X),
                                  model.getSlicesModel(AXIS_Y),
                                  model.getSlicesModel(AXIS_Z))
        self._slicesTableModels = {
            AXIS_X: SlicesTableModel(xModel, 'Axis-X'),
            AXIS_Y: SlicesTableModel(yModel, 'Axis-Y'),
            AXIS_Z: SlicesTableModel(zModel, 'Axis-Z')
        }
        self._multiSlicesView.setModel((xModel, yModel, zModel), normalize=True,
                                       slice=int(model.getDim()[0]/2))
        self.__setupComboBoxAxis()

    def clear(self):
        """ Clear the volume view """
        self.setModel(EmptyVolumeModel())

    def setView(self, view):
        """ Sets the current view: GALLERY or SLICES """
        if view == GALLERY:
            self._view = GALLERY
            self._aGallery.setChecked(True)
            self._onGalleryViewTriggered(True)
        elif view == SLICES:
            self._view = SLICES
            self._aSlices.setChecked(True)
            self._onMultiSlicesViewTriggered(True)

        self.__setupToolBar()
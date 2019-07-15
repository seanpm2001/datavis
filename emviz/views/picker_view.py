import sys
import os
from math import cos, sin
from numpy import pi

from PyQt5.QtCore import (pyqtSlot, Qt, QFile, QIODevice, QJsonDocument,
                          QJsonParseError, QLocale, QMetaObject,
                          QCoreApplication)
from PyQt5.QtGui import (QStandardItem, QBrush, QColor, QDoubleValidator,
                         QIntValidator, QKeySequence, QPainterPath)
import PyQt5.QtWidgets as qtw
import pyqtgraph as pg
import qtawesome as qta


# FIXME: We should not import neither em or emviz.core from other submodules
import em
from emviz.widgets import MultiStateAction, OptionList
from emviz.models import (Micrograph, Coordinate, TableModel, ColumnConfig,
                          TYPE_STRING, TYPE_INT)

from .model import TablePageItemModel
from ._image_view import ImageView
from ._columns import ColumnsView


SHAPE_RECT = 0
SHAPE_CIRCLE = 1
SHAPE_CENTER = 2
SHAPE_SEGMENT = 3

PICK = 0
ERASE = 1
SHOW_ON = 0
SHOW_OFF = 1

DEFAULT_MODE = 0
FILAMENT_MODE = 1

picker_params1 = [
    [
        {
            'name': 'threshold',
            'type': 'float',
            'value': 0.55,
            'label': 'Quality threshold',
            'help': 'If this is ... bla bla bla',
            'display': 'default'
        },
        {
            'name': 'thresholdBool',
            'type': 'bool',
            'value': True,
            'label': 'Quality checked',
            'help': 'If this is a boolean param'
        }
    ],
    [
        {
            'name': 'threshold543',
            'type': 'float',
            'value': 0.67,
            'label': 'Quality',
            'help': 'If this is ... bla bla bla',
            'display': 'default'
        },
        {
            'name': 'threshold',
            'type': 'float',
            'value': 14.55,
            'label': 'Quality threshold2',
            'help': 'If this is ... bla bla bla',
            'display': 'default'
        }
    ],
    {
        'name': 'threshold2',
        'type': 'string',
        'value': 'Explanation text',
        'label': 'Threshold ex',
        'help': 'If this is ... bla bla bla 2',
        'display': 'default'
    },
    {
        'name': 'text',
        'type': 'string',
        'value': 'Text example',
        'label': 'Text',
        'help': 'If this is ... bla bla bla for text'
    },
    {
        'name': 'threshold4',
        'type': 'float',
        'value': 1.5,
        'label': 'Quality',
        'help': 'If this is ... bla bla bla for quality'
    },
    {
      'name': 'picking-method',
      'type': 'enum',  # or 'int' or 'string' or 'enum',
      'choices': ['LoG', 'Swarm', 'SVM'],
      'value': 1,  # values in enum are int, in this case it is 'LoG'
      'label': 'Picking method',
      'help': 'Select the picking strategy that you want to use. ',
      # display should be optional, for most params, a textbox is the default
      # for enum, a combobox is the default, other options could be sliders
      'display': 'combo'  # or 'combo' or 'vlist' or 'hlist'
    },
    {
        'name': 'threshold3',
        'type': 'bool',
        'value': True,
        'label': 'Checked',
        'help': 'If this is a boolean param'
    }
]


class PickerView(qtw.QWidget):

    def __init__(self, parent, model, **kwargs):
        """ Constructor
        @param parent reference to the parent widget
        @model input PickerDataModel
        kwargs:
           UI config params.
           sources (dict): dict with tuples (mic-path, coordinates-path) or
                           (mic-path, list) where list contains the coordinates
        """
        qtw.QWidget.__init__(self, parent)
        self._model = model
        self.__currentLabelName = 'Manual'
        self._handleSize = 8
        self.__pickerMode = kwargs.get('picker_mode', FILAMENT_MODE)
        self.__pickerParams = {
            'float': {
                'type': float,
                'display': {
                    'default': qtw.QLineEdit
                },
                'validator': QDoubleValidator
            },
            'int': {
                'type': int,
                'display': {
                    'default': qtw.QLineEdit
                },
                'validator': QIntValidator
            },
            'string': {
                'type': str,
                'display': {
                    'default': qtw.QLineEdit
                }
            },
            'bool': {
                'type': bool,
                'display': {
                    'default': qtw.QCheckBox
                }
            },
            'enum': {
                'display': {
                    'default': OptionList,
                    'vlist': OptionList,
                    'hlist': OptionList,
                    'slider': qtw.QSlider,
                    'combo': OptionList
                }
            }
        }

        self.__paramsWidgets = dict()

        self.__setupUi(**kwargs)
        self.__createColumsViewModel()

        self._currentMic = None
        self._currentImageDim = None
        self._roiList = []
        self._roiAspectLocked = True
        self._roiCentered = True
        self._shape = SHAPE_RECT
        self._clickAction = PICK

        self.__setup(**kwargs)
        self._spinBoxBoxSize.editingFinished.connect(
            self._boxSizeEditingFinished)

        self._setupViewBox()
        self.__segmentROI = None
        self.__eraseList = []
        self.__eraseSize = 300
        self.__eraseROI = pg.CircleROI((0, 0), self.__eraseSize,
                                       pen=pg.mkPen(color="FFF",
                                                    width=1,
                                                    dash=[2, 2, 2]))
        self.__eraseROI.setCursor(Qt.CrossCursor)
        self.__eraseROI.setVisible(False)
        self.__eraseROI.sigRegionChanged.connect(self.__eraseRoiChanged)

        self._imageView.getViewBox().addItem(self.__eraseROI)
        for h in self.__eraseROI.getHandles():
            self.__eraseROI.removeHandle(h)
        self.__eraseROIText = pg.TextItem(text="", color=(220, 220, 0),
                                          fill=pg.mkBrush(color=(0, 0, 0, 128)))
        self.__eraseROIText.setVisible(False)
        self._imageView.getViewBox().addItem(self.__eraseROIText)

        if len(self._model) > 0:
            for micId in self._model:
                self.__addMicToTable(self._model[micId])

        sources = kwargs.get("sources", None)
        if isinstance(sources, dict):
            for k in sources.keys():
                mic_path, coord = sources.get(k)
                self._openFile(mic_path, coord=coord, showMic=False,
                               appendCoord=True)

        self._tvImages.setModel(self._tvModel)
        self._tvImages.setSelectionBehavior(qtw.QAbstractItemView.SelectRows)
        self._tvImages.sigCurrentRowChanged.connect(
            self.__onCurrentRowChanged)
        self._tvImages.getHorizontalHeader().sectionClicked.connect(
            self.__onSectionClicked)
        # By default select the first micrograph in the list
        if self._tvModel.rowCount() > 0:
            self._tvImages.selectRow(0)

    def __setup(self, **kwargs):
        """ Configure the PickerView. """
        v = kwargs.get("remove_rois", "on") == "on"
        if self.__pickerMode == DEFAULT_MODE:
            self._actionErase.setEnabled(v)
        self._roiAspectLocked = kwargs.get("roi_aspect_locked", "on") == "on"
        self._roiCentered = kwargs.get("roi_centered", "on") == "on"

        self._shape = kwargs.get(
            'shape', SHAPE_RECT if self.__pickerMode == DEFAULT_MODE else
            SHAPE_SEGMENT)
        if self._shape == SHAPE_RECT:
            self._actionPickRect.setChecked(True)
        elif self._shape == SHAPE_CIRCLE:
            self._actionPickEllipse.setChecked(True)
        elif self._shape == SHAPE_SEGMENT:
            self._actionPickSegment.setChecked(True)

        self._spinBoxBoxSize.setValue(kwargs.get("boxsize", 100))

    def __setupUi(self, **kwargs):
        self.resize(1097, 741)
        self._horizontalLayout = qtw.QHBoxLayout(self)
        self._horizontalLayout.setContentsMargins(1, 1, 1, 1)
        self._imageView = ImageView(self, **kwargs)
        self._imageView.setObjectName("pageBar")
        imgViewToolBar = self._imageView.getToolBar()

        self._micPanel = imgViewToolBar.createPanel()
        self._micPanel.setSizePolicy(qtw.QSizePolicy.Ignored,
                                     qtw.QSizePolicy.Minimum)
        #  setting a reasonable panel width for micrographs table
        self._micPanel.setGeometry(0, 0, 200, self._micPanel.height())
        self._verticalLayout = qtw.QVBoxLayout(self._micPanel)
        self._verticalLayout.setContentsMargins(0, 0, 0, 0)
        self._tvImages = ColumnsView(self._micPanel, **kwargs)
        self._tvImages.setObjectName("columnsViewImages")
        self._verticalLayout.addWidget(self._tvImages)

        self._viewWidget = qtw.QWidget(self)
        self._viewLayout = qtw.QVBoxLayout(self._viewWidget)
        self._viewLayout.setContentsMargins(1, 1, 1, 1)
        self._viewLayout.addWidget(self._imageView)
        self._labelMouseCoord = qtw.QLabel(self)
        self._labelMouseCoord.setMaximumHeight(22)
        self._labelMouseCoord.setAlignment(Qt.AlignRight)
        self._viewLayout.addWidget(self._labelMouseCoord)

        def _createNewAction(parent, actionName, text="", faIconName=None,
                             checkable=False):
            a = qtw.QAction(parent)
            a.setObjectName(actionName)
            if faIconName:
                a.setIcon(qta.icon(faIconName))
            a.setCheckable(checkable)
            a.setText(text)
            return a

        # picker operations
        actPickerROIS = qtw.QAction(imgViewToolBar)
        actPickerROIS.setIcon(qta.icon('fa.object-group'))
        actPickerROIS.setText('Picker Tools')

        boxPanel = imgViewToolBar.createPanel()
        boxPanel.setObjectName('boxPanel')
        boxPanel.setStyleSheet(
            'QWidget#boxPanel{border-left: 1px solid lightgray;}')

        gLayout = qtw.QVBoxLayout(boxPanel)
        toolbar = qtw.QToolBar(boxPanel)
        toolbar.addWidget(qtw.QLabel("<strong>Action:</strong>", toolbar))

        self._actGroupPickErase = qtw.QActionGroup(self)
        self._actGroupPickErase.setExclusive(True)

        self._actionPick = _createNewAction(self, "actionPick", "",
                                            "fa5s.crosshairs", checkable=True)
        self._actGroupPickErase.addAction(self._actionPick)
        self._actionPick.setChecked(True)
        self._actionPick.setToolTip("Pick")
        self._actionPick.setShortcut(QKeySequence(Qt.Key_P))
        self._actionPick.triggered.connect(self.__onPickTriggered)
        self._imageView.addAction(self._actionPick)
        toolbar.addAction(self._actionPick)

        if self.__pickerMode == DEFAULT_MODE:
            self._actionErase = _createNewAction(self, "actionErase", "",
                                                 "fa5s.eraser", checkable=True)
            self._actGroupPickErase.addAction(self._actionErase)
            self._actionErase.setToolTip("Erase")
            self._actionErase.setShortcut(QKeySequence(Qt.Key_E))
            self._actionErase.triggered.connect(self.__onEraseTriggered)
            self._imageView.addAction(self._actionErase)
            toolbar.addAction(self._actionErase)

        gLayout.addWidget(toolbar)

        toolbar = qtw.QToolBar(boxPanel)
        toolbar.addWidget(qtw.QLabel("<strong>Box:</strong>", toolbar))
        self._labelBoxSize = qtw.QLabel("  Size", toolbar)
        self._spinBoxBoxSize = qtw.QSpinBox(toolbar)
        self._spinBoxBoxSize.setRange(3, 65535)
        toolbar.addWidget(self._labelBoxSize)
        toolbar.addWidget(self._spinBoxBoxSize)
        toolbar.addSeparator()
        self._actionGroupPick = qtw.QActionGroup(self)
        self._actionGroupPick.setExclusive(True)

        toolbar.addWidget(qtw.QLabel("  Shape", toolbar))
        if self.__pickerMode == DEFAULT_MODE:
            self._actionPickRect = _createNewAction(self, "actionPickRect",
                                                    "", "fa.square-o",
                                                    checkable=True)
            self._actionPickRect.setToolTip("Rect")
            self._actionPickRect.setShortcut(QKeySequence(Qt.Key_R))
            self._actionPickRect.setChecked(True)

            self._actionPickEllipse = _createNewAction(self,
                                                       "actionPickEllipse", "",
                                                       "fa.circle-o",
                                                       checkable=True)
            self._actionPickEllipse.setToolTip("Circle")
            self._actionPickEllipse.setShortcut(QKeySequence(Qt.Key_C))
            self._actionPickEllipse.setChecked(False)
            toolbar.addAction(self._actionPickRect)
            toolbar.addAction(self._actionPickEllipse)
            self._actionGroupPick.addAction(self._actionPickRect)
            self._actionGroupPick.addAction(self._actionPickEllipse)
            self._imageView.addAction(self._actionPickRect)
            self._imageView.addAction(self._actionPickEllipse)
        else:
            self._actionPickSegment = _createNewAction(self,
                                                       "actionPickSegment", "",
                                                       "fa5s.arrows-alt-h",
                                                       checkable=True)
            self._actionPickSegment.setToolTip("Segment")
            self._actionPickSegment.setShortcut(QKeySequence(Qt.Key_S))
            self._actionPickSegment.setChecked(True)
            toolbar.addAction(self._actionPickSegment)
            self._actionGroupPick.addAction(self._actionPickSegment)
            self._imageView.addAction(self._actionPickSegment)

        self._actionPickCenter = _createNewAction(self, "actionPickCenter",
                                                  "", "fa5.dot-circle",
                                                  checkable=True)
        self._actionPickCenter.setToolTip("Center")
        self._actionPickCenter.setShortcut(QKeySequence(Qt.Key_D))
        self._actionPickCenter.setChecked(False)

        self._actionPickShowHide = MultiStateAction(toolbar)
        self._actionPickShowHide.add(SHOW_ON, qta.icon('fa5s.toggle-on'),
                                          "Hide coordinates")
        self._actionPickShowHide.add(SHOW_OFF, qta.icon('fa5s.toggle-off'),
                                          "Show coordinates")
        self._actionPickShowHide.set(SHOW_ON)
        self._actionPickShowHide.setShortcut(QKeySequence(Qt.Key_N))
        self._actionPickShowHide.triggered.connect(
            self.__onPickShowHideTriggered)

        toolbar.addAction(self._actionPickCenter)
        toolbar.addSeparator()
        toolbar.addAction(self._actionPickShowHide)

        self._imageView.addAction(self._actionPickCenter)
        self._imageView.addAction(self._actionPickShowHide)
        gLayout.addWidget(toolbar)
        self._paramsLayout = qtw.QGridLayout()
        hLayout = qtw.QHBoxLayout()
        hLayout.addLayout(self._paramsLayout)
        hLayout.addStretch()
        gLayout.addLayout(hLayout)

        self.__addVParamsWidgets(self._paramsLayout, picker_params1)
        if not self._paramsLayout.isEmpty():
            label = qtw.QLabel(self)
            label.setText("<strong>Params:</strong>")
            self._paramsLayout.addWidget(label, 0, 0, Qt.AlignLeft)

            button = qtw.QPushButton(self)
            button.setText("Collect")
            button.clicked.connect(self.__collectParams)
            button.setStyleSheet("font-weight:bold;")
            gLayout.addWidget(button)

        boxPanel.setFixedHeight(gLayout.totalSizeHint().height())

        self._actionGroupPick.addAction(self._actionPickCenter)
        # End-picker operations

        self._horizontalLayout.addWidget(self._viewWidget)

        actMics = qtw.QAction(imgViewToolBar)
        actMics.setIcon(qta.icon('fa.list-alt'))
        actMics.setText('Micrographs')

        controlsPanel = imgViewToolBar.createPanel()
        controlsPanel.setObjectName('boxPanel')
        controlsPanel.setStyleSheet(
            'QWidget#boxPanel{border-left: 1px solid lightgray;}')

        gLayout = qtw.QGridLayout(controlsPanel)

        self._controlTable = qtw.QTableWidget(controlsPanel)
        self.__setupControlsTable()
        gLayout.addWidget(self._controlTable)

        actControls = qtw.QAction(imgViewToolBar)
        actControls.setIcon(qta.icon('fa5s.sliders-h'))
        actControls.setText('Controls')

        imgViewToolBar.addAction(actControls, controlsPanel, index=0,
                                 exclusive=False, checked=False)
        imgViewToolBar.addAction(actMics, self._micPanel, index=0,
                                 exclusive=False, checked=True)
        imgViewToolBar.addAction(actPickerROIS, boxPanel, index=0,
                                 exclusive=False, checked=True)

        self.setWindowTitle("Picker")
        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def __addHParamsWidgets(self, layout, params, row, col):
        """
        Add the params to the given layout in the row "row" from
        the column "col"
        """
        for param in params:
            if isinstance(param, list):
                row, col = self.__addHParamsWidgets(layout, param, row, col)
            elif isinstance(param, dict):
                widget = self.__createParamWidget(param)
                if widget is not None:
                    label = param.get('label')
                    if label is not None:
                        lab = qtw.QLabel(self)
                        lab.setText(label)
                        lab.setToolTip(param.get('help', ""))
                        layout.addWidget(lab, row, col, Qt.AlignRight)
                        col += 1
                    layout.addWidget(widget, row, col, 1, 1)
                    col += 1
        return row, col

    def __addVParamsWidgets(self, layout, params):
        """ Add the widgets created from params to the given QGridLayout """
        row = layout.rowCount()
        for param in params:
            if isinstance(param, list):
                col = 0
                row, col = self.__addHParamsWidgets(layout,
                                                    param, row, col)
                row += 1
            else:
                col = 0
                widget = self.__createParamWidget(param)
                if widget is not None:
                    label = param.get('label')
                    if label is not None:
                        lab = qtw.QLabel(self)
                        lab.setText(label)
                        lab.setToolTip(param.get('help', ""))
                        layout.addWidget(lab, row, col, Qt.AlignRight)
                        col += 1
                    layout.addWidget(widget, row, col, 1, -1)
                    row += 1

    def __createParamWidget(self, param):
        """
        Creates the corresponding widget from the given param.
        """
        if not isinstance(param, dict):
            return None

        widgetName = param.get('name')
        if widgetName is None:
            return None  # rise exception??

        valueType = param.get('type')
        if valueType is None:
            return None  # rise exception??

        paramDef = self.__pickerParams.get(valueType)

        if paramDef is None:
            return None  # rise exception??

        display = paramDef.get('display')
        widgetClass = display.get(param.get('display', 'default'))

        if widgetClass is None:
            return None  # rise exception??

        if valueType == 'enum':
            widget = OptionList(parent=self, display=param.get('display',
                                                               'default'),
                                tooltip=param.get('help', ""), exclusive=True,
                                buttonsClass=qtw.QRadioButton,
                                options=param.get('choices'),
                                defaultOption=param.get('value', 0))
        else:
            widget = widgetClass(self)
            widget.setToolTip(param.get('help', ''))
            self.__setParamValue(widget, param.get('value'))

        widget.setObjectName(widgetName)

        self.__paramsWidgets[widgetName] = param

        if widgetClass == qtw.QLineEdit:
            # widget.setClearButtonEnabled(True)
            validatorClass = paramDef.get('validator')
            if validatorClass is not None:
                val = validatorClass()
                if validatorClass == QDoubleValidator:
                    loc = QLocale.c()
                    loc.setNumberOptions(QLocale.RejectGroupSeparator)
                    val.setLocale(loc)
                widget.setValidator(val)
            if valueType == 'float' or valueType == 'int':
                widget.setFixedWidth(80)

        return widget

    def __setParamValue(self, widget, value):
        """ Set the widget value"""
        if isinstance(widget, qtw.QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, qtw.QCheckBox) and isinstance(value, bool):
            widget.setChecked(value)

    def __removeHandles(self, roi):
        """ Remove all handles from the given roi """
        if roi is not None:
            for h in roi.getHandles():
                roi.removeHandle(h)

    @pyqtSlot()
    def __collectParams(self):
        """ Collect picker params """
        self.__collectData(self._paramsLayout)
        print(picker_params1)

    def __collectData(self, item):
        if isinstance(item, qtw.QVBoxLayout) or isinstance(item, qtw.QHBoxLayout):
            for index in range(item.count()):
                self.__collectData(item.itemAt(index))
        elif isinstance(item, qtw.QWidgetItem):
            widget = item.widget()
            param = self.__paramsWidgets.get(widget.objectName())
            if param is not None:
                t = self.__pickerParams.get(param.get('type')).get('type')
                if isinstance(widget, qtw.QLineEdit):
                    if t is not None:
                        text = widget.text()
                        if text in ["", ".", "+", "-"]:
                            text = 0
                        param['value'] = t(text)
                elif isinstance(widget, qtw.QCheckBox) and t == bool:
                    # other case may be checkbox for enum: On,Off
                    param['value'] = widget.isChecked()
                elif isinstance(widget, OptionList):
                    param['value'] = widget.getSelectedOptions()

    def __setupControlsTable(self):
        """ Setups the controls table (Help) """
        self._controlTable.setColumnCount(2)
        # Set table header
        self._controlTable.setHorizontalHeaderItem(0, qtw.QTableWidgetItem("Tool"))
        self._controlTable.setHorizontalHeaderItem(1, qtw.QTableWidgetItem("Help"))
        # Add table items
        # Add row1
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        self.__addRowToControls([(qtw.QTableWidgetItem(qta.icon('fa.list-alt'),
                                                   "Title1"), flags),
                                 (qtw.QTableWidgetItem("Help text"), flags)])
        # Add row2
        self.__addRowToControls([(qtw.QTableWidgetItem(qta.icon('fa5s.user'),
                                                   "Ok ok"), flags),
                                 (qtw.QTableWidgetItem("Help text 2"), flags)])

        # other configurations
        self._controlTable.setSelectionBehavior(qtw.QAbstractItemView.SelectRows)
        self._controlTable.setSortingEnabled(True)
        self._controlTable.horizontalHeader().setStretchLastSection(True)
        self._controlTable.resizeColumnsToContents()

    def __updateFilemantText(self, angle, size, pos):
        """ Update the filament text, and pos """
        self.__eraseROIText.setPos(pos)
        self.__eraseROIText.setText('angle=%.2f len=%.2f' % (angle, size))

    def __addRowToControls(self, row):
        """ Add a row to controls table """
        rows = self._controlTable.rowCount()
        self._controlTable.setRowCount(rows + 1)
        col = 0
        for v in row:
            item = v[0]
            item.setFlags(v[1])
            self._controlTable.setItem(rows, col, item)
            col += 1

    def __addMicToTable(self, mic):
        """
        Add an image to the em table.
        """
        r = self.__emTable.createRow()
        tableColumn = self.__emTable.getColumnByIndex(0)
        r[tableColumn.getName()] = mic.getId()
        tableColumn = self.__emTable.getColumnByIndex(1)
        r[tableColumn.getName()] = os.path.basename(mic.getPath())
        tableColumn = self.__emTable.getColumnByIndex(2)
        r[tableColumn.getName()] = len(mic)
        self.__emTable.addRow(r)

    def __showHidePickCoord(self, visible):
        """ Show or hide the pick coordinates for the current micrograph """
        for roi in self._roiList:
            roi.getROI().setVisible(visible)

    def __updateEraseTextPos(self):
        """
        Update the erase text position according to the erase-roi.
        """
        pos = self.__eraseROI.pos()
        size = self.__eraseROI.size()
        rect2 = self.__eraseROIText.boundingRect()
        rect2 = self.__eraseROIText.mapRectToView(rect2)
        self.__eraseROIText.setPos(pos.x() + size[0] / 2 - rect2.width(),
                                   pos.y() + size[0] / 2)

    def __removeROI(self, roi):
        """ This slot is invoked when the user clicks on a ROI. """
        if roi:
            self._destroyCoordROI(roi)
            self._roiList.remove(roi.parent)  # remove the coordROI
            self._currentMic.removeCoordinate(roi.coordinate)
            row = self._tvImages.currentRow() % self._tvModel.getPageSize()
            self._tvModel.setData(self._tvModel.createIndex(row, 2),
                                  len(self._currentMic))

    def _showError(self, msg):
        """
        Popup the error msg
        :param msg: The message for the user
        """
        qtw.QMessageBox.critical(self, "Particle Picking", msg)

    def _showMicrograph(self, mic):
        """
        Show the an image in the ImageView
        :param mic: the ImageElem
        """
        self.__eraseROI.setVisible(False)
        self.__eraseROIText.setVisible(False)
        self._destroyROIs()
        self._imageView.clear()
        self._currentMic = mic
        path = mic.getPath()
        # FIXME: The following import is here because it cause a cyclic dependency
        # FIXME: we should remove the use of ImageManager and  ImageRef or find another way
        # FIXME: Check if we want ImageManager or other data model here
        from emviz.core import ImageManager, EmPath
        image = ImageManager.readImage(path)
        self._currentImageDim = image.getDim()
        self._imageView.setImage(ImageManager.getNumPyArray(image))
        self._imageView.setImageInfo(path=path,
                                     format=EmPath.getExt(path),
                                     data_type=str(image.getType()))
        self._createROIs()

    def _destroyROIs(self):
        """
        Remove and destroy all ROIs from the pageBar
        """
        if self._roiList:
            for coordROI in self._roiList:
                self._destroyCoordROI(coordROI.getROI())
            self._roiList = []

    def _createROIs(self):
        """ Create the ROIs for current micrograph
        """
        # Create new ROIs and add to the list
        self._roiList = [self._createCoordROI(coord)
                         for coord in self._currentMic] \
            if self._currentMic else []

    def _updateROIs(self):
        """ Update all ROIs that need to be shown in the current micrographs.
        Remove first the old ones and then create new ones.
        """
        # First destroy the ROIs
        self._destroyROIs()
        # then create new ones
        self._createROIs()

    def _loadMicCoordinates(self, path, parserFunc, clear=True, showMic=True):
        """ Load coordinates for the current selected micrograph.
        Params:
            path: Path that will be parsed and search for coordinates.
            parserFunc: function that will parse the file and yield
                all coordinates.
            clear: Remove all previous coordinates.
            showMic: Show current mic
        """
        if self._currentMic is not None:
            if clear:
                self._currentMic.clear()  # remove all coordinates
            index = self._tvImages.currentIndex()
            for c in parserFunc(path):
                coord = Coordinate(c[0], c[1], c[2])
                self._currentMic.addCoordinate(coord)
                if index.isValid():
                    self._tvModel.setData(
                        self._tvModel.createIndex(index.row(), 2),
                        len(self._currentMic))

            if showMic:
                self._showMicrograph(self._currentMic)

    def _openFile(self, path, **kwargs):
        """
        Open de given file.
        kwargs:
             showMic (boolean): True if you want to show the micrograph
                                immediately. False for add to the micrographs
                                list. Default=True.
             coord (path or list): The path to the coordinates file or a list of
                                   tuples for coordinates.
             appendCoord (boolean): True if you want to append the coordinates
                                    to the current coordinates. False to clear
                                    the current coordinates and add.
                                    Default=False.
        """
        _, ext = os.path.splitext(path)

        if ext == '.json':
            self.openPickingFile(path)
        elif ext == '.box':
            from emviz.core.utils import parseTextCoordinates
            self._loadMicCoordinates(path, parserFunc=parseTextCoordinates,
                                     clear=not kwargs.get("appendCoord", False),
                                     showMic=kwargs.get("showMic", True))
        else:
            from emviz.core.utils import parseTextCoordinates
            c = kwargs.get("coord", None)
            coord = parseTextCoordinates(c) if isinstance(c, str) else c

            self.__openImageFile(path, coord)

    def _makePen(self, labelName, width=1):
        """
        Make the Pen for labelName
        :param labelName: the label name
        :return: pg.makePen
        """
        label = self._model.getLabel(labelName)

        if label:
            return pg.mkPen(color=label["color"], width=width)

        return pg.mkPen(color="#1EFF00", width=width)

    def __createColumsViewModel(self):
        """ Setup the em table """
        Column = em.Table.Column
        self.__emTable = em.Table([Column(1, "Id", em.typeSizeT),
                                   Column(2, "Micrograph", em.typeString),
                                   Column(3, "Coordinates", em.typeSizeT)])
        tableViewConfig = TableModel(
            ColumnConfig('Id', dataType=TYPE_INT, editable=True, visible=False),
            ColumnConfig('Micrograph', dataType=TYPE_STRING, editable=True),
            ColumnConfig('Coordinates', dataType=TYPE_INT, editable=True)
        )
        self._tvModel = TablePageItemModel(self.__emTable,
                                           tableViewConfig=tableViewConfig)

    def __showHandlers(self, roi, show=True):
        """ Show or hide the ROI handlers. """
        if not isinstance(roi, pg.ScatterPlotItem):
            funcName = 'show' if show else 'hide'
            for h in roi.getHandles():
                getattr(h, funcName)()  # show/hide

    def _handleViewBoxClick(self, event):
        """ Invoked when the user clicks on the ViewBox
        (ImageView contains a ViewBox).
        """
        if self._currentMic is None:
            print("not selected micrograph....")
            return
        if event.button() == Qt.LeftButton:
            if self._clickAction == PICK:
                viewBox = self._imageView.getViewBox()
                pos = viewBox.mapToView(event.pos())
                # Create coordinate with event click coordinates and add it
                if self.__pickerMode == DEFAULT_MODE:
                    coord = Coordinate(pos.x(), pos.y(), self.__currentLabelName)
                    self._currentMic.addCoordinate(coord)
                    self._createCoordROI(coord)
                    if self._tvModel is not None:
                        r = self._tvImages.currentRow()
                        self._tvModel.setData(
                            self._tvModel.createIndex(
                                r % self._tvModel.getPageSize(), 2),
                            len(self._currentMic))
                elif self.__segmentROI is None:  # filament mode
                    self.__segPos = pos
                    self.__segmentROI = pg.LineSegmentROI(
                        [(pos.x(), pos.y()), (pos.x(), pos.y())],
                        pen=self._makePen(self.__currentLabelName, 2))
                    viewBox.addItem(self.__segmentROI)
                    self.__eraseROIText.setPos(pos)
                    self.__eraseROIText.setText("angle=")
                    self.__eraseROIText.setVisible(True)
                elif not self.__segPos == pos:  # filament mode
                    coord1 = Coordinate(self.__segPos.x(), self.__segPos.y(),
                                        self.__currentLabelName)
                    coord2 = Coordinate(pos.x(), pos.y(),
                                        self.__currentLabelName)
                    coord = (coord1, coord2)
                    self._currentMic.addCoordinate(coord)
                    self._createCoordROI(coord)
                    if self._tvModel is not None:
                        r = self._tvImages.currentRow()
                        self._tvModel.setData(
                            self._tvModel.createIndex(
                                r % self._tvModel.getPageSize(), 2),
                            len(self._currentMic))
                    viewBox.removeItem(self.__segmentROI)
                    self.__segmentROI = None  # TODO[hv] delete, memory leak???
                    self.__eraseROIText.setVisible(False)

    def _updateBoxSize(self, newBoxSize):
        """ Update the box size to be used. """
        if newBoxSize != self._model.getBoxSize():
            self._model.setBoxSize(newBoxSize)
            # Probably is more efficient to just change size and position
            # of ROIs, but maybe re-creating is good enough
            self._updateROIs()

    def _getSelectedPen(self):
        """
        :return: The selected pen(PPSystem label depending)
        """
        btn = self._buttonGroup.checkedButton()

        if btn:
            return pg.mkPen(color=self._model.getLabel(btn.text())["color"])

        return pg.mkPen(0, 9)

    def _createCoordROI(self, coord):
        """ Create the CoordROI for a given coordinate.
        This function will take into account the selected ROI shape
        and other global properties.
        """
        if self.__pickerMode == FILAMENT_MODE and isinstance(coord, tuple):
                pos1, pos2 = (coord[0], coord[1])
                if isinstance(pos1, Coordinate) \
                        and isinstance(pos2, Coordinate):
                    label = pos1.getLabel()
                else:
                    raise Exception("Invalid coordinates type for picker mode")
        elif self.__pickerMode == DEFAULT_MODE \
                and isinstance(coord, Coordinate):
            label = coord.getLabel()
        elif self.__pickerMode == DEFAULT_MODE and isinstance(coord, tuple):
            x, y = (coord[0], coord[1])
            if isinstance(x, Coordinate) or isinstance(y, Coordinate):
                raise Exception("Invalid coordinate type for picker mode")
            label = self.__currentLabelName
            coord = Coordinate(coord[0], coord[1], self.__currentLabelName)
        else:
            raise Exception("Invalid coordinates for picker mode")

        roiDict = {
            # 'centered': True,
            # 'aspectLocked': self.aspectLocked,
            'pen': self._makePen(label, 2)
        }
        size = self._model.getBoxSize()
        if self.__pickerMode == DEFAULT_MODE:
            if self._actionPickCenter.isChecked():
                roiClass = pg.ScatterPlotItem
                roiDict['symbol'] = 'o'
                roiDict['brush'] = QBrush(QColor(roiDict['pen'].color()))
                roiDict['pen'] = pg.mkPen({'color': "FFF", 'width': 1})
                size = 3
            else:
                if self._shape == SHAPE_RECT:
                    roiClass = pg.RectROI
                elif self._shape == SHAPE_CIRCLE:
                    roiClass = pg.EllipseROI
                else:
                    raise Exception("Unknown shape value: %s" % self._shape)
        else:  # picker-mode : filament
            roiClass = pg.LineSegmentROI if self._actionPickCenter.isChecked() \
                else pg.ROI

        coordROI = CoordROI(coord, size, roiClass, self._handleSize, **roiDict)
        roi = coordROI.getROI()

        # Connect some slots we are interested in
        roi.setAcceptedMouseButtons(Qt.LeftButton)
        if not isinstance(roi, pg.ScatterPlotItem):
            #roi.sigHoverEvent.connect(self._roiMouseHover)
            roi.sigRegionChanged.connect(self._roiRegionChanged)
            roi.sigRegionChangeFinished.connect(self._roiRegionChangeFinished)
            roi. setAcceptHoverEvents(True)
            mouseDoubleClickEvent = roi.mouseDoubleClickEvent
            wheelEvent = roi.wheelEvent
            hoverEnterEvent = roi.hoverEnterEvent
            hoverLeaveEvent = roi.hoverLeaveEvent

            def __hoverEnterEvent(ev):
                hoverEnterEvent(ev)
                self.__showHandlers(roi, True)

            def __hoverLeaveEvent(ev):
                hoverLeaveEvent(ev)
                self.__showHandlers(roi, False)

            def __mouseDoubleClickEvent(ev):
                mouseDoubleClickEvent(ev)
                if self._clickAction == PICK:
                    self.__removeROI(roi)

            def __wheelEvent(ev):
                if self._clickAction == PICK:
                    view = self._imageView.getViewBox()
                    view.setMouseEnabled(False, False)
                    d = 1 if ev.delta() > 0 else -1
                    self._spinBoxBoxSize.setValue(
                        self._spinBoxBoxSize.value() + d * 5)
                    self._boxSizeEditingFinished()
                    view.setMouseEnabled(True, True)
                else:
                    wheelEvent(ev)

            roi.mouseDoubleClickEvent = __mouseDoubleClickEvent
            roi.wheelEvent = __wheelEvent
            roi.hoverEnterEvent = __hoverEnterEvent
            roi.hoverLeaveEvent = __hoverLeaveEvent

        # roi.sigRemoveRequested.connect(self._roiRemoveRequested)
        # roi.sigClicked.connect(self._roiMouseClicked)
        roi.setVisible(self._actionPickShowHide.get() == SHOW_ON)
        self._imageView.getViewBox().addItem(roi)
        roi.setFlag(qtw.QGraphicsItem.ItemIsSelectable, self._clickAction == ERASE)
        self._roiList.append(coordROI)

        if self._shape == SHAPE_CIRCLE or self._shape == SHAPE_RECT:
            self.__removeHandles(roi)

        coordROI.showHandlers(False)  # initially hide ROI handlers

        return coordROI

    def _destroyCoordROI(self, roi):
        """ Remove a ROI from the view, from our list and
        disconnect all related slots.
        """
        view = self._imageView.getViewBox()
        view.removeItem(roi)
        # Disconnect from roi the slots.
        if not isinstance(roi, pg.ScatterPlotItem):
            #roi.sigHoverEvent.disconnect(self._roiMouseHover)
            roi.sigRegionChanged.disconnect(self._roiRegionChanged)
        # roi.sigRemoveRequested.disconnect(self._roiRemoveRequested)
        # roi.sigClicked.disconnect(self._roiMouseClicked)

    def _setupViewBox(self):
        """
        Configures the View Widget for self.pageBar
        """
        v = self._imageView.getViewBox()

        if v:
            v.mouseClickEvent = self._handleViewBoxClick
            wheelEvent = v.wheelEvent

            def __wheelEvent(ev, axis=None):
                wheelEvent(ev, axis=axis)
                if self._clickAction == ERASE:
                    block = self.__eraseROI.blockSignals(True)
                    self.__eraseROI.setVisible(True)
                    self.__eraseROIText.setVisible(True)
                    size = self.__eraseROI.size()[0]
                    dif = -ev.delta() * v.state['wheelScaleFactor']
                    size += dif
                    if size:
                        self.__eraseROI.setSize((size, size), update=False)
                        pos = self._imageView.getViewBox().mapToView(ev.pos())
                        self.__eraseROI.setPos(
                            (pos.x() - size / 2,
                             pos.y() - size / 2))
                        self.__eraseROIText.setText(str(size))
                        self.__updateEraseTextPos()
                    self.__eraseROI.blockSignals(block)

            v.wheelEvent = __wheelEvent

            scene = v.scene()
            if scene:
                scene.sigMouseMoved.connect(self.viewBoxMouseMoved)
                mousePressEvent = scene.mousePressEvent
                mouseReleaseEvent = scene.mouseReleaseEvent

                def __mousePressEvent(ev):
                    mousePressEvent(ev)
                    if self._clickAction == ERASE:
                        block = self.__eraseROI.blockSignals(True)
                        self.__eraseROI.setVisible(True)
                        size = self.__eraseROI.size()[0]
                        pos = self._imageView.getViewBox().mapSceneToView(
                            ev.pos())
                        pos.setX(pos.x() - size / 2)
                        pos.setY(pos.y() - size / 2)
                        self.__eraseROI.setPos((pos.x(), pos.y()))
                        self.__eraseROI.setVisible(True)
                        self.__eraseROIText.setVisible(True)
                        self.__eraseROIText.setText(str(size))
                        self.__updateEraseTextPos()
                        self.__eraseROI.blockSignals(block)

                def __mouseReleaseEvent(ev):
                    mouseReleaseEvent(ev)
                    if self._clickAction == ERASE:
                        for item in self.__eraseList:
                            self._roiList.remove(item.parent)
                            self._currentMic.removeCoordinate(item.coordinate)
                        self.__eraseList = []
                    else:
                        self.__eraseROIText.setVisible(False)

                scene.mousePressEvent = __mousePressEvent
                scene.mouseReleaseEvent = __mouseReleaseEvent

    @pyqtSlot(object)
    def viewBoxMouseMoved(self, pos):
        """
        This slot is invoked when the mouse is moved hover de View
        :param pos: The mouse pos
        """
        if pos:
            origPos = pos
            pos = self._imageView.getViewBox().mapSceneToView(pos)
            imgItem = self._imageView.getImageItem()
            (x, y) = (pos.x(), pos.y())
            value = "x"
            (w, h) = (imgItem.width(), imgItem.height())

            if w and h:
                if x >= 0 and x < w and y >= 0 and y < h:
                    value = "%0.4f" % imgItem.image[int(x), int(y)]
            text = "<table width=\"279\" border=\"0\" align=\"right\">" \
                   "<tbody><tr><td width=\"18\" align=\"right\">x=</td>" \
                   "<td width=\"38\" align=\"left\" nowrap>%i</td>" \
                   "<td width=\"28\" align=\"right\">y=</td>" \
                   "<td width=\"42\" nowrap>%i</td>" \
                   "<td width=\"46\" align=\"right\">value=</td>" \
                   "<td width=\"67\" align=\"left\">%s</td></tr>" \
                   "</tbody></table>"
            self._labelMouseCoord.setText(text % (pos.x(), pos.y(), value))

            if self._clickAction == ERASE:
                block = self.__eraseROI.blockSignals(True)
                size = self.__eraseROI.size()[0]
                pos.setX(pos.x() - size / 2)
                pos.setY(pos.y() - size / 2)
                self.__eraseROI.setPos((pos.x(), pos.y()))
                self.__eraseROI.setVisible(True)
                self.__eraseROIText.setVisible(False)
                self.__eraseROI.blockSignals(block)
            elif self._clickAction == PICK and self.__segmentROI is not None:
                handler = self.__segmentROI.getHandles()[1]
                handler.movePoint(origPos)
                d = pg.Point(pos) - pg.Point(self.__segPos)
                angle = pg.Point(1, 0).angle(d)
                if angle is not None:
                    self.__updateFilemantText(-angle, d.x(), self.__segPos)
                    self.__eraseROIText.setVisible(True)

    @pyqtSlot()
    def on_actionPickEllipse_triggered(self):
        """ Activate the coordinates to ellipse ROI. """
        self._shape = SHAPE_CIRCLE
        self._updateROIs()

    @pyqtSlot()
    def on_actionPickSegment_triggered(self):
        """ Activate the coordinates to filament ROI. """
        self._shape = SHAPE_SEGMENT
        self._updateROIs()

    @pyqtSlot()
    def on_actionPickRect_triggered(self):
        """
        Activate the pick rect ROI.
        Change all boxes to rect ROI
        """
        self._shape = SHAPE_RECT
        self._updateROIs()

    @pyqtSlot()
    def on_actionPickCenter_triggered(self):
        """
        Activate the pick rect ROI.
        Change all boxes to center ROI
        """
        self._shape = SHAPE_CENTER
        self._updateROIs()

    @pyqtSlot(int)
    def __onSectionClicked(self, logicalIndex):
        self._destroyROIs()
        self._imageView.clear()
        self._currentMic = None

    @pyqtSlot()
    def __onPickTriggered(self):
        """ Invoked when action pick is triggered """
        view = self._imageView.getViewBox()
        view.setMouseEnabled(True, True)
        self._clickAction = PICK
        imgItem = self._imageView.getImageItem()
        if imgItem is not None:
            imgItem.setCursor(Qt.ArrowCursor)
        self.__eraseROI.setVisible(False)
        self.__eraseROIText.setVisible(False)
        for roi in self._imageView.getViewBox().addedItems:
            if isinstance(roi, pg.EllipseROI) or isinstance(roi, pg.RectROI) \
                    or isinstance(roi, pg.ScatterPlotItem):
                roi.setFlag(qtw.QGraphicsItem.ItemIsSelectable, False)

    @pyqtSlot()
    def __onEraseTriggered(self):
        """ Invoked when action erase is triggered """
        view = self._imageView.getViewBox()
        view.setMouseEnabled(False, False)
        self._clickAction = ERASE
        imgItem = self._imageView.getImageItem()
        if imgItem is not None:
            imgItem.setCursor(Qt.CrossCursor)
        for roi in self._imageView.getViewBox().addedItems:
            if (isinstance(roi, pg.EllipseROI) or isinstance(roi, pg.RectROI)
                or isinstance(roi, pg.ScatterPlotItem)) and \
                    not roi == self.__eraseROI:
                roi.setFlag(qtw.QGraphicsItem.ItemIsSelectable, True)

    @pyqtSlot()
    def __onPickShowHideTriggered(self):
        """ Invoked when action pick-show-hide is triggered """
        self._actionPickShowHide.next()
        self.__showHidePickCoord(
            self._actionPickShowHide.get() == SHOW_ON)

    @pyqtSlot(int)
    def __onCurrentRowChanged(self, row):
        """ Invoked when current row change in micrographs list """
        micId = int(self._tvModel.getTableData(row, 0))
        try:
            if micId > 0:
                self._showMicrograph(self._model[micId])
        except RuntimeError as ex:
            self._showError(ex.message)

    @pyqtSlot(int)
    def _boxSizeChanged(self, value):
        """
        This slot is invoked when de value of spinBoxBoxSize is changed
        :param value: The value
        """
        self._updateBoxSize(value)

    @pyqtSlot()
    def _boxSizeEditingFinished(self):
        """
        This slot is invoked when spinBoxBoxSize editing is finished
        """
        self._updateBoxSize(self._spinBoxBoxSize.value())

    @pyqtSlot(bool)
    def _labelAction_triggered(self, checked):
        """
        This slot is invoked when clicks on label
        """
        btn = self._buttonGroup.checkedButton()

        if checked and btn:
            self.__currentLabelName = btn.text()

    @pyqtSlot(object)
    def _roiMouseHover(self, roi):
        """ Handler invoked when the roi is hovered by the mouse. """
        self.__showHandlers(roi, roi.mouseHovering)
        #roi.parent.showHandlers(True)

    @pyqtSlot(object)
    def __eraseRoiChanged(self, eraseRoi):
        """ Handler invoked when the roi is moved. """
        self.__eraseROIText.setVisible(False)
        viewBox = self._imageView.getViewBox()
        scene = viewBox.scene()
        pos = self.__eraseROI.pos()
        size = self.__eraseROI.size()
        shape = QPainterPath()
        shape.addEllipse(pos.x(), pos.y(), size[0], size[1])
        scene.setSelectionArea(viewBox.mapViewToScene(shape),
                               Qt.IntersectsItemShape)
        items = scene.selectedItems()
        for item in items:
            if isinstance(item, pg.EllipseROI) or isinstance(item, pg.RectROI) \
                    or isinstance(item, pg.ScatterPlotItem):
                pos = item.pos()
                if not isinstance(item, pg.ScatterPlotItem):
                    size = item.size()
                    pos += size / 2
                    rem = False
                else:
                    rem = True

                if rem or shape.contains(pos):
                    viewBox.removeItem(item)
                    self.__eraseList.append(item)
                    if self._tvModel is not None:
                        r = self._tvImages.currentRow()
                        self._tvModel.setData(
                            self._tvModel.createIndex(
                                r % self._tvModel.getPageSize(), 2),
                            len(self._currentMic) - len(self.__eraseList))

    @pyqtSlot(object)
    def _roiRegionChanged(self, roi):
        """
        Handler invoked when the roi region is changed.
        For example:
           When the user stops dragging the ROI (or one of its handles)
           or if the ROI is changed programatically.
        """
        if self.__pickerMode == DEFAULT_MODE:
            pos = roi.pos()
            size = roi.size()
            if roi.coordinate is not None:
                roi.coordinate.set(int(pos.x() + size[0]/2.0),
                                   int(pos.y() + size[1]/2.0))
        else:  # filament mode
            self.__updateFilemantText(roi.angle(), roi.size()[0], roi.pos())
            self.__eraseROIText.setVisible(True)

    @pyqtSlot(object)
    def _roiRegionChangeFinished(self, roi):
        """
        Handler invoked when the roi region is changed.
        For example:
           When the user stops dragging the ROI (or one of its handles)
           or if the ROI is changed programatically.
        """
        if self.__pickerMode == DEFAULT_MODE:
            pos = roi.pos()
            size = roi.size()
            if roi.coordinate is not None:
                roi.coordinate.set(int(pos.x() + size[0] / 2.0),
                                   int(pos.y() + size[1] / 2.0))
        else:  # filament mode
            viewBox = self._imageView.getViewBox()
            pos1 = viewBox.mapSceneToView(roi.getSceneHandlePositions(0)[1])
            pos2 = viewBox.mapSceneToView(roi.getSceneHandlePositions(1)[1])
            coord1, coord2 = roi.coordinate
            coord1.set(pos1.x(), pos1.y())
            coord2.set(pos2.x(), pos2.y())
            if isinstance(roi, pg.ROI):
                width = roi.size().y()
                if not width == self._model.getBoxSize():
                    self._spinBoxBoxSize.setValue(width)
                    self._boxSizeEditingFinished()

    def __openImageFile(self, path, coord=None):
        """
        Open an em image for picking
        :param path: file path
        :param coord: coordinate list ([(x1,y1), (x2,y2)...])
        """
        if path:
            try:
                imgElem = Micrograph(0,
                                     path,
                                     coord)
                imgElem.setId(self._model.nextId())
                self._model.addMicrograph(imgElem)
                self.__addMicToTable(imgElem)
            except:
                print(sys.exc_info())
                self._showError(sys.exc_info()[2])

    def openPickingFile(self, path):
        """
        Open the picking specification file an add the ImageElem
        to the ColumnsView widget
        :param path: file path
        """
        file = None
        if path:
            try:
                file = QFile(path)

                if file.open(QIODevice.ReadOnly):
                    error = QJsonParseError()
                    json = QJsonDocument.fromJson(file.readAll(), error)

                    if not error.error == QJsonParseError.NoError:
                        self._showError("Parsing pick file: " +
                                        error.errorString())
                    else:
                        # FIXME: The following import is here because it cause a cyclic dependency
                        # FIXME: we should remove the use of ImageElemParser here
                        from emviz.core import ImageElemParser
                        parser = ImageElemParser()
                        imgElem = parser.parseImage(json.object())
                        if imgElem:
                            imgElem.setId(self._model.getImgCount()+1)
                            self._model.addMicrograph(imgElem)
                            self.__addMicToTable(imgElem)
                else:
                    self._showError("Error opening file.")
                    file = None

            except:
                print(sys.exc_info())
            finally:
                if file:
                    file.close()

    def getImageDim(self):
        """ Returns the current image dimentions """
        return self._currentImageDim

    def getToolBar(self):
        return self._imageView.getToolBar()

    def retranslateUi(self):
        _translate = QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "MainWindow"))


class MicrographItem(QStandardItem):
    """
    The MicrographItem is the item that we use in the ColumnsView
    where the images are displayed
    """
    def __init__(self, imgElem, icon=None):
        super(MicrographItem, self).__init__("%i" % imgElem.getId())
        self._micrograph = imgElem
        if icon:
            self.setIcon(icon)

    def getMicrograph(self):
        """ Return the micrographs corresponding to this node (or item). """
        return self._micrograph


class CoordROI:
    """ Class to match between ROI objects and corresponding coordinate """
    def __init__(self, coord, boxSize, roiClass, handleSize, **kwargs):
        # Lets compute the left-upper corner for the ROI
        if roiClass == pg.ScatterPlotItem:
            self._roi = pg.ScatterPlotItem(pos=[(coord.x, coord.y)], **kwargs)
        elif isinstance(coord, tuple):  # filament coordinates (Coord1, Coord2)
            pos1, pos2 = coord[0], coord[1]
            self._roi = self.__createFilament((pos1.x, pos1.y),
                                              (pos2.x, pos2.y),
                                              boxSize, roiClass,
                                              handleSize, **kwargs)
        else:
            half = boxSize / 2
            x = coord.x - half
            y = coord.y - half
            self._roi = roiClass((x, y), (boxSize, boxSize), **kwargs)

        # Set a reference to the corresponding coordinate
        self._roi.coordinate = coord
        self._roi.parent = self

    def __createFilament(self, pos1, pos2, width, roiClass, handleSize,
                         **kwargs):
        """
        Create a line or filament according to the given roi class:
        pg.LineSegmentROI or pg.ROI
        """
        if roiClass == pg.ROI:
            d = pg.Point(pos2) - pg.Point(pos1)
            angle = pg.Point(1, 0).angle(d)
            if angle is None:
                angle = 0
            ra = -angle * pi / 180.
            c = pg.Point(width / 2. * sin(ra), -width / 2. * cos(ra))
            pos1 = pos1 + c

            seg = pg.ROI(pos1, size=pg.Point(d.length(), width), angle=-angle,
                         **kwargs)
            seg.handleSize = handleSize
            seg.addScaleRotateHandle([0, 0.5], [1, 0.5])
            seg.addScaleRotateHandle([1, 0.5], [0, 0.5])
            seg.addScaleHandle([1, 0], [1, 1])
            seg.addScaleHandle([0, 1], [0, 0])
            seg.addScaleHandle([0.5, 1], [0.5, 0.5])
        else:
            seg = pg.LineSegmentROI([pos1, pos2], **kwargs)

        return seg

    def getCoord(self):
        """ Return the internal coordinate. """
        return self._roi.coordinate

    def getROI(self):
        return self._roi

    def showHandlers(self, show=True):
        """ Show or hide the ROI handlers. """
        if self._roi and not isinstance(self._roi, pg.ScatterPlotItem):
            funcName = 'show' if show else 'hide'
            for h in self._roi.getHandles():
                getattr(h, funcName)()  # show/hide

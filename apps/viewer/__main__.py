#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
import argparse

from PyQt5.QtCore import QDir, QSize, Qt, pyqtSlot
from PyQt5.QtWidgets import (QApplication, QMessageBox, QWidget, QHBoxLayout,
                             QSplitter, QSizePolicy, QVBoxLayout,
                             QPushButton, QAbstractItemView)

from emviz.core import (EmPath, VolImageManager, ModelsFactory,
                        ViewsFactory, MOVIE_SIZE, getDim)
from emviz.views import (DataView, PIXEL_UNITS, GALLERY, COLUMNS, ITEMS, SLICES,
                         ImageView, SlicesView, SHAPE_CIRCLE, SHAPE_RECT,
                         SHAPE_SEGMENT,
                         SHAPE_CENTER, DEFAULT_MODE, FILAMENT_MODE, PickerView,
                         PagingView, ColumnsView, VolumeView)
from emviz.widgets import ActionsToolBar, DynamicWidgetsFactory, TriggerAction
from emviz.models import EmptyTableModel
from emviz.windows import BrowserWindow

from utils import *

tool_params1 = [
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    paramCount = 0

    kwargs = {}


    class CmpView(QWidget):

        def __init__(self, parent, files, **kwargs):
            """
            Constructor
            :param parent: the parent widget
            :param files: the file list
            :param kwargs:
            """
            QWidget.__init__(self, parent)
            self._tvModel = None
            self._imageData = None
            self._processedImageData = None
            self._leftView = None
            self._rightView = None
            self._path = None
            self.__setupUi(**kwargs)
            self.__createColumsViewModel(files)
            self._columnsViewFiles.setSelectionBehavior(
                QAbstractItemView.SelectRows)
            self._columnsViewFiles.sigCurrentRowChanged.connect(
                self.__onCurrentRowChanged)

        def __setupUi(self, **kwargs):
            self.resize(1097, 741)
            self._mainLayout = QHBoxLayout(self)
            self._mainLayout.setContentsMargins(1, 1, 1, 1)
            self._mainSplitter = QSplitter(self)

            self._splitter = QSplitter(self)
            self._toolBar = ActionsToolBar(self, orientation=Qt.Vertical)
            self._toolBar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            self._splitter.addWidget(self._toolBar)
            self._splitter.setCollapsible(0, False)
            self._splitter.addWidget(self._mainSplitter)

            self._filesPanel = self._toolBar.createPanel('filesPanel')
            self._filesPanel.setSizePolicy(QSizePolicy.Ignored,
                                           QSizePolicy.Ignored)

            vLayout = QVBoxLayout(self._filesPanel)
            vLayout.setContentsMargins(0, 0, 0, 0)
            self._columnsViewFiles = ColumnsView(self._filesPanel,
                                                 model=EmptyTableModel())
            vLayout.addWidget(self._columnsViewFiles)
            self._actFiles = TriggerAction(parent=None, actionName="AFiles",
                                           text='Files',
                                           faIconName='fa5s.file')
            #  setting a reasonable width for display panel
            self._filesPanel.setGeometry(0, 0, vLayout.sizeHint().width(),
                                         self._filesPanel.height())
            self._toolBar.addAction(self._actFiles, self._filesPanel,
                                    exclusive=False, checked=True)

            self._paramsPanel = self._toolBar.createPanel('paramsPanel')
            self._paramsPanel.setSizePolicy(QSizePolicy.Ignored,
                                            QSizePolicy.Ignored)
            dFactory = DynamicWidgetsFactory()
            self._dynamicWidget = dFactory.createWidget(tool_params1)
            vLayout = QVBoxLayout(self._paramsPanel)
            vLayout.setContentsMargins(0, 0, 0, 0)
            vLayout.addWidget(self._dynamicWidget)
            button = QPushButton(self)
            button.setText("Collect")
            button.clicked.connect(self.__collectParams)
            button.setStyleSheet("font-weight:bold;")
            vLayout.addWidget(button)
            self._paramsPanel.setFixedHeight(vLayout.totalSizeHint().height())
            self._paramsPanel.setMinimumWidth(vLayout.totalSizeHint().width())

            self._actParams = TriggerAction(parent=None, actionName="APArams",
                                            text='Params',
                                            faIconName='fa5s.id-card')
            self._toolBar.addAction(self._actParams, self._paramsPanel,
                                    exclusive=False, checked=True)

            self._mainLayout.addWidget(self._splitter)

        def __createViews(self, dim, **kwargs):
            """
            Creates the left and right views according
            to the given image dimensions
            """
            if dim.z == 1:
                # kwargs['tool_bar'] = 'off'
                self._leftView = ImageView(self, **kwargs)
                self._rightView = ImageView(self, **kwargs)
            else:
                kwargs['toolBar'] = False
                kwargs['imageManager'] = VolImageManager(self._imageData)
                self._leftView = VolumeView(self, **kwargs)
                kwargs['imageManager'] = \
                    VolImageManager(self._processedImageData)
                self._rightView = VolumeView(self, **kwargs)

            self._splitter.addWidget(self._leftView)
            self._splitter.addWidget(self._rightView)

        def __createColumsViewModel(self, files=None):
            """ Setup the em table """
            pass
            # FIXME[phv] commented until revisions
            #Column = em.Table.Column
            #emTable = em.Table([Column(1, "File Name", em.typeString),
            #                    Column(2, "Path", em.typeString)])
            #tableViewConfig = TableModel()
            #tableViewConfig.addColumnConfig(name='File Name',
            #                                dataType=TableModel.TYPE_STRING,
            #                                label='File Name',
            #                                editable=False,
            #                                visible=True)
            #tableViewConfig.addColumnConfig(name='Path',
            #                                dataType=TableModel.TYPE_STRING,
            #                                label='Path',
            #                                editable=False,
            #                                visible=False)
            #if isinstance(files, list):
            #    for file in files:
            #        r = emTable.createRow()
            #        tableColumn = emTable.getColumnByIndex(0)
            #        r[tableColumn.getName()] = os.path.basename(file)
            #        tableColumn = emTable.getColumnByIndex(1)
            #        r[tableColumn.getName()] = file
            #        emTable.addRow(r)

            #self._tvModel = TablePageItemModel(emTable,
            #                                   tableViewConfig=tableViewConfig)
            #self._columnsViewFiles.setModel(self._tvModel)

        @pyqtSlot()
        def __collectParams(self):
            """ Collect params """
            data = self._dynamicWidget.getParams()
            print(data)

        @pyqtSlot(int)
        def __onCurrentRowChanged(self, row):
            """ Invoked when current row change in micrographs list """
            pass
            # FIXME[phv] commented until revisions
            #path = self._tvModel.getTableData(row, 1)
            #try:
            #   if self._leftView is None:
            #        dim = ImageManager.getDim(path)
            #        self.__createViews(dim, **kwargs)
            #    self._showPath(path)
            #except RuntimeError as ex:
            #    self._showError(ex.message)

        def _showPath(self, path):
            """
            Show the given image
            :param path: the image path
            """
            if not self._path == path:
                try:
                    self._path = path
                    image = ImageManager.readImage(path)
                    self._imageData = ImageManager.getNumPyArray(image)
                    self._processedImageData = \
                        ImageManager.getNumPyArray(image, copy=True)
                    if isinstance(self._leftView, ImageView):
                        self._leftView.setImage(self._imageData)
                        ext = EmPath.getExt(path)
                        data_type = str(image.getType())
                        self._leftView.setImageInfo(path=path, format=ext,
                                                    data_type=data_type)
                        self._rightView.setImage(self._processedImageData)
                        self._rightView.setImageInfo(path=path, format=ext,
                                                     data_type=data_type)
                    elif isinstance(self._leftView, VolumeView):
                        imgManager = VolImageManager(self._imageData)
                        self._leftView.setup(path, imageManager=imgManager)
                        imgManager = VolImageManager(self._processedImageData)
                        self._rightView.setup(path, imageManager=imgManager)

                except RuntimeError as ex:
                    print(ex)
                    raise ex
                except Exception as ex:
                    print(ex)
                    raise ex

    argParser = argparse.ArgumentParser(usage='Tool for Viewer Apps',
                                        description='Display the selected '
                                                    'viewer app',
                                        prefix_chars='--',
                                        argument_default=None)

    # GLOBAL PARAMETERS
    argParser.add_argument('files', type=str, nargs='*', default=[],
                           help='3D image path or a list of image files or'
                           ' specific directory')

    # EM-BROWSER PARAMETERS
    on_off_dict = {'on': True, 'off': False}
    on_off = capitalizeStrList(on_off_dict.keys())
    argParser.add_argument('--zoom', type=str, default=True, required=False,
                           choices=on_off, action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Enable/disable the option to zoom in/out in '
                                'the image(s)')
    argParser.add_argument('--axis', type=str, default=True, required=False,
                           choices=on_off, action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Show/hide the image axis (ImageView)')
    argParser.add_argument('--tool-bar', type=str, default=True, required=False,
                           choices=on_off, action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Show or hide the toolbar for ImageView')
    argParser.add_argument('--histogram', type=str, default=False,
                           required=False, choices=on_off,
                           action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Show or hide the histogram for ImageView')
    argParser.add_argument('--fit', type=str, default=True,
                           required=False, choices=on_off,
                           action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Enables fit to size for ImageView')
    viewsDict = {
        'gallery': GALLERY,
        'columns': COLUMNS,
        'items': ITEMS,
        'slices': SLICES
    }
    views_params = capitalizeStrList(viewsDict.keys())

    argParser.add_argument('--view', type=str, default='', required=False,
                           choices=views_params, action=ValidateValues,
                           valuesDict=viewsDict,
                           help=' The default view. Default will depend on the '
                                'input')
    argParser.add_argument('--size', type=int, default=100,
                           required=False,
                           help=' The default size of the displayed image, '
                                'either in pixels or in percentage')

    # Picker arguments
    argParser.add_argument('--picker', type=str, nargs='*', default=[],
                           required=False, action=ValidateMics,
                           help='Show the Picker tool. '
                                '2 path pattern for micrograph and coordinates '
                                'files.')
    argParser.add_argument('--boxsize', type=int, default=100,
                           required=False,
                           help=' an integer for pick size(Default=100).')
    shapeDict = {
        'RECT': SHAPE_RECT,
        'CIRCLE': SHAPE_CIRCLE,
        'CENTER': SHAPE_CENTER,
        'SEGMENT': SHAPE_SEGMENT
    }
    shape_params = capitalizeStrList(shapeDict.keys())
    argParser.add_argument('--shape', default=SHAPE_RECT,
                           required=False, choices=shape_params,
                           valuesDict=shapeDict,
                           action=ValidateValues,
                           help=' the shape type '
                                '[CIRCLE, RECT, CENTER or SEGMENT]')
    pickerDict = {
        'default': DEFAULT_MODE,
        'filament': FILAMENT_MODE
    }
    picker_params = capitalizeStrList(shapeDict.keys())
    argParser.add_argument('--picker-mode', default='default', required=False,
                           choices=picker_params, valuesDict=pickerDict,
                           action=ValidateValues,
                           help=' the picker type [default or filament]')
    argParser.add_argument('--remove-rois', type=str, default=True,
                           required=False, choices=on_off,
                           action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Enable/disable the option. '
                                'The user will be able to eliminate rois')
    argParser.add_argument('--roi-aspect-locked', type=str, default=True,
                           required=False, choices=on_off,
                           action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Enable/disable the option. '
                                'The rois will retain the aspect ratio')
    argParser.add_argument('--roi-centered', type=str, default=True,
                           required=False, choices=on_off,
                           action=ValidateValues,
                           valuesDict=on_off_dict,
                           help=' Enable/disable the option. '
                                'The rois will work accordance with its center')
    # COLUMNS PARAMS
    argParser.add_argument('--visible', type=str, nargs='?', default='',
                           required=False, action=ValidateStrList,
                           help=' Columns to be shown (and their order).')
    argParser.add_argument('--render', type=str, nargs='?', default='',
                           required=False, action=ValidateStrList,
                           help=' Columns to be rendered.')
    argParser.add_argument('--sort', type=str, nargs='?', default='',
                           required=False, action=ValidateStrList,
                           help=' Sort command.')

    argParser.add_argument('--cmp', type=str, nargs='*', default=[],
                           required=False, action=ValidateCmpList,
                           help='Show the Comparator tool. '
                                'You can specify a list of path patterns.')
    args = argParser.parse_args()

    models = None
    delegates = None

    # ARGS
    files = []
    for f in args.files:
        files.append(QDir.toNativeSeparators(f))

    if not files and not args.picker:
        files = [str(os.getcwd())]  # if not files use the current dir

    kwargs['files'] = files
    kwargs['zoom'] = args.zoom
    kwargs['histogram'] = args.histogram
    kwargs['roi'] = False
    kwargs['menu'] = False
    kwargs['popup'] = False
    kwargs['toolBar'] = args.tool_bar
    kwargs['img_desc'] = False
    kwargs['fit'] = args.fit
    kwargs['axis'] = args.axis
    kwargs['size'] = args.size
    kwargs['maxCellSize'] = 300
    kwargs['minCellSize'] = 25
    kwargs['zoom_units'] = PIXEL_UNITS
    kwargs['views'] = [GALLERY, COLUMNS, ITEMS]

    kwargs['view'] = args.view
    kwargs['selectionMode'] = PagingView.MULTI_SELECTION

    # Picker params
    kwargs['boxsize'] = args.boxsize
    kwargs['picker_mode'] = args.picker_mode
    kwargs['shape'] = args.shape
    kwargs['remove_rois'] = args.remove_rois
    kwargs['roi_aspect_locked'] = args.roi_aspect_locked
    kwargs['roi_centered'] = args.roi_centered

    def getPreferedBounds(width=None, height=None):
        size = QApplication.desktop().size()
        p = 0.8
        (w, h) = (int(p * size.width()), int(p * size.height()))
        width = width or w
        height = height or h
        w = min(width, w)
        h = min(height, h)
        return (size.width() - w) / 2, (size.height() - h) / 2, w, h

    def fitViewSize(viewWidget, imageDim=None):
        """
        Fit the view size according to the desktop size.
        imageDim is the image dimensions if viewWidget is ImageView
         """
        if view is None:
            return

        if isinstance(viewWidget, DataView):
            size = viewWidget.getPreferredSize()
            x, y, w, h = getPreferedBounds(size[0], size[1])
        elif (isinstance(viewWidget, ImageView) or
                isinstance(viewWidget, SlicesView) or
                isinstance(viewWidget, PickerView)) and \
                imageDim is not None:
            if isinstance(viewWidget, SlicesView):
                toolWith = 0
            else:
                toolBar = viewWidget.getToolBar()
                toolWith = toolBar.getPanelMinSize() + toolBar.width()

            x, y, w, h = getPreferedBounds(max(viewWidget.width(), imageDim.x),
                                           max(viewWidget.height(),
                                               imageDim.y))
            size = QSize(imageDim.x, imageDim.y).scaled(w, h,
                                                        Qt.KeepAspectRatio)
            dw, dh = w - size.width(), h - size.height()
            x, y, w, h = x + dw/2 - toolWith, y + dh/2, \
                         size.width() + 2 * toolWith, size.height()
        else:
            x, y, w, h = getPreferedBounds(100000,
                                           100000)
        viewWidget.setGeometry(x, y, w, h)

    def showMsgBox(text, icon=None, details=None):
        """
        Show a message box with the given text, icon and details.
        The icon of the message box can be specified with one of the Qt values:
            QMessageBox.NoIcon
            QMessageBox.Question
            QMessageBox.Information
            QMessageBox.Warning
            QMessageBox.Critical
        """
        msgBox = QMessageBox()
        msgBox.setText(text)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setDefaultButton(QMessageBox.Ok)
        if icon is not None:
            msgBox.setIcon(icon)
        if details is not None:
            msgBox.setDetailedText(details)

        msgBox.exec_()

    try:
        d = None
        if args.picker in ['on', 'On'] or isinstance(args.picker, dict):
            if files and files[0] == str(os.getcwd()):
                files = None
            kwargs["selectionMode"] = PagingView.SINGLE_SELECTION
            view = PickerView(None, createPickerModel(files, args.boxsize),
                              sources=args.picker, **kwargs)
            view.setWindowTitle("EM-PICKER")
            d = view.getImageDim()
        elif args.cmp in ['on', 'On'] or args.cmp:
            view = CmpView(None,
                           args.cmp if isinstance(args.cmp, list) else files)
            view.setWindowTitle('EM-COMPARATOR')

        else:
            # If the input is a directory, display the BrowserWindow
            if len(files) > 1:
                raise Exception("Multiple files are not supported")
            else:
                files = files[0]

            if not os.path.exists(files):
                raise Exception("Input file '%s' does not exists. " % files)

            if os.path.isdir(files):
                kwargs['selectionMode'] = PagingView.SINGLE_SELECTION
                kwargs['view'] = args.view or COLUMNS
                view = BrowserWindow(None, files, **kwargs)
            elif EmPath.isTable(files):  # Display the file as a Table:
                if not args.view == SLICES:
                    if args.visible or args.render:
                        # FIXME[phv] create the TableConfig
                        pass
                    else:
                        tableViewConfig = None
                    if args.sort:
                        # FIXME[phv] sort by the given column
                        pass
                    kwargs['view'] = args.view or COLUMNS
                    view = ViewsFactory.createDataView(files, **kwargs)
                    fitViewSize(view, d)
                else:
                    raise Exception("Invalid display mode for table: '%s'"
                                    % args.view)
            elif EmPath.isImage(files) or EmPath.isVolume(files) \
                    or EmPath.isStack(files):
                # *.mrc may be image, stack or volume. Ask for dim.n
                d = getDim(files)
                if d.n == 1:  # Single image or volume
                    if d.z == 1:  # Single image
                        view = ViewsFactory.createImageView(files, **kwargs)
                    else:  # Volume
                        mode = args.view or SLICES
                        if mode == SLICES or mode == GALLERY:
                            kwargs['toolBar'] = False
                            kwargs['axis'] = False
                            sm = PagingView.SINGLE_SELECTION
                            kwargs['selectionMode'] = sm
                            view = ViewsFactory.createVolumeView(files,
                                                                 **kwargs)
                        else:
                            raise Exception("Invalid display mode for volume")
                else:  # Stack
                    kwargs['selectionMode'] = PagingView.SINGLE_SELECTION
                    if d.z > 1:  # volume stack
                        mode = args.view or SLICES
                        if mode == SLICES:
                            kwargs['toolBar'] = False
                            kwargs['axis'] = False
                            view = ViewsFactory.createVolumeView(files,
                                                                 **kwargs)
                        else:
                            kwargs['view'] = GALLERY
                            view = ViewsFactory.createDataView(files, **kwargs)
                    else:
                        mode = args.view or (SLICES if d.x > MOVIE_SIZE
                                             else GALLERY)
                        if mode == SLICES:
                            view = ViewsFactory.createSlicesView(files,
                                                                 **kwargs)
                        else:
                            kwargs['view'] = mode
                            view = ViewsFactory.createDataView(files, **kwargs)
            elif EmPath.isStandardImage(files):
                view = ViewsFactory.createImageView(files, **kwargs)
            else:
                view = None
                raise Exception("Can't perform a view for this file.")

        if view:
            fitViewSize(view, d)
            view.show()

    except Exception as ex:
        showMsgBox("Can't perform the action", QMessageBox.Critical, str(ex))
        print(traceback.format_exc())
        sys.exit(0)
    except RuntimeError as ex:
        showMsgBox("Can't perform the action", QMessageBox.Critical, str(ex))
        print(traceback.format_exc())
        sys.exit(0)
    except ValueError as ex:
        showMsgBox("Can't perform the action", QMessageBox.Critical, str(ex))
        print(traceback.format_exc())
        sys.exit(0)

    sys.exit(app.exec_())

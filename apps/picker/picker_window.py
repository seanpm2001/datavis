import sys
import os

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (pyqtSlot, Qt, QDir, QModelIndex, QItemSelectionModel,
                          QFile, QIODevice, QJsonDocument, QJsonParseError)
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QCompleter,
                             QInputDialog)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import pyqtgraph as pg
import qtawesome as qta
from pyqtgraph import RectROI, ROI
import numpy as np
import em


from model import PPSystem, ImageElem, PPCoordinate, PPBox
from utils import ImageElemParser


class PPWindow(QMainWindow):

    def __init__(self, parent=None, **kwargs):
        """
        Constructor

        @param parent reference to the parent widget
        @type QWidget
        """
        QMainWindow.__init__(self, parent)
        self.__setupUi__()
        self.ppSystem = PPSystem()
        self.model = QStandardItemModel()
        self.treeViewImages.setModel(self.model)

        # Completer init
        self.completer = QCompleter()
        self.lineEdit.setCompleter(self.completer)
        # self.completer.setFilterMode(Qt.MatchCaseSensitive)
        self.completer.setModel(self.treeViewImages.model())
        self.completer.activated[QModelIndex].connect(self.on_treeViewImages_clicked)

        # picking dim in pixels, respect to the image size
        self.pickingW = 200
        self.pickingH = 200
        self.actualImage = None

        self.disableZoom = kwargs.get('--disable-zoom', False)
        self.disableHistogram = kwargs.get('--disable-histogram', False)
        self.disableROI = kwargs.get('--disable-roi', False)
        self.disableMenu = kwargs.get('--disable-menu', False)
        self.disableRemoveROIs = kwargs.get('--disable-remove-rois', False)
        self.disableROIAspectLocked = kwargs.get('--disable-roi-aspect-locked',
                                                 False)

        for pickFile in kwargs.get('--pick-files', []):
            self._openFile(pickFile)

        self._setupImageView()

    @pyqtSlot()
    def showError(self, msg):
        """
        Popup the error msg
        :param msg: The message for the user
        """
        QMessageBox.critical(self, "Particle Picking", msg)

    @pyqtSlot()
    def _on_imageAdded(self, imgElem):
        """
        Add an image to the treeview widget. The user can invoke this method
        when he wants to add an image or connect it to a signal that notifies
        the action of add an ImageElem.
        We use the fa.archive icon from qtawesome temporarily.
        :param imgElem: The image
        """
        item = PPItem(imgElem.getName(), imgElem, qta.icon("fa.archive"))
        self.model.appendRow(item)

    @pyqtSlot()
    def on_actionOpenPick_triggered(self):
        """
        Show a FileDialog for the picking file (.json) selection.
        Open the file, if was selected, and add a new node corresponding
        to the image specified in the file.
        """
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File",
                                                  QDir.currentPath())
        if fileName:
            self._openFile(fileName)

    @pyqtSlot()
    def on_actionNextImage_triggered(self):
        """
        Select the next node in the treeview widget
        """
        indexes = self.treeViewImages.selectedIndexes()

        if indexes:
            selectedIndex = indexes[0]
            nextIndex = self.treeViewImages.indexBelow(selectedIndex)
            if nextIndex:
                selectionModel = self.treeViewImages.selectionModel()
                selectionModel.select(selectedIndex, QItemSelectionModel.Toggle)
                selectionModel.select(nextIndex, QItemSelectionModel.Toggle)
                self.on_treeViewImages_clicked(nextIndex)

    @pyqtSlot()
    def on_actionSetPickBox_triggered(self):
        """
        Show an input dialog for user configuration
        """

        boxSize = QInputDialog.getInt(self,
                                      "Particle picking",
                                      "Box size",
                                      self.pickingW,
                                      5,
                                      65535)
        if boxSize[1]:
            self.pickingW = boxSize[0]
            self.pickingH = boxSize[0]

    @pyqtSlot()
    def on_actionPrevImage_triggered(self):
        """
        Select the previous node in the treeview widget
        """
        indexes = self.treeViewImages.selectedIndexes()

        if indexes:
            selectedIndex = indexes[0]
            nextIndex = self.treeViewImages.indexAbove(selectedIndex)
            if nextIndex:
                selectionModel = self.treeViewImages.selectionModel()
                selectionModel.select(selectedIndex, QItemSelectionModel.Toggle)
                selectionModel.select(nextIndex, QItemSelectionModel.Toggle)
                self.on_treeViewImages_clicked(nextIndex)

    @pyqtSlot(QModelIndex)
    def on_treeViewImages_clicked(self, index):
        """
        This slot is invoked when de user clicks one node in the treeview widget
        :param index: Index for the selected node (or item)
        :return:
        """
        item = self.model.itemFromIndex(index)
        if item:
            self.showImage(item.getImageElem())

    def showImage(self, imgElem):
        """
        Show the an image in the ImageView
        :param imgElem: the ImageElem
        """
        if imgElem:
            self.actualImage = imgElem
            self._clearImageView()  # clean the widget for the new image
            img = em.Image()
            loc2 = em.ImageLocation(imgElem.getPath())
            img.read(loc2)
            array = np.array(img, copy=False)
            self.imageView.setImage(array)
            viewBox = self.imageView.getView()

            for ppCoord in imgElem.getCoordinates():

                roi = self._createRectROI((ppCoord.x-imgElem.box.width/2,
                                           ppCoord.y-imgElem.box.height/2),
                                          (imgElem.box.width,
                                           imgElem.box.height),
                                          pen=(0, 9))
                roi.pickCoord = ppCoord
                viewBox.addItem(roi)

    def _openFile(self, path):
        _, ext = os.path.splitext(path)

        if ext == '.json':
            self.openPickingFile(path)
        else:
            self.openImageFile(path)

    def openImageFile(self, path):
        """
        Open an em image for picking
        :param path: file path
        """
        if path:
            try:
                imgElem = ImageElem(os.path.basename(path), path,
                                    PPBox(self.pickingW, self.pickingH),
                                    [])
                self._on_imageAdded(imgElem)
            except:
                print(sys.exc_info())
                self.showError(sys.exc_info()[2])

    def openPickingFile(self, path):
        """
        Open the picking specification file an add the ImageElem
        to the treeview widget
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
                        self.showError("Parsing pick file: " +
                                       error.errorString())
                    else:
                        parser = ImageElemParser()
                        imgElem = parser.parseImage(json.object())
                        if imgElem:
                            self.ppSystem.addImage(imgElem)
                            self._on_imageAdded(imgElem)
                else:
                    self.showError("Error opening file.")
                    file = None

            except:
                print(sys.exc_info())
            finally:
                if file:
                    file.close()

    def _setupImageView(self):
        """
        Setup the ImageView widget used to show the images
        """
        if self.imageView:
            if self.disableHistogram:
                self.imageView.ui.histogram.hide()
            if self.disableMenu:
                self.imageView.ui.menuBtn.hide()
            if self.disableROI:
                self.imageView.ui.roiBtn.hide()
            if self.disableZoom:
                self.imageView.getView().setMouseEnabled(False, False)

    def __setupUi__(self):
        self.setObjectName("MainWindow")
        self.resize(1097, 741)
        self.centralWidget = QtWidgets.QWidget(self)
        self.centralWidget.setObjectName("centralWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralWidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.splitter = QtWidgets.QSplitter(self.centralWidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.widget = QtWidgets.QWidget(self.splitter)
        self.widget.setObjectName("widget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.widget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.lineEdit = QtWidgets.QLineEdit(self.widget)
        self.lineEdit.setObjectName("lineEdit")
        self.verticalLayout.addWidget(self.lineEdit)
        self.treeViewImages = QtWidgets.QTreeView(self.widget)
        self.treeViewImages.setObjectName("treeViewImages")
        self.verticalLayout.addWidget(self.treeViewImages)
        self.imageView = pg.ImageView(self)
        vb = self.imageView.getView()
        vb.mouseClickEvent = self.viewBoxMouseClickEvent

        self.splitter.addWidget(self.imageView)
        self.imageView.setObjectName("imageView")
        self.horizontalLayout.addWidget(self.splitter)
        self.setCentralWidget(self.centralWidget)
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setObjectName("toolBar")
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.menuBar = QtWidgets.QMenuBar(self)
        self.menuBar.setGeometry(QtCore.QRect(0, 0, 1097, 26))
        self.menuBar.setObjectName("menuBar")
        self.menuFile = QtWidgets.QMenu(self.menuBar)
        self.menuFile.setObjectName("menuFile")
        self.setMenuBar(self.menuBar)

        def _creaNewAction(parent, actionName, faIconName,
                           text="", checkable=False):
            a = QtWidgets.QAction(parent)
            a.setObjectName(actionName)
            a.setIcon(qta.icon(faIconName))
            a.setCheckable(checkable)
            a.setText(text)
            return a

        self.actionPickRect = _creaNewAction(self, "actionPickRect", "fa.clone",
                                             checkable=True)
        self.actionOpenPick = _creaNewAction(self, "actionOpenPick",
                                             "fa.folder-open",
                                             text="Open Pick File")
        self.actionNextImage = _creaNewAction(self, "actionNextImage",
                                              "fa.arrow-right")
        self.actionPrevImage = _creaNewAction(self, "actionPrevImage",
                                              "fa.arrow-left")
        self.actionSetPickBox = _creaNewAction(self, "actionSetPickBox",
                                               "fa.arrows-alt")

        self.toolBar.addAction(self.actionOpenPick)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPrevImage)
        self.toolBar.addAction(self.actionNextImage)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionSetPickBox)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPickRect)
        self.menuFile.addAction(self.actionOpenPick)
        self.menuFile.addSeparator()
        self.menuBar.addAction(self.menuFile.menuAction())

        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.toolBar.setWindowTitle(_translate("MainWindow", "toolBar"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.actionPickRect.setText(_translate("MainWindow", "PickRect"))
        self.actionOpenPick.setText(_translate("MainWindow", "Open Pick"))
        self.actionNextImage.setText(_translate("MainWindow", "Next Image"))
        self.actionPrevImage.setText(_translate("MainWindow", "Prev Image"))
        self.actionSetPickBox.setText(_translate("MainWindow", "Box size..."))


    def viewBoxMouseClickEvent(self, ev):
        """
        Invoked when the user clicks
        on the ViewBox (ImageView contains a ViewBox).
        :param ev: Mouse event
        :return:
        """
        if ev.button() == QtCore.Qt.LeftButton and \
                self.actionPickRect.isChecked():
            pos = ev.pos()

            pos = self.imageView.getView().mapToView(pos)
            roi = self._createRectROI((pos.x()-self.pickingH/2,
                                       pos.y()-self.pickingW/2),
                                      (self.pickingW, self.pickingH),
                                      centered=True,
                                      pen=(0, 9))
            roi.pickCoord = PPCoordinate(pos.x(), pos.y())
            self.imageView.getView().addItem(roi)
            # add coordinate to actual image elem
            if self.actualImage:
                self.actualImage.\
                    addPPCoordinate(roi.pickCoord)

    @pyqtSlot()
    def completerSelection(self):
        QMessageBox.information(self, "Information", "Not yet implemented")

    def _createRectROI(self, pos, size, centered=False, sideScalers=False,
                       **args):
        """
        Create a RectROI. The params are in agreement to the constructor
        of the class. We connect the following slots:
        PPWindow._roiSizeChanged
        PPWindow._roiMouseHover
        PPWindow._roiRemoveRequested

        :param pos:
        :param size:
        :param centered:
        :param sideScalers:
        :param args:
        :return:
        """
        roi = PPRectROI(pos, size, **args, centered=centered,
                         sideScalers=sideScalers,
                         removable=not self.disableRemoveROIs)
        roi.sigRegionChangeFinished.connect(self._roiSizeChanged)
        roi.sigHoverEvent.connect(self._roiMouseHover)
        roi.sigRemoveRequested.connect(self._roiRemoveRequested)

        roi.aspectLocked = not self.disableROIAspectLocked

        for h in roi.getHandles():
            h.hide()  # Hide all handlers

        return roi

    @pyqtSlot(object)
    def _roiMouseHover(self, roi):
        """
        This slot is invoked when the mouse enters the ROI.
        We need to show the handlers for user operations
        :param roi: The roi
        """
        for h in roi.getHandles():
            h.show()  # Show all handlers

    @pyqtSlot(object)
    def _roiSizeChanged(self, roi):
        """
        This slot is invoked when a roi change its size
        :param roi:
        :return:
        """
        if isinstance(roi, PPRectROI):  # Only PPRectROI for now
            roiSize = roi.size()
            roiPos = roi.pos()
            pos = roiPos + roiSize/2

            roi.pickCoord.set(pos.x(), pos.y())

            for r in self.imageView.getView().addedItems:
                if isinstance(r, PPRectROI) and not r == roi:
                    r.setSize(roiSize, finish=False)

            if self.actualImage:
                self.actualImage.setBox(PPBox(roiSize.x(), roiSize.y()))

    @pyqtSlot(object)
    def _roiRemoveRequested(self, roi):
        """
        This slot is invoked when the roi will be removed
        :param roi: The roi
        """
        if roi:
            self.imageView.getView().removeItem(roi)

    def _disconnectAllSlots(self, roi):
        """
        Disconnect from roi the slots:
        PPWindow._roiSizeChanged
        PPWindow._roiMouseHover
        PPWindow._roiRemoveRequested
        :param roi:
        :return:
        """
        if roi:
            roi.sigRegionChangeFinished.disconnect(self._roiSizeChanged)
            roi.sigHoverEvent.disconnect(self._roiMouseHover)
            roi.sigRemoveRequested.disconnect(self._roiRemoveRequested)

    def _clearImageView(self):
        """
        Clear the ImageView.
        Note: ImageView has the clear() method, but we need to make others
        operations like disconnect
              the sigRegionChangeFinished signal
        :return:
        """
        v = self.imageView.getView()

        for r in v.addedItems[:]:
            if isinstance(r, PPRectROI):
                v.removeItem(r)
                self._disconnectAllSlots(r)

        self.imageView.clear()


class PPItem(QStandardItem):
    """
    The PPItem is the item that we use in the treeview
    where the images are displayed
    """
    def __init__(self, text="", imgElem=None, icon=None):

        super(PPItem, self).__init__(text)
        self.imgElem = imgElem
        self.setIcon(icon)
        self.roiList = []

    def addROI(self, roi):
        """
        Add a roi to the roi list
        :param roi: the roi
        """
        if roi:
            self.roiList.append(roi)

    def getImageElem(self):
        """
        :return: The image elem corresponding to this node (or item)
        """
        return self.imgElem


class PPRectROI(RectROI):
    """
    Rect roi for particle picking
    """

    def __init__(self, pos, size, centered=False, sideScalers=False, **args):
        RectROI.__init__(self, pos, size, **args,
                        centered=centered,
                        sideScalers=sideScalers)
        self.pickCoord = None

    def hoverEvent(self, ev):
        """
        Reimplementation of hoverEvent.
        Hide all handlers
        :param ev: Mouse event
        """
        if ev.isExit():
            for h in self.getHandles():
                h.hide()  # Hide all handlers
        ROI.hoverEvent(self, ev)

    def setPickCoordinate(self, coordinate):
        """
        Set de picking coordinate
        :param coordinate: The PPCoordinate
        """
        self.pickCoord = coordinate

    def getPickCoordinate(self):
        """
        :return:  The PPCoordinate
        """
        return self.pickCoord

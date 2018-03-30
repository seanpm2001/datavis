#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QMainWindow, QStatusBar, QWidget, QVBoxLayout,
                             QLabel)

from emqt5.widgets.table.table_view import TableView
from emqt5.widgets.table.model import TableDataModel


class TableViewWindow(QMainWindow):
    """
    Main window
    """

    def __init__(self, parent=None, **kwargs):
        """ Constructor
        @param parent reference to the parent widget
        @model input TableDataModel
        """
        QMainWindow.__init__(self, parent)
        self.__setupUi__(**kwargs)
        self._model = TableDataModel(parent=self.tableView,
                                     data=kwargs['tableData'],
                                     columnProperties=kwargs['colProperties'])
        self.tableView.setModel(self._model)

    def __setupUi__(self, **kwargs):
        self.resize(816, 517)
        self.centralWidget = QWidget(self)
        self.setCentralWidget(self.centralWidget)
        self.verticalLayout = QVBoxLayout(self.centralWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.tableView = TableView(parent=self.centralWidget, **kwargs)
        self.verticalLayout.addWidget(self.tableView)

        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self._labelInfo = QLabel(parent=self.statusBar,
                                 text="Some information about...")
        self.statusBar.addWidget(self._labelInfo)

#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
from PyQt5.QtWidgets import QApplication

from emviz.models import TableModel, TYPE_INT, TYPE_STRING, ColumnConfig
from emviz.views import TablePageItemModel, GalleryView
from emviz.core import ImageManager

import em


app = QApplication(sys.argv)
testDataPath = os.environ.get("EM_TEST_DATA", None)

if testDataPath is not None:
    path = os.path.join(testDataPath, "relion_tutorial", "import", "classify2d",
                            "extra", "relion_it015_classes.mrcs")

    table = em.Table([em.Table.Column(0, "index", em.typeInt32, "Image index"),
                      em.Table.Column(1, "path", em.typeString, "Image path")])

    tableModel = TableModel(
        ColumnConfig('index', dataType=TYPE_INT, editable=False, visible=True),
        ColumnConfig('path', dataType=TYPE_STRING, renderable=True,
                     editable=False, visible=True))

    row = table.createRow()
    n = ImageManager.getDim(path).n
    for i in range(1, n+1):
        row['index'] = i
        row['path'] = '%d@%s' % (i, path)
        table.addRow(row)
    galleryView = GalleryView()
    galleryView.setIconSize((100, 100))
    galleryView.setModel(TablePageItemModel(table, parent=galleryView,
                                            title="Stack",
                                            tableViewConfig=tableModel))
    galleryView.setModelColumn(1)
    galleryView.show()

sys.exit(app.exec_())

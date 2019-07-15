
import os
import numpy as np

import em
import emviz.models as models
from emviz.utils import py23

from ._image_manager import ImageManager
from ._emtype import EmType


class EmTableModel(models.TableModel):
    """
    Implementation of TableBase with an underlying em.Table object.
    """
    def __init__(self, tableSource, **kwargs):
        """
        Initialization of an EmTableModel
        :param tableSource: Input from where table will be retrieved,
            it can be one of the following options:
            * em.Table: just a single table that will be used, not
                other tables will be loaded in this case
            * string: This should be the path from where to read
                the table(s). The first table will be loaded by default.
            * tuple (string, string): Here you can specify the path and
                the name of the table that you want to be loaded by
                default.
        :param **kwargs: Extra arguments
            * imageManager=value Provide an ImageManager that can be used
                to read images referenced from this table.
        """
        if isinstance(tableSource, em.Table):
            self._table = tableSource
            self._tableIO = None
            # Define only a single table name ''
            tableName = ''
            self._path = None
            self._tableNames = [tableName]
        else:  # In this variant we will create a em.TableIO to read data
            if isinstance(tableSource, py23.str):
                self._path, tableName = tableSource, None
            elif isinstance(tableSource, tuple):
                self._path, tableName = tableSource
            else:
                raise Exception("Invalid tableSource input '%s' (type %s)"
                                % (tableSource, type(tableSource)))
            self._tableIO = em.TableIO()
            self._tableIO.open(self._path, em.File.Mode.READ_ONLY)
            self._table = em.Table()
            self._tableNames = self._tableIO.getTableNames()
            # If not tableName provided, load first table
            tableName = tableName or self._tableNames[0]

        # Create an ImageManager if none is provided
        self._imageManager = kwargs.get('imageManager', ImageManager())
        # Use a dictionary for checking the prefix path of the
        # images columns data
        self._imagePrefixes = kwargs.get('imagePrefixes', {})
        self.loadTable(tableName)

    def __del__(self):
        if self._tableIO is not None:
            self._tableIO.close()

    def __updateColsMap(self):
        # TODO: Check if this is needed now, or should go to QtModel
        # Map between the order and the columns Id
        self._colsMap = {i: c.getId()
                         for i, c in enumerate(self._table.iterColumns())}

    def _loadTable(self, tableName):
        # Only really load table if we have created the em.TableIO
        if self._tableIO is not None:
            self._tableIO.read(tableName, self._table)
            self.__updateColsMap()

    def iterColumns(self):
        for c in self._table.iterColumns():
            yield models.ColumnInfo(c.getName(), EmType.toModel(c.getType()))

    def getColumnsCount(self):
        """ Return the number of columns. """
        return self._table.getColumnsSize()

    def getRowsCount(self):
        """ Return the number of rows. """
        return self._table.getSize()

    def getValue(self, row, col):
        """ Return the value of the item in this row, column. """
        return self._table[row][self._colsMap[col]]

    def getData(self, row, col):
        """ Return the data (array like) for the item in this row, column.
         Used by rendering of images in a given cell of the table.
        """
        value = str(self._table[row][self._colsMap[col]])
        imgRef = self._imageManager.getRef(value)

        if col in self._imagePrefixes:
            imgPrefix = self._imagePrefixes[col]
        else:
            imgPrefix = self._imagePrefixes.get(
                col, self._imageManager.findImagePrefix(value, self._path))
            print("Finding image prefix: ", imgPrefix)
            self._imagePrefixes[col] = imgPrefix

        if imgPrefix is not None:
            imgRef.path = os.path.join(imgPrefix, imgRef.path)

        return self._imageManager.getData(imgRef)


class EmStackModel(models.SlicesModel):
    """
    The EmStackModel class provides the basic functionality for image stack.
    The following methods are wrapped directly from SlicesModel:
        - getDim
        - getData
        - getLocation
        - getImageModel
    """
    def __init__(self, path, **kwargs):
        """
        Constructs an EmStackModel.
        Note that you can specify the path and/or SlicesModel.
        :param path:     (str) The image path
        :param kwargs:
         - slicesModel : (SlicesModel) The SlicesModel from which this
                         EmStackModel will be created.
         - columnName  : (str) The column name for image column.
                         if columnName is None, then 'Image' will be used.
        """
        models.SlicesModel.__init__(self, **kwargs)
        self._path = path
        if path is not None:
            imgio = em.ImageIO()
            imgio.open(path, em.File.READ_ONLY)
            dim = imgio.getDim()
            image = em.Image()

            if dim.z > 1:
                raise Exception("No valid image type: Volume.")
            self._data = []
            self._dim = dim.x, dim.y, dim.n
            # FIXME: Implement read on-demand, we can't have all stacks
            # in memory always
            for i in range(1, dim.n + 1):
                imgio.read(i, image)
                self._data.append(np.array(image, copy=True))
            imgio.close()

    def getLocation(self):
        """ Returns the image location(the image path). """
        return self._path

    # TODO: Maybe we will need to implement the getData in
    # the case that we don't want to store the whole stack in memory


class EmVolumeModel(models.VolumeModel):
    """
    The EmVolumeModel class provides the basic functionality for image volume
    """
    def __init__(self, path, data=None):
        """
        Constructs an EmVolumeModel.
        :param path: (str) The volume path
        :param data: (numpy array) The volume data
        """
        self._path = path
        if data is None:
            imgio = em.ImageIO()
            imgio.open(path, em.File.READ_ONLY)
            dim = imgio.getDim()
            image = em.Image()

            if dim.z <= 1:
                raise Exception("No valid image type.")
            imgio.read(1, image)
            data = np.array(image, copy=True)
            imgio.close()

        models.VolumeModel.__init__(self, data)
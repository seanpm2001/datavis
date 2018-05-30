
import em


class TableViewConfig:
    """
    Class that allows to specify options for the behaviour of certain Views.
    These views are related to the visualization of tabular data.
    """

    """ Datatypes that will be used for the visualization. """
    TYPE_BOOL = 0
    TYPE_INT = 1
    TYPE_FLOAT = 2
    TYPE_STRING = 3
    # TODO: other possibilities for the future:
    # TYPE_URL, TYPE_IMAGE, etc

    """ Basic type map between em.Type and current types. """
    TYPE_MAP = {
        em.typeBool: TYPE_BOOL,
        em.typeInt8: TYPE_INT,
        em.typeInt16: TYPE_INT,
        em.typeInt32: TYPE_INT,
        em.typeInt64: TYPE_INT,
        em.typeFloat: TYPE_FLOAT,
        em.typeDouble: TYPE_FLOAT,
        em.typeString: TYPE_STRING
    }

    def __init__(self):
        # Store a list of ColumnConfig objects
        self._cols = []

    def addColumnConfig(self, *args, **kwargs):
        """ Add a new column config. """
        self._cols.append(ColumnConfig(*args, **kwargs))

    def __iter__(self):
        """ Iterate through all the column configs. """
        for colConfig in self._cols:
            yield colConfig

    def __str__(self):
        s = "TableViewConfig columnConfigs: %d" % len(self._cols)
        for c in self._cols:
            s += '\n%s' % str(c)
        return s

    def __getitem__(self, *args, **kwargs):
        return self._cols[args[0]]

    def __len__(self):
        return len(self._cols)

    @classmethod
    def fromTable(cls, table, colsConfig=None):
        """
        Create a TableViewConfig instance from a given em.Table input.
        This function allows users to specify the minimum of properties
        and create the config from that.
        :param table: input em.Table that will be visualized
        :param colsConfig: this will be a list of elements to specify
            the values for each ColumnConfig. Each element could be either
            a single string (the column name) or a tuple (column name and
            a dict with properties). If only the column name is provided,
            the property values will be inferred from the em.Table.Column.
        :return: an instance of TableViewConfig
        """
        # TODO: Implement iterColumns in table
        # tableColNames = [col.getName() for col in table.iterColumns()]
        tableColNames = [table.getColumnByIndex(i).getName()
                         for i in range(table.getColumnsSize())]

        if colsConfig is None:
            colsConfig = tableColNames

        tvConfig = TableViewConfig()

        for item in colsConfig:
            if isinstance(item, str):
                name = item
                properties = {}
            elif isinstance(item, tuple):
                name, properties = item
            else:
                raise Exception("Invalid item type: %s" % type(item))

            # Only consider names that are present in the table ignore others
            if name in tableColNames:
                col = table.getColumn(name)
                # Take the values from the 'properties' dict or infer from col
                cType = cls.TYPE_MAP.get(col.getType(), cls.TYPE_STRING)
                if 'description' not in properties:
                    properties['description'] = col.getDescription()
                tvConfig.addColumnConfig(name, cType, **properties)
        return tvConfig


class ColumnConfig:
    """
    Store some properties about the visualization of a given column.
    """
    def __init__(self, name, dataType, **kwargs):
        """
        Constructor
        :param name: column name
        :param label: column label
        :param type: column type : 'Bool', 'Int', 'Float', 'Str', 'Image'
        :param kwargs:
            - visible (Bool)
            - visibleReadOnly (Bool)
            - renderable (Bool)
            - renderableReadOnly (Bool)
            - editable (Bool)
            - editableReadOnly (Bool)
        """
        self._name = name
        self._label = kwargs.get('label', name)
        self._type = dataType
        self._description = kwargs.get('description', '')
        self._propertyNames = []
        self.__setProperty__('visible', True, False, **kwargs)
        self.__setProperty__('renderable', False, False, **kwargs)
        self.__setProperty__('editable', False, True, **kwargs)

    def __setProperty__(self, name, default, defaultRO, **kwargs):
        """ Internal function to define a 'property' that will
        define an attribute with similar name and also a 'ReadOnly'
        flag to define when the property can be changed or not.
        :param name: the name of the property to be defined
        :param default: default value for the property
        :param defaultRO: default value for propertyReadOnly
        :param **kwargs: keyword-arguments from where to read the values
        """
        setattr(self, '__%s' % name, kwargs.get(name, default))
        self._propertyNames.append(name)
        roName = name + 'ReadOnly'
        setattr(self, '__%s' % roName, kwargs.get(roName, defaultRO))
        self._propertyNames.append(roName)

    def getName(self):
        """ Return the original name of the represented column."""
        return self._name

    def getLabel(self):
        """ Return the string that will be used to display this column. """
        return self._label

    def getType(self):
        return self._type

    def getDescrition(self):
        return self._description

    def getPropertyValue(self, propName):
        """ Return the value for specified propName"""
        return self.__getitem__(propName)

    def __getitem__(self, propertyName):
        """ Return the value of a given property.
        If the property does not exits, an Exception is raised.
        """
        if propertyName not in self._propertyNames:
            raise Exception("Invalid property name: %s" % propertyName)

        return getattr(self, '__%s' % propertyName)

    def __setitem__(self, propertyName, value):
        """ Return the value of a given property.
        If the property does not exits, an Exception is raised.
        """
        if propertyName not in self._propertyNames:
            raise Exception("Invalid property name: %s" % propertyName)

        return setattr(self, '__%s' % propertyName, value)

    def __str__(self):
        """ A readable representation. """
        s = "ColumnConfig: name = %s\n" % self.getName()
        s += "   label: %s\n" % self.getLabel()
        s += "    desc: %s\n" % self.getDescrition()
        s += "    type: %s\n" % self.getType()
        for p in self._propertyNames:
            s += "    %s: %s\n" % (p, self[p])

        return s
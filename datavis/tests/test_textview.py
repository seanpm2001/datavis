
import sys

import PyQt5.QtWidgets as qtw

import datavis as dv


app = qtw.QApplication(sys.argv)

win = qtw.QMainWindow()
win.resize(500, 300)

Param = dv.models.Param
fileTypes = Param('fileType', dv.models.PARAM_TYPE_ENUM,
                  label='File types',
                  choices=['.py', '.json', 'text file'],
                  display=dv.models.PARAM_DISPLAY_HLIST, value=0)

form = dv.models.Form([fileTypes])
centralWidget = dv.widgets.ViewPanel(None,
                                     dv.widgets.ViewPanel.VERTICAL)
selectionWidget = dv.widgets.FormWidget(form, parent=centralWidget)
textView = dv.widgets.TextView(centralWidget)
textView.setReadOnly(True)

centralWidget.addWidget(selectionWidget, 'selectionWidget')
centralWidget.addWidget(textView, 'textView')


def paramChanged(paramName, value):
    if paramName == 'fileType':
        if value == 0:  # python code example
            text = dv.tests.getPythonCodeExample()
            textView.setHighlighter(dv.widgets.PythonHighlighter(None))
            textView.setPlainText(text)
        elif value == 1:  # json example
            text = dv.tests.getJsonTextExample()
            textView.setHighlighter(
                dv.widgets.JsonSyntaxHighlighter(None))
            textView.setPlainText(text)
        else:
            textView.setHighlighter(None)
            textView.setPlainText("This is a text example.\n"
                                  "The Highlighter works very well.")
    else:
        print("Oh!! wrong param.")


selectionWidget.sigValueChanged.connect(paramChanged)

win.setCentralWidget(centralWidget)
win.show()
win.setWindowTitle('TextView example')

paramChanged('fileType', 0)

sys.exit(app.exec_())
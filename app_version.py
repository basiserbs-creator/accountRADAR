"""
Losse module voor het versienummer - apart van main.py zodat zowel
main.py als ui/main_window.py dit kunnen importeren zonder circulaire
import (main.py importeert MainWindow uit ui.main_window, dus
main_window.py kan niet omgekeerd weer uit main.py importeren).
"""

APP_VERSION = "build 19"
